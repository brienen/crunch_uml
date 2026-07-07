"""Layered, deterministic translation pipeline (backend ``pipeline``).

See docs/technisch/vertaalpijplijn.md for the full design. In short:

1. the i18n output file is the translation memory (reuse per section/GUID/field);
2. termbanks (IATE TBX, EuroVoc/GEMMA as Linked Open Data) supply candidate
   concepts, disambiguated deterministically on the source definition;
3. a local LLM (Ollama) translates per model element with a binding glossary,
   two workhorse models voting on names and a heavy model arbitrating;
4. an optional NMT model is the safety net below the LLM;
5. online services (Google/Bing) run only when explicitly allowed.

Configuration is environment-variable based (``CRUNCH_UML_*``) — no config
files. A preflight establishes which layers are available and degrades
gracefully, with warnings, when resources are missing or outdated.
"""
