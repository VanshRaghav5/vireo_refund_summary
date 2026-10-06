"""Vireo refund review pipeline.

Design rule: every rupee figure is computed deterministically from the data.
The only learned component (reason re-coding) changes the *label* of a refund, never the amount,
and every re-coded row is marked so it can be audited.
"""
from __future__ import annotations
import re, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

LEGACY_FACTOR = 100          # Freshdesk stored money x100 (verified on every duplicated pair, see audit)
REPLACEMENT_LOGISTICS = 340  # policy s5: reverse pickup + forward shipping
DEFAULT_CODE = "GW-OTHER"    # first item in the agents' dropdown (email thread, Sameer)

# ------------------------------------------------------------------ loading
def _pick(data_dir: Path, pattern: str) -> Path:
    hits = sorted(p for p in data_dir.iterdir() if re.search(pattern, p.name, re.I))
    if not hits:
        raise FileNotFoundError(f"No file matching /{pattern}/ in {data_dir}")
    return hits[0]

def load(data_dir) -> dict[str, pd.DataFrame]:
    d = Path(data_dir)
    out = {
        "tickets": pd.read_csv(_pick(d, r"tickets\.csv$")),
        "agents": pd.read_csv(_pick(d, r"agents\.csv$")),
        "orders": pd.read_csv(_pick(d, r"orders\.csv$")),
        "products": pd.read_csv(_pick(d, r"products\.csv$")),
    }
    return out

# ------------------------------------------------------------------ cleaning
def clean(raw: dict) -> tuple[pd.DataFrame, dict]:
    """Return one row per ticket with corrected rupee amounts, plus an audit dict."""
    t = raw["tickets"].copy()
    audit: dict = {"raw_rows": len(t), "raw_refund_sum": float(t.refund_amount_inr.sum()),
                   "raw_refund_rows": int(t.refund_amount_inr.notna().sum())}

    # 1. duplicates: same ticket_id under both source systems (migration re-import)
    dup_ids = t.loc[t.ticket_id.duplicated(keep=False), "ticket_id"].unique()
    pairs = t[t.ticket_id.isin(dup_ids)]
    h = pairs[pairs.source_system == "helpdesk"].set_index("ticket_id")
    l = pairs[pairs.source_system == "legacy_fd"].set_index("ticket_id").reindex(h.index)
    both_money = h.refund_amount_inr.notna() & l.refund_amount_inr.notna()
    ratio = (l.loc[both_money, "refund_amount_inr"] / h.loc[both_money, "refund_amount_inr"])
    audit.update(dup_ticket_ids=len(dup_ids), dup_rows_removed=len(pairs) - len(dup_ids),
                 pairs_checked_for_unit=int(both_money.sum()),
                 pairs_exactly_x100=int((ratio.round(6) == LEGACY_FACTOR).sum()))
    # any other field differing inside a pair?
    diff_cols = []
    for c in t.columns:
        if c in ("ticket_id", "source_system", "refund_amount_inr"):
            continue
        ne = ~((h[c] == l[c]) | (h[c].isna() & l[c].isna()))
        if ne.any():
            diff_cols.append(c)
    audit["pair_fields_that_differ_besides_money"] = diff_cols

    t["_pref"] = (t.source_system == "helpdesk").astype(int)
    removed = t[t.ticket_id.duplicated(keep=False) & (t.source_system == "legacy_fd")]
    audit["raw_refund_in_removed_dups"] = float(removed.refund_amount_inr.sum())
    t = (t.sort_values(["ticket_id", "_pref"], ascending=[True, False])
           .drop_duplicates("ticket_id", keep="first").drop(columns="_pref"))

    # 2. unit correction on the legacy rows that remain
    leg = t.source_system == "legacy_fd"
    audit["legacy_rows_kept"] = int(leg.sum())
    audit["legacy_raw_refund_kept"] = float(t.loc[leg, "refund_amount_inr"].sum())
    t["refund_inr"] = np.where(leg, t.refund_amount_inr / LEGACY_FACTOR, t.refund_amount_inr)
    audit["corrected_refund_sum"] = float(t.refund_inr.sum())
    audit["refund_tickets"] = int(t.refund_inr.notna().sum())

    # 3. time keys. Month = ticket creation month (no refund date exists in the export).
    t["created"] = pd.to_datetime(t.created_at)
    t["month"] = t.created.dt.to_period("M").astype(str)
    t["quarter"] = t.created.dt.to_period("Q").astype(str)

    # 4. attach roster (one row per agent in this pack; handle several rows by date anyway)
    ag = raw["agents"].copy()
    ag["from_date"] = pd.to_datetime(ag.from_date); ag["to_date"] = pd.to_datetime(ag.to_date)
    t = t.reset_index(drop=True)
    m = t[["ticket_id", "agent_id", "created"]].merge(ag, on="agent_id", how="left")
    ok = (m.created >= m.from_date) & (m.to_date.isna() | (m.created <= m.to_date))
    m = m[ok | m.from_date.isna()].drop_duplicates("ticket_id")
    audit["agents_unmatched_tickets"] = int(t.agent_id.isna().sum() + (~t.ticket_id.isin(m.ticket_id)).sum())
    t = t.merge(m[["ticket_id", "name", "site", "team", "shift", "tier"]]
                .rename(columns={"name": "agent_name", "team": "agent_team"}), on="ticket_id", how="left")

    # 5. order + product
    o = raw["orders"].drop_duplicates("order_id")[["order_id", "order_value_inr", "order_date"]]
    t = t.merge(o, on="order_id", how="left")
    p = raw["products"][["sku", "product_name", "unit_cost_inr", "retail_price_inr"]]
    t = t.merge(p, left_on="product_sku", right_on="sku", how="left").drop(columns="sku")
    return t, audit

