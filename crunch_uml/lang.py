import logging
import time

import translators as ts  # type: ignore

logger = logging.getLogger()
ALTERNATIVE_TRANSLATOR = "google"  # Alternatieve vertaalmachine


def translate(value, to_language, from_language, max_retries=3, sleep_between_retries=60):
    """
    Probeert een vertaling uit te voeren en bij een fout probeert het opnieuw, met een maximum van 3 pogingen.
    Tussen de pogingen wordt 1 minuut gewacht.
    """
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
                    f"Fout opgetreden bij vertalen van tekst '{value}', probeer alternatieve vertaalmachine {ALTERNATIVE_TRANSLATOR}..."
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
                        f"Laatste herhaling na fout bij vertalen mislukt met fout {e}. Vertalen mislukt, originele tekst wordt gehanfhaafd..."
                    )
                    return value
