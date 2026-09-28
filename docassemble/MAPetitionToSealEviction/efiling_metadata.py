"""Validate optional EFSP metadata without treating missing data as a case decision."""

from collections.abc import Mapping
import logging

__all__ = ["case_labels", "sealing_case_status", "waiver_payment_id"]


def _name(data):
    value = data.get("name") if isinstance(data, Mapping) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def case_labels(proxy, court_id, case_type, category):
    """Return validated names (None when unavailable); never classify raw codes."""
    response = proxy.get_case_type(court_id, case_type)
    type_name = _name(response.data) if response is not None and response.is_ok() else None
    categories = proxy.get_case_categories(court_id, fileable_only=False, timing=None)
    category_name = None
    if categories is not None and categories.is_ok() and isinstance(categories.data, list):
        category_name = next(
            (_name(item) for item in categories.data
             if isinstance(item, Mapping) and str(item.get("code")) == str(category)),
            None,
        )
    if type_name is None or category_name is None:
        logging.getLogger(__name__).warning(
            "efiling.case_labels court=%s type=%s status=%s payload=%s "
            "category_status=%s category_payload=%s request=%s",
            court_id, case_type,
            response.response_code if response is not None else None,
            type(response.data).__name__ if response is not None else "NoneType",
            categories.response_code if categories is not None else None,
            type(categories.data).__name__ if categories is not None else "NoneType",
            getattr(response, "req_id", None),
        )
    return type_name, category_name


def sealing_case_status(type_name, category_name):
    """Return True/False for known eligibility, None for insufficient evidence."""
    if category_name and "summary process" in category_name.lower():
        return True
    if type_name and any(term in type_name.lower() for term in ("civil", "restraining order")):
        return True
    if type_name is None or category_name is None:
        return None
    return False


def waiver_payment_id(config):
    """Return a configured payment ID, or None; do not invent a usable ID."""
    waivers = config.get("global waivers") if isinstance(config, Mapping) else None
    value = waivers.get("massachusetts") if isinstance(waivers, Mapping) else None
    return value.strip() if isinstance(value, str) and value.strip() else None