# ------------------------------------------------------------------ re-coding
GOODWILL_CUES = re.compile(r"goodwill|one[- ]time gesture|keep (him|her|them) happy|threatened|"
                           r"very upset|escalation avoided|to keep cx|as a gesture", re.I)
HW = "HW-FAULT"   # DOA-REPL + WTY-BUYBACK merged: the data cannot separate them (see decision.md)
MERGE = {"DOA-REPL": HW, "WTY-BUYBACK": HW}

_STRIP = None
def _text(df, strip=False):
    s = (df.customer_message.fillna("") + " || " + df.agent_notes.fillna("")).str.lower()
    if strip:
        s = s.str.replace(r"[^.|\n]*(" + _BOTH_PHRASES.pattern + r")[^.|\n]*", " ", regex=True, case=False)
        s = s.str.replace(r"[^.|\n]*(new unit|fresh unit|fresh pair|new set|new piece|re-?shipped|reshipped)[^.|\n]*", " ", regex=True, case=False) if False else s
    return s

def _model():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline, make_union
    return make_pipeline(
        make_union(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
                   TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True)),
        LogisticRegression(max_iter=2000, C=5))

def recode(t: pd.DataFrame, min_conf: float = 0.60, seed: int = 0) -> tuple[pd.DataFrame, dict]:
    """Add `reason_final` + `reason_source`.
    Trust deliberate codes (anything other than the dropdown default). For GW-OTHER rows decide
    from the free text: genuine-goodwill language -> GOODWILL, else classifier trained ONLY on the
    deliberate codes; below `min_conf` -> UNCLEAR."""
    from sklearn.model_selection import cross_val_predict, StratifiedKFold
    from sklearn.metrics import accuracy_score
    t = t.copy()
    r = t.refund_inr.notna()
    t["reason_filed"] = t.refund_reason_code
    t["reason_final"] = pd.NA; t["reason_source"] = pd.NA
    lab = r & (t.refund_reason_code != DEFAULT_CODE)
    unl = r & (t.refund_reason_code == DEFAULT_CODE)
    t.loc[lab, "reason_final"] = t.loc[lab, "refund_reason_code"].replace(MERGE)
    t.loc[lab, "reason_source"] = "agent code"

    X, y = _text(t[lab]), t.loc[lab, "refund_reason_code"].replace(MERGE)
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)
    pred = cross_val_predict(_model(), X, y, cv=cv)
    proba = cross_val_predict(_model(), X, y, cv=cv, method="predict_proba")
    conf = proba.max(1)
    qa = {"labelled_rows": int(lab.sum()), "cv_accuracy": float(accuracy_score(y, pred)),
          "cv_accuracy_per_class": {c: float((pred[y.values == c] == c).mean()) for c in sorted(y.unique())},
          "cv_accuracy_at_conf": float(accuracy_score(y[conf >= min_conf], pred[conf >= min_conf])),
          "cv_coverage_at_conf": float((conf >= min_conf).mean()), "min_conf": min_conf,
          "cv_accuracy_unmerged": None}
    m = _model().fit(X, y)
    U = t[unl]
    tx = _text(U)
    pr = m.predict_proba(tx); lbl = m.classes_[pr.argmax(1)]; cf = pr.max(1)
    gw = (tx.str.contains(GOODWILL_CUES) | (tx.str.contains(_BOTH_PHRASES) & ~tx.str.contains(_NEGATED))).values
    final = np.where(gw, "GOODWILL", np.where(cf >= min_conf, lbl, "UNCLEAR"))
    src = np.where(gw, "text: goodwill language", np.where(cf >= min_conf, "text: model", "text: low confidence"))
    t.loc[unl, "reason_final"] = final; t.loc[unl, "reason_source"] = src
    t.loc[unl, "reason_conf"] = cf
    qa["default_code_rows"] = int(unl.sum())
    qa["default_rows_goodwill_language"] = int(gw.sum())
    qa["default_rows_recoded_by_model"] = int((~gw & (cf >= min_conf)).sum())
    qa["default_rows_unclear"] = int((~gw & (cf < min_conf)).sum())
    return t, qa

