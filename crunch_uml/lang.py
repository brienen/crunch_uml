import logging
import os
import time

import translators as ts  # type: ignore

from crunch_uml import ollama_translator

logger = logging.getLogger()
ALTERNATIVE_TRANSLATOR = "google"  # Alternatieve vertaalmachine


def translate(value, to_language, from_language, *, context=None, max_retries=3, sleep_between_retries=60):
    """
    Probeert een vertaling uit te voeren en bij een fout probeert het opnieuw, met een maximum van 3 pogingen.
    Tussen de pogingen wordt 1 minuut gewacht.

    Backend wordt geselecteerd via de env-var ``CRUNCH_UML_TRANSLATE_BACKEND``:

    * ``translators`` (default) → bestaande Google/Bing-route via de
      ``translators``-library.
    * ``ollama`` → lokale LLM via :mod:`crunch_uml.ollama_translator`. Bij
      onbereikbare Ollama valt de call alsnog terug op ``translators`` zodat
      we geen vertalingen verliezen.

    De optionele ``context``-dict wordt alleen door de Ollama-backend
    gebruikt; voor de externe API heeft het geen betekenis en wordt het
    genegeerd (compatibel met de bestaande call sites).
    """
    backend = os.environ.get("CRUNCH_UML_TRANSLATE_BACKEND", "translators").lower()
    if backend == "ollama":
        try:
            return ollama_translator.translate(value, to_language, from_language, context=context)
        except Exception as e:
            logger.warning(f"Ollama-vertaling mislukt voor '{value}' ({e}); val terug op translators-API...")
            # door naar de bestaande translators-flow hieronder

    logger.debug(f"Translating text '{value}' from language '{from_language}' to '{to_language}'...")
    attempt = 0
    while attempt < max_retries:
        try:
            # Probeer de vertaling uit te voeren
            translated_text = ts.translate_text(
                value,
                to_language=to_language,
                from_language=from_language,
                update_session_after_seconds=10,
                if_ignore_limit_of_length=True,
            )
            return translated_text  # Als de vertaling succesvol is, geef het resultaat terug
        except Exception:
            try:
                logger.warning(
                    f"Fout opgetreden bij vertalen van tekst '{value}', probeer alternatieve vertaalmachine"
                    f" {ALTERNATIVE_TRANSLATOR}..."
                )
                # Probeer de vertaling uit te voeren
                translated_text = ts.translate_text(
                    value,
                    to_language=to_language,
                    from_language=from_language,
                    update_session_after_seconds=10,
                    translator=ALTERNATIVE_TRANSLATOR,
                )
                return translated_text  # Als de vertaling succesvol is, geef het resultaat terug
            except Exception as e:
                attempt += 1
                logger.warning(f"Fout opgetreden vertalen van tekst '{value}' bij poging {attempt}: {e}")
                if attempt < max_retries:
                    logger.warning(f"Wacht {sleep_between_retries} seconden voor nieuwe poging om te vertalen...")
                    time.sleep(sleep_between_retries)
                else:
                    logger.warning(
                        f"Laatste herhaling na fout bij vertalen mislukt met fout {e}. Vertalen mislukt, originele"
                        " tekst wordt gehanfhaafd..."
                    )
                    return value
