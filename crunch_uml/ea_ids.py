"""Identifier rules shared by the ``qea`` and ``eaxmi`` parsers.

Both parsers must yield the same primary key for the same model element,
whatever the source format. Three EA quirks make that non-trivial:

* **GUID notation.** A QEA stores ``{XXXXXXXX-XXXX-...}``; the XMI export
  writes ``EAID_XXXXXXXX_XXXX_...`` (``EAPK_`` for packages). Some models
  carry a *doubled* brace pair, ``{{...}}``, which the XMI export turns into
  ``EAID_{...}``. :func:`guid_to_ea_id` and :func:`normalize_ea_id` map every
  variant onto the brace-less ``EAID_``/``EAPK_`` form.
* **Missing GUIDs.** Some ``t_attribute`` rows have ``ea_guid`` NULL; EA
  exports those members with ``xmi:id=""``. Storing the empty string as a
  primary key silently collapses all of them into one row. Instead both
  parsers mint the same deterministic id with :class:`SyntheticIdMinter`:
  ``EAID_syn_`` + ``sha1(owner_id|name|dup_index)``. The QEA row number is
  deliberately NOT part of it: it differs from the XMI ``ea_localid`` for the
  same attribute, so it cannot give cross-format identity.
* **Placeholders.** Classes the XMI parser invents for dangling association
  ends get a hash of their context (:func:`placeholder_class_id`) instead of
  a random uuid, so two parses of the same file give identical rows.
"""

import hashlib
import logging

logger = logging.getLogger()

SYNTHETIC_ID_PREFIX = "EAID_syn_"
PLACEHOLDER_ID_PREFIX = "EAID_orphan_"
_ID_PREFIXES = ("EAID_", "EAPK_")


def guid_to_ea_id(guid, prefix="EAID"):
    """Convert an EA GUID (``{X-Y-...}`` or ``{{X-Y-...}}``) to ``<prefix>_X_Y_...``.

    Returns None for a missing/empty GUID so callers can mint a synthetic id.
    """
    if not guid:
        return None
    clean = guid.strip().strip("{}").replace("-", "_")
    if not clean:
        return None
    return f"{prefix}_{clean}"


def normalize_ea_id(value):
    """Normalize an XMI id such as ``EAID_{X_Y}`` or ``EAID_{{X_Y}}`` to ``EAID_X_Y``.

    Values that are not braced EA ids are returned unchanged.
    """
    if isinstance(value, str) and value[:5] in _ID_PREFIXES and value[5:6] == "{":
        return value[:5] + value[5:].strip("{}")
    return value


def synthetic_id(owner_id, name, dup_index):
    """Deterministic id for an element without a source GUID.

    ``dup_index`` is the 0-based position of this (owner, name) pair among the
    owner's other GUID-less elements with the same name, in source order.
    """
    key = f"{owner_id or ''}|{name or ''}|{dup_index}"
    return SYNTHETIC_ID_PREFIX + hashlib.sha1(key.encode("utf-8")).hexdigest()


def placeholder_class_id(association_id, member_end_id):
    """Deterministic id for a placeholder class of a dangling association end."""
    key = f"{association_id or ''}|{member_end_id or ''}"
    return PLACEHOLDER_ID_PREFIX + hashlib.sha1(key.encode("utf-8")).hexdigest()


class SyntheticIdMinter:
    """Mints :func:`synthetic_id` values, tracking the duplicate index per owner
    and name. Each minted id is logged at DEBUG; the parsers log one WARNING per
    import with :attr:`count`, so a model with hundreds of GUID-less members
    (InkomenMIM: 827) does not bury every other warning."""

    def __init__(self, source_label):
        self._source_label = source_label
        self._seen = {}
        self.count = 0

    def mint(self, owner_id, name, kind="element"):
        key = (owner_id or "", name or "")
        dup_index = self._seen.get(key, 0)
        self._seen[key] = dup_index + 1
        new_id = synthetic_id(owner_id, name, dup_index)
        self.count += 1
        logger.debug(
            f"{self._source_label}: {kind} '{name}' of owner {owner_id} has no source id; using synthetic id {new_id}"
        )
        return new_id