# ------------------------------------------------------------------ policy exceptions
_REF = r"refund|rfnd|refunded|amount (back|returned)|credited full|reversed the payment|money back"
_REP = r"replacement|rplc|new unit|new one|new set|fresh unit|dispatched a new|replacement case|new pair"
_BOTH_PHRASES = re.compile(r"refund \+ (rplc|replacement)|rfnd \+ (rplc|replacement)|both (refund|rfnd)|and also raised (replacement|rplc)|also raised (replacement|rplc)|"
                           r"processed f(r|ull refund) (and|&) raised rma for new set|money back to source and a fresh pair|"
                           r"sent a new unit (and|&) released the money|refund \+ replacement both|rfnd \+ replacement both|"
                           r"new unit also|also sending a new|refund done and new unit|one[- ]time gesture|"
                           r"and replacement dispatched|& rplc dispatched|& also raised|fresh unit shipped|"
                           r"reversed the payment (&|and) dispatched a new|dispatched a new one under rma", re.I)
GIVEAWAY_TEXT = _BOTH_PHRASES   # boilerplate sentences that carry no information about the *cause* of the refund
_NEGATED = re.compile(r"offered|opted|prefer|declin|did not want|rejected|not applicable|out of stock|"
                      r"not eligible|refused", re.I)

def exceptions(t: pd.DataFrame) -> pd.DataFrame:
    """Refunds that also gave the customer a unit (policy s5: never both)."""
    r = t[t.refund_inr.notna()].copy()
    r["flag_Y"] = r.replacement_issued.eq("Y")
    n = r.agent_notes.fillna("")
    r["note_evidence"] = n.str.contains(_BOTH_PHRASES) & ~n.str.contains(_NEGATED)
    r["double_dip"] = np.select([r.flag_Y, r.note_evidence], ["flag", "notes only"], "")
    e = r[r.double_dip != ""].copy()
    e["replacement_cost_inr"] = e.unit_cost_inr + REPLACEMENT_LOGISTICS      # policy s5
    e["leak_low_inr"] = e.replacement_cost_inr                               # refund stands, unit should not ship
    e["leak_high_inr"] = e.refund_inr                                        # unit stands, refund should not be paid
    return e

def over_refunded_orders(t: pd.DataFrame) -> pd.DataFrame:
    """Orders where refunds across tickets exceed the order value (order_id quoted only)."""
    r = t[t.refund_inr.notna() & t.order_id.notna()]
    g = r.groupby("order_id").agg(tickets=("ticket_id", "count"), refunded=("refund_inr", "sum"),
                                  order_value=("order_value_inr", "first"),
                                  ticket_ids=("ticket_id", lambda s: ", ".join(s)))
    g = g[(g.tickets > 1)]
    g["over_by"] = g.refunded - g.order_value
    return g[g.over_by > 0].sort_values("over_by", ascending=False)

# ------------------------------------------------------------------ summaries
def summaries(t: pd.DataFrame) -> dict[str, pd.DataFrame]:
    r = t[t.refund_inr.notna()]
    s = {}
    s["monthly_by_reason_filed"] = r.pivot_table(index="month", columns="reason_filed", values="refund_inr", aggfunc="sum", fill_value=0)
    s["monthly_by_reason_final"] = r.pivot_table(index="month", columns="reason_final", values="refund_inr", aggfunc="sum", fill_value=0)
    s["monthly_by_agent"] = r.pivot_table(index=["agent_id", "agent_name", "agent_team", "tier"], columns="month",
                                          values="refund_inr", aggfunc="sum", fill_value=0)
    s["monthly_agent_reason"] = (r.groupby(["month", "agent_id", "agent_name", "agent_team", "reason_final"])
                                 .agg(tickets=("ticket_id", "count"), refund_inr=("refund_inr", "sum")).reset_index())
    s["by_status"] = r.groupby(["quarter", "status"]).refund_inr.sum().unstack(fill_value=0)
    vol = t.groupby("quarter").agg(tickets=("ticket_id", "count"), refunds=("refund_inr", "count"),
                                   refund_inr=("refund_inr", "sum"), csat=("csat_score", "mean"))
    vol["refund_rate"] = vol.refunds / vol.tickets
    vol["refund_inr_per_ticket"] = vol.refund_inr / vol.tickets
    s["quarterly"] = vol
    ag = (r.groupby(["agent_id", "agent_name", "agent_team", "site", "shift", "tier"])
           .agg(refund_tickets=("ticket_id", "count"), refund_inr=("refund_inr", "sum"),
                avg_refund=("refund_inr", "mean"),
                filed_default_share=("reason_filed", lambda x: (x == DEFAULT_CODE).mean())).reset_index())
    tk = t.groupby("agent_id").size().rename("tickets_resolved")
    ag = ag.merge(tk, on="agent_id")
    ag["refund_per_100_tickets"] = ag.refund_tickets / ag.tickets_resolved * 100
    s["agents"] = ag.sort_values("refund_inr", ascending=False)
    return s

def run_all(data_dir):
    raw = load(data_dir)
    t, audit = clean(raw)
    t, qa = recode(t)
    ex = exceptions(t)
    oo = over_refunded_orders(t)
    s = summaries(t)
    return dict(tickets=t, audit=audit, recode_qa=qa, exceptions=ex, over_refunded=oo, summaries=s)
