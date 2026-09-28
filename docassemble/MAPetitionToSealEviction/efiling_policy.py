"""Massachusetts sealing eligibility and waiver-account policy."""

from collections.abc import Mapping

__all__ = ["sealing_case_status", "waiver_payment_id"]


def sealing_case_status(type_name, category_name):
    """Return True/False for known eligibility, None for insufficient evidence."""
    if category_name and "summary process" in category_name.lower():
        return True
    if type_name and any(
        term in type_name.lower() for term in ("civil", "restraining order")
    ):
        return True
    if type_name is None or category_name is None:
        return None
    return False


def waiver_payment_id(config):
    """Return a configured payment ID, or None; do not invent a usable ID."""
    waivers = config.get("global waivers") if isinstance(config, Mapping) else None
    value = waivers.get("massachusetts") if isinstance(waivers, Mapping) else None
    return value.strip() if isinstance(value, str) and value.strip() else None
