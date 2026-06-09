"""
Fast mock-based tests for I18nRenderer.translate_data.

These tests exercise the dedup + parallel logic without hitting any external
translator service. Each test monkeypatches ``lang.translate`` so:

* we count how often it is invoked (proving dedup works);
* we control the returned value to assert the structure is rebuilt
  correctly.

Behaviour-preserving guarantees we check:

* duplicate values are translated exactly once across the whole dataset;
* the output structure (sections → entries → key → fields) is identical to
  the input shape;
* ``update_i18n=True`` reuses existing translations from ``original_i18n``
  and does NOT call the translator for those fields;
* ``update_i18n=False`` always calls the translator (overwrite mode).
"""

from typing import Any, Dict, List

import crunch_uml.lang as lang
from crunch_uml.renderers.pandasrenderer import I18nRenderer


def _make_data(n_entries: int, n_unique: int):
    """Build a small data dict with controlled (key, value) repetition.

    Each entry has one record with two fields: ``name`` and ``definitie``.
    Values cycle through ``n_unique`` distinct strings so duplicates happen
    deterministically.
    """
    data: Dict[str, List[Dict[str, Any]]] = {"classes": []}
    for i in range(n_entries):
        v = f"value_{i % n_unique}"
        data["classes"].append({f"id_{i}": {"name": v, "definitie": v + "_def"}})
    return data


def _record_calls(monkeypatch):
    calls: List[str] = []

    def fake_translate(value, to_language, from_language="auto", **kwargs):
        # **kwargs accepts the optional ``context`` (and any other future
        # forwarded kwargs) so this stub stays compatible with the public
        # lang.translate signature.
        calls.append(value)
        return f"<{to_language}:{value}>"

    monkeypatch.setattr(lang, "translate", fake_translate)
    return calls


def test_translate_data_deduplicates_repeated_strings(monkeypatch):
    """100 entries × 2 fields = 200 fields, but only 5 unique values per field
    (10 unique strings total). The translator must be called 10 times."""
    calls = _record_calls(monkeypatch)
    data = _make_data(n_entries=100, n_unique=5)

    renderer = I18nRenderer()
    out = renderer.translate_data(data, to_language="en", from_language="nl")

    # 5 unique "value_N" + 5 unique "value_N_def" = 10 unique strings.
    assert len(set(calls)) == 10
    assert len(calls) == 10, f"expected 10 calls (no duplicates); got {len(calls)}"

    # Output structure preserved.
    assert set(out.keys()) == {"classes"}
    assert len(out["classes"]) == 100
    for i, entry in enumerate(out["classes"]):
        assert list(entry.keys()) == [f"id_{i}"]
        rec = entry[f"id_{i}"]
        assert set(rec.keys()) == {"name", "definitie"}
        # Translated values follow the fake formatter.
        v = f"value_{i % 5}"
        assert rec["name"] == f"<en:{v}>"
        assert rec["definitie"] == f"<en:{v}_def>"


def test_translate_data_uses_existing_translations_when_update_i18n_true(monkeypatch):
    """When original_i18n already contains a translation for (section, key,
    field), update_i18n=True must reuse it and skip the translator entirely.
    """
    calls = _record_calls(monkeypatch)
    data = {
        "classes": [
            {"id_1": {"name": "Aap", "definitie": "Een primaat"}},
            {"id_2": {"name": "Beer", "definitie": "Roofdier"}},
        ]
    }
    original_i18n = {
        "en": {
            "classes": [
                # Both fields of id_1 already translated → skip both
                {"id_1": {"name": "Monkey", "definitie": "A primate"}},
                # Only the name of id_2 is known → only definitie gets translated
                {"id_2": {"name": "Bear"}},
            ]
        }
    }

    out = I18nRenderer().translate_data(
        data, to_language="en", from_language="nl", update_i18n=True, original_i18n=original_i18n
    )

    # Only id_2.definitie remains untranslated → exactly one call.
    assert calls == ["Roofdier"], f"expected one translator call (Roofdier); got {calls}"

    # Verify the known values came from original_i18n unchanged.
    classes_out = out["classes"]
    id1 = next(e["id_1"] for e in classes_out if "id_1" in e)
    id2 = next(e["id_2"] for e in classes_out if "id_2" in e)
    assert id1 == {"name": "Monkey", "definitie": "A primate"}
    assert id2["name"] == "Bear"
    assert id2["definitie"] == "<en:Roofdier>"


def test_translate_data_overwrites_when_update_i18n_false(monkeypatch):
    """update_i18n=False must translate every string, ignoring original_i18n."""
    calls = _record_calls(monkeypatch)
    data = {"classes": [{"id_1": {"name": "Aap"}}]}
    original_i18n = {"en": {"classes": [{"id_1": {"name": "AlreadyTranslated"}}]}}

    out = I18nRenderer().translate_data(
        data,
        to_language="en",
        from_language="nl",
        update_i18n=False,
        original_i18n=original_i18n,
    )

    assert calls == ["Aap"], f"expected translator call for 'Aap'; got {calls}"
    assert out["classes"][0]["id_1"]["name"] == "<en:Aap>"


def test_translate_data_logs_progress_per_call(monkeypatch, caplog):
    """Every completed translation must be logged at INFO level with an
    ``[n/total]`` progress counter so a long batch is observable in real
    time."""
    _record_calls(monkeypatch)
    data = {
        "classes": [
            {"id_1": {"name": "Aap"}},
            {"id_2": {"name": "Beer"}},
            {"id_3": {"name": "Koe"}},
        ]
    }

    with caplog.at_level("INFO", logger="root"):
        I18nRenderer().translate_data(data, to_language="en", from_language="nl")

    progress_lines = [msg for msg in caplog.messages if " → " in msg and "/" in msg]
    assert len(progress_lines) == 3, f"expected 3 progress lines, got {progress_lines}"
    # The header line announcing the unique-string count must also appear.
    assert any("Translating 3 unique strings" in msg for msg in caplog.messages)
    # Each progress line carries the [n/total] counter and the translation.
    sources_seen = set()
    for line in progress_lines:
        assert any(f"[{i}/3]" in line for i in (1, 2, 3))
        for src in ("Aap", "Beer", "Koe"):
            if src in line:
                sources_seen.add(src)
    assert sources_seen == {"Aap", "Beer", "Koe"}


def test_translate_data_skips_empty_and_non_string_values(monkeypatch):
    """Empty/whitespace strings and non-string values are never translated."""
    calls = _record_calls(monkeypatch)
    data = {
        "classes": [
            {"id_1": {"name": "", "definitie": None, "count": 7, "real": "Hond"}},
        ]
    }

    out = I18nRenderer().translate_data(data, to_language="en", from_language="nl")
    assert calls == ["Hond"]
    # The output only contains the field that was actually translated.
    assert out["classes"][0]["id_1"] == {"real": "<en:Hond>"}
