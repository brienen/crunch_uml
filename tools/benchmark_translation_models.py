#!/usr/bin/env python3
"""Golden-testset benchmark for translation workhorse candidates.

Builds a deterministic golden set from an existing, reviewed i18n file (the
reference translations) joined by GUID with the Dutch source in a crunch_uml
database, then scores one or more Ollama models on it:

* **name accuracy** — normalised match (same check as the pipeline's voting
  layer) between the model's name translation and the reference;
* **chrF** — character n-gram F-score of the translated definition against
  the reference definition (0..1, higher is better);
* **glossary compliance** — for elements whose definition mentions other
  class names, the reference translations of those names are passed as a
  binding glossary (exactly like the pipeline's glossary propagation) and
  violations are counted;
* **speed** — average seconds per element call.

Every call goes through the pipeline's own ``translate_element_once`` —
temperature 0, fixed seed, JSON schema — so the benchmark measures the real
call path, not a simplified one.

Results are merged into a JSON file so each model can be benchmarked in a
separate invocation (Ollama loads one model at a time); the summary table
prints every model present in the file. Example:

    .venv/bin/python tools/benchmark_translation_models.py \\
        --db "../GemeentelijkGegevensmodel-v3.0.0/crunch_uml.db" \\
        --schema GGM_ROOT_SCHEMA \\
        --i18n "../GemeentelijkGegevensmodel-v3.0.0/v3.0.0/translations/ggm.i18n.json" \\
        --language en --models mistral-small3.1:24b \\
        --out /tmp/benchmark_results.json

Caveat: the reference is the *existing* i18n translation. Scores measure
agreement with that reference, which is itself imperfect — treat them as
relative ranking between models, and inspect the printed disagreements.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from crunch_uml.translation.config import TranslationConfig
from crunch_uml.translation.llm import (
    Element,
    _term_in_text,
    glossary_violations,
    names_agree,
    translate_element_once,
)

logging.basicConfig(level=logging.WARNING)

# Elements sampled per section (deterministic, evenly spaced over the
# GUID-sorted population).
SECTION_SAMPLES = {"classes": 30, "attributes": 20, "enumerationliterals": 10}
MIN_DEFINITION_CHARS = 20
MAX_GLOSSARY_ENTRIES = 10


# ---------------------------------------------------------------------------
# chrF (character n-gram F-score), self-contained implementation
# ---------------------------------------------------------------------------


def _char_ngrams(text: str, n: int) -> Counter:
    text = " ".join(text.split()).lower()
    return Counter(text[i : i + n] for i in range(len(text) - n + 1))


def chrf(hypothesis: str, reference: str, max_n: int = 6, beta: float = 2.0) -> float:
    """chrF score (Popović 2015): mean F-beta over character 1..6-grams."""
    if not hypothesis or not reference:
        return 0.0
    scores = []
    for n in range(1, max_n + 1):
        hyp, ref = _char_ngrams(hypothesis, n), _char_ngrams(reference, n)
        if not hyp or not ref:
            continue
        overlap = sum((hyp & ref).values())
        precision = overlap / sum(hyp.values())
        recall = overlap / sum(ref.values())
        if precision + recall == 0:
            scores.append(0.0)
        else:
            b2 = beta * beta
            scores.append((1 + b2) * precision * recall / (b2 * precision + recall))
    return sum(scores) / len(scores) if scores else 0.0


# ---------------------------------------------------------------------------
# Golden set construction
# ---------------------------------------------------------------------------


def _index_i18n_section(i18n: Dict, language: str, section: str) -> Dict[str, Dict]:
    result: Dict[str, Dict] = {}
    for entry in i18n.get(language, {}).get(section, []):
        result.update(entry)
    return result


def build_golden_set(db_path: str, schema: str, i18n_path: str, language: str) -> Tuple[List[Dict], Dict[str, str]]:
    """Join the Dutch source (db) with the reference translation (i18n) per
    GUID. Returns (golden elements, class-name glossary map nl->reference)."""
    with open(i18n_path, encoding="utf-8") as f:
        i18n = json.load(f)
    conn = sqlite3.connect(db_path)

    # Reference translations of ALL class names: the glossary source, exactly
    # like the pipeline's cross-level glossary propagation.
    class_refs = _index_i18n_section(i18n, language, "classes")
    class_glossary: Dict[str, str] = {}
    for guid, name in conn.execute("SELECT id, name FROM classes WHERE schema_id=? AND name IS NOT NULL", (schema,)):
        ref_name = (class_refs.get(guid) or {}).get("name")
        if name and ref_name and len(name) > 3:
            class_glossary[name] = ref_name

    golden: List[Dict] = []
    for section, sample_size in SECTION_SAMPLES.items():
        refs = _index_i18n_section(i18n, language, section)
        rows = conn.execute(
            f"SELECT id, name, definitie FROM {section} WHERE schema_id=? AND name IS NOT NULL ORDER BY id",
            (schema,),
        ).fetchall()
        candidates = []
        for guid, name, definitie in rows:
            ref = refs.get(guid) or {}
            if not name or not ref.get("name"):
                continue
            src_def = (definitie or "").strip()
            ref_def = (ref.get("definitie") or "").strip()
            has_def = len(src_def) >= MIN_DEFINITION_CHARS and len(ref_def) >= MIN_DEFINITION_CHARS
            fields = {"name": name}
            if has_def:
                fields["definitie"] = src_def
            glossary = {}
            if has_def:
                glossary = {
                    src: tgt for src, tgt in class_glossary.items() if src != name and _term_in_text(src, src_def)
                }
                glossary = dict(sorted(glossary.items())[:MAX_GLOSSARY_ENTRIES])
            candidates.append(
                {
                    "section": section,
                    "guid": guid,
                    "fields": fields,
                    "reference": {"name": ref["name"], **({"definitie": ref_def} if has_def else {})},
                    "glossary": glossary,
                }
            )
        # Deterministic, evenly spaced sample over the GUID-sorted list.
        if len(candidates) > sample_size:
            step = len(candidates) / sample_size
            candidates = [candidates[int(i * step)] for i in range(sample_size)]
        golden.extend(candidates)

    conn.close()
    return golden, class_glossary


# ---------------------------------------------------------------------------
# Benchmark run
# ---------------------------------------------------------------------------


def run_model(model: str, golden: List[Dict], config: TranslationConfig, workers: int) -> Dict:
    def _one(item: Dict) -> Tuple[Dict, Optional[Dict[str, str]], float]:
        element = Element(section=item["section"], key=item["guid"], fields=dict(item["fields"]))
        start = time.time()
        try:
            result = translate_element_once(
                element, "en", "nl", model=model, config=config, glossary=item["glossary"] or None
            )
        except Exception as e:
            print(f"  FOUT bij {item['guid']}: {e}", file=sys.stderr)
            return item, None, time.time() - start
        return item, result, time.time() - start

    started = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = list(pool.map(_one, golden))
    wall = time.time() - started

    per_element = []
    name_hits = name_total = 0
    chrf_scores = []
    gloss_total = gloss_violated = 0
    failures = 0
    for item, result, seconds in outcomes:
        if result is None:
            failures += 1
            continue
        ref = item["reference"]
        record = {
            "section": item["section"],
            "guid": item["guid"],
            "source": item["fields"],
            "reference": ref,
            "output": result,
            "seconds": round(seconds, 2),
        }
        name_total += 1
        record["name_match"] = names_agree(result.get("name"), ref["name"])
        name_hits += record["name_match"]
        if "definitie" in ref and "definitie" in result:
            record["chrf"] = round(chrf(result["definitie"], ref["definitie"]), 4)
            chrf_scores.append(record["chrf"])
        if item["glossary"] and "definitie" in result:
            gloss_total += 1
            violations = glossary_violations(item["fields"]["definitie"], result["definitie"], item["glossary"])
            record["glossary_violations"] = violations
            gloss_violated += bool(violations)
        per_element.append(record)

    return {
        "model": model,
        "elements": len(golden),
        "failures": failures,
        "name_accuracy": round(name_hits / name_total, 4) if name_total else None,
        "chrf_mean": round(sum(chrf_scores) / len(chrf_scores), 4) if chrf_scores else None,
        "glossary_tested": gloss_total,
        "glossary_compliance": round(1 - gloss_violated / gloss_total, 4) if gloss_total else None,
        "seconds_per_element": round(wall / len(golden), 2),
        "wall_seconds": round(wall, 1),
        "per_element": per_element,
    }


def print_summary(results: Dict[str, Dict]) -> None:
    print("\n| model | naam-accuraat | chrF (definities) | glossarium-naleving | sec/element |")
    print("|---|---|---|---|---|")
    for model, r in results.items():
        gloss = (
            f"{r['glossary_compliance']:.0%} (n={r['glossary_tested']})"
            if r["glossary_compliance"] is not None
            else "—"
        )
        print(f"| {model} | {r['name_accuracy']:.0%} | {r['chrf_mean']:.3f} | {gloss} | {r['seconds_per_element']} |")


def print_disagreements(result: Dict, limit: int = 5) -> None:
    """The most interesting output: where the model and the reference differ."""
    misses = [r for r in result["per_element"] if not r["name_match"]]
    if misses:
        print(f"\nNaam-afwijkingen t.o.v. referentie ({result['model']}, eerste {limit}):")
        for r in misses[:limit]:
            print(
                f"  {r['source']['name']!r}: model={r['output'].get('name')!r} vs referentie={r['reference']['name']!r}"
            )
    lows = sorted((r for r in result["per_element"] if "chrf" in r), key=lambda r: r["chrf"])[:limit]
    if lows:
        print(f"\nLaagste chrF-definities ({result['model']}):")
        for r in lows:
            print(f"  [{r['chrf']:.2f}] {r['source']['name']}: {r['output'].get('definitie', '')[:90]!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="pad naar crunch_uml.db met de Nederlandse bron")
    parser.add_argument("--schema", default="GGM_ROOT_SCHEMA")
    parser.add_argument("--i18n", required=True, help="pad naar het i18n-bestand met referentievertalingen")
    parser.add_argument("--language", default="en")
    parser.add_argument("--models", nargs="+", required=True, help="Ollama-modeltags om te benchmarken")
    parser.add_argument("--out", default="benchmark_results.json", help="JSON-resultaten (wordt samengevoegd)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    golden, class_glossary = build_golden_set(args.db, args.schema, args.i18n, args.language)
    with_def = sum(1 for g in golden if "definitie" in g["fields"])
    with_gloss = sum(1 for g in golden if g["glossary"])
    print(
        f"Gouden testset: {len(golden)} elementen ({with_def} met definitie, {with_gloss} met glossarium;"
        f" {len(class_glossary)} klassenamen als glossariumbron)"
    )

    try:
        with open(args.out, encoding="utf-8") as f:
            all_results = json.load(f)
    except (OSError, json.JSONDecodeError):
        all_results = {}

    config = TranslationConfig(ollama_timeout=args.timeout, workers=args.workers)
    for model in args.models:
        print(f"\nBenchmark {model}: {len(golden)} elementen...")
        result = run_model(model, golden, config, args.workers)
        all_results[model] = result
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(
            f"Klaar in {result['wall_seconds']}s — naam {result['name_accuracy']:.0%},"
            f" chrF {result['chrf_mean']:.3f}, mislukt: {result['failures']}"
        )
        print_disagreements(result)

    print_summary(all_results)
    print(f"\nVolledige resultaten (per element): {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
