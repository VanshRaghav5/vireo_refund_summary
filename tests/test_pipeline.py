"""Invariants that must hold on the supplied pack. Run: pytest -q"""
import sys; sys.path.insert(0, ".")
from pathlib import Path
import numpy as np, pytest
from vireo.pipeline import run_all, DEFAULT_CODE

@pytest.fixture(scope="module")
def R():
    return run_all(Path(__file__).parent.parent / "data")

def test_no_duplicate_ticket_ids(R):
    assert not R["tickets"].ticket_id.duplicated().any()

def test_legacy_unit_factor_is_exactly_100_on_every_duplicated_pair(R):
    a = R["audit"]
    assert a["pairs_checked_for_unit"] > 0 and a["pairs_checked_for_unit"] == a["pairs_exactly_x100"]

def test_duplicate_pairs_identical_except_money(R):
    assert R["audit"]["pair_fields_that_differ_besides_money"] == []

def test_bridge_adds_up(R):
    a = R["audit"]
    legacy_over = a["legacy_raw_refund_kept"] - a["legacy_raw_refund_kept"] / 100
    assert a["raw_refund_sum"] - a["raw_refund_in_removed_dups"] - legacy_over == pytest.approx(a["corrected_refund_sum"])

def test_no_refund_exceeds_retail_price_times_qty_sanity(R):
    t = R["tickets"]; r = t[t.refund_inr.notna() & t.order_value_inr.notna()]
    assert (r.refund_inr <= r.order_value_inr + 1e-6).all()   # a single ticket never refunds more than its order

def test_every_cut_of_the_data_reconciles_to_the_same_total(R):
    t, s = R["tickets"], R["summaries"]
    total = t.refund_inr.sum()
    assert s["monthly_by_reason_final"].to_numpy().sum() == pytest.approx(total)
    assert s["monthly_by_reason_filed"].to_numpy().sum() == pytest.approx(total)
    assert s["monthly_by_agent"].to_numpy().sum() == pytest.approx(total)
    assert s["agents"].refund_inr.sum() == pytest.approx(total)
    assert s["monthly_agent_reason"].refund_inr.sum() == pytest.approx(total)

def test_recoding_never_touches_amounts_or_deliberate_codes(R):
    t = R["tickets"]; r = t[t.refund_inr.notna()]
    deliberate = r[r.reason_filed != DEFAULT_CODE]
    assert (deliberate.reason_source == "agent code").all()
    assert r.reason_final.notna().all()

def test_all_tickets_have_an_agent(R):
    assert R["audit"]["agents_unmatched_tickets"] == 0

def test_cv_accuracy_floor(R):
    assert R["recode_qa"]["cv_accuracy"] > 0.95

def test_exceptions_include_all_flagged_rows(R):
    t = R["tickets"]; flagged = t[t.refund_inr.notna() & (t.replacement_issued == "Y")].ticket_id
    assert set(flagged) <= set(R["exceptions"].ticket_id)
