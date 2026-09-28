# do not pre-load

"""Exercise the shipped YAML code blocks with controlled EFSP responses."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "docassemble/MAPetitionToSealEviction"
spec = importlib.util.spec_from_file_location("metadata", PKG / "efiling_policy.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
BLOCKS = list(
    yaml.safe_load_all((PKG / "data/questions/support_efiling.yml").read_text())
)


def block(block_id):
    return next(b["code"] for b in BLOCKS if b and b.get("id") == block_id)


@pytest.mark.parametrize(
    "type_name,category_name,expected",
    [
        (None, "Summary Process", True),
        ("Civil", None, True),
        ("Restraining Order", None, True),
        (None, "Civil", None),
        ("No Cause", None, None),
        ("Other", "Other", False),
        (None, None, None),
    ],
)
def test_classification(type_name, category_name, expected):
    assert m.sealing_case_status(type_name, category_name) is expected


@pytest.mark.parametrize(
    "config",
    [
        None,
        [],
        {},
        {"global waivers": None},
        {"global waivers": []},
        {"global waivers": {}},
        {"global waivers": {"massachusetts": None}},
        {"global waivers": {"massachusetts": ""}},
        {"global waivers": {"massachusetts": "  "}},
        {"global waivers": {"massachusetts": 123}},
    ],
)
def test_unavailable_waiver(config):
    assert m.waiver_payment_id(config) is None


def test_waiver_and_submission_guard():
    assert (
        m.waiver_payment_id({"global waivers": {"massachusetts": " account "}})
        == "account"
    )

    class Screen(Exception):
        pass

    def force_ask(screen):
        raise Screen(screen)

    scope = dict(
        waiver_payment_id=m.waiver_payment_id,
        get_config=lambda key: None,
        force_ask=force_ask,
    )
    with pytest.raises(Screen, match="efiling_payment_unavailable"):
        exec(block("validated waiver payment account"), scope)
    assert "tyler_payment_id" not in scope


@pytest.mark.parametrize(
    "name,expected",
    [
        (None, None),
        ("No Cause", "eviction_reason_nofault"),
        ("Cause", "eviction_reason_fault"),
        ("Non-Payment", "eviction_reason_nonpayment"),
        ("Foreclosure", "eviction_reason_foreclosure"),
    ],
)
def test_prediction(name, expected):
    scope = dict(
        can_check_efile=True,
        case_search=SimpleNamespace(found_case=SimpleNamespace(case_type_name=name)),
        trial_court=SimpleNamespace(department="Housing Court"),
    )
    exec(block("predict eviction reason from verified metadata"), scope)
    assert scope["predicted_eviction_reason"] == expected


@pytest.mark.parametrize(
    "department,type_name,category_name,payment,expected,reason",
    [
        ("Housing Court", None, None, "id", False, "metadata"),
        ("Housing Court", None, "Summary Process", "id", True, None),
        ("District Court", "Civil", None, "id", True, None),
        ("Boston Municipal Court", "Restraining Order", None, "id", True, None),
        ("Superior Court", "Civil", "Summary Process", "id", False, None),
        ("Housing Court", "No Cause", "Summary Process", None, False, "payment"),
        ("Housing Court", "Other", "Other", "id", False, None),
    ],
)
def test_actual_eligibility_block(
    department, type_name, category_name, payment, expected, reason
):
    case = SimpleNamespace(case_type_name=type_name, case_category_name=category_name)
    scope = dict(
        can_check_efile=True,
        showifdef=lambda key: case,
        trial_court=SimpleNamespace(department=department),
        case_search=SimpleNamespace(found_case=case),
        sealing_case_status=m.sealing_case_status,
        waiver_payment_id=m.waiver_payment_id,
        get_config=lambda key: {"global waivers": {"massachusetts": payment}},
    )
    exec(block("determine efiling availability"), scope)
    assert scope["petition_is_efileable"] is expected
    assert scope["efiling_unavailable_reason"] == reason


@pytest.mark.parametrize(
    "can_check,found", [(False, False), (False, True), (True, False)]
)
def test_no_case_or_declined_efiling(can_check, found):
    scope = dict(can_check_efile=can_check, showifdef=lambda key: found)
    exec(block("determine efiling availability"), scope)
    assert scope["petition_is_efileable"] is False


def test_submission_does_not_run_without_eligibility():
    class Screen(Exception):
        pass

    def force_ask(screen):
        raise Screen(screen)

    with pytest.raises(Screen, match="warn_sorry_not_efileable"):
        exec(block("efile"), dict(petition_is_efileable=False, force_ask=force_ask))


def test_refresh_runs_once_per_request_for_multiple_results():
    refresh = next(b["code"] for b in BLOCKS if b and b.get("initial"))
    search = SimpleNamespace()
    clear = Mock()
    scope = dict(case_search=search, clear_case_labels=clear)
    scope["defined"] = lambda name: name in scope
    exec(refresh, scope)
    exec(refresh, scope)
    clear.assert_called_once_with(search)
    del scope["efiling_metadata_refreshed"]
    exec(refresh, scope)
    assert clear.call_count == 2
