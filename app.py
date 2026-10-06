"""Optional dashboard:  streamlit run app.py   (the board pack comes from `python run.py`; this is for exploring)."""
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
from pathlib import Path
import pandas as pd, streamlit as st
from vireo.pipeline import run_all, DEFAULT_CODE
from run import headline

st.set_page_config(page_title="Vireo refund review", layout="wide")
DATA = Path(os.getenv("VIREO_DATA_DIR", Path(__file__).parent / "data"))

@st.cache_data(show_spinner="Reconciling and re-coding...")
def load():
    R = run_all(DATA); return R, headline(R)
R, h = load(); t = R["tickets"]; a = R["audit"]; s = R["summaries"]
r = t[t.refund_inr.notna()]

st.title("Vireo Audio - refund review")
st.caption("Money is deterministic. The only learned part re-labels the reason on tickets where the agent left the dropdown default.")
c = st.columns(4)
c[0].metric("Reconciled refunds (18m)", f"Rs {h['total_refund_inr']/1e5:,.2f} L")
c[1].metric("Raw export said", f"Rs {a['raw_refund_sum']/1e7:,.2f} cr")
c[2].metric("Refund + unit shipped", f"{h['double_dips_18m']} tickets", f"{h['dd_rate_last4']:.1%} of refunds, last 4 qtrs")
c[3].metric("Filed as GW-OTHER", f"{h['filed_default_share_value']:.0%} of value", f"true goodwill {h['true_goodwill_share_value']:.0%}", delta_color="off")

tab = st.tabs(["Reason (monthly)", "Agent (monthly)", "Why refunds rose", "Refund + unit", "How far to trust this"])
with tab[0]:
    which = st.radio("Reason column", ["Re-coded from text (recommended)", "As filed by agents"], horizontal=True)
    m = s["monthly_by_reason_final"] if which.startswith("Re") else s["monthly_by_reason_filed"]
    st.bar_chart(m); m2 = m.copy(); m2["TOTAL"] = m2.sum(1); st.dataframe(m2.style.format("{:,.0f}"), use_container_width=True)
with tab[1]:
    team = st.multiselect("Team", sorted(r.agent_team.dropna().unique()), default=sorted(r.agent_team.dropna().unique()))
    ag = s["agents"][s["agents"].agent_team.isin(team)]
    st.dataframe(ag, use_container_width=True, hide_index=True)
    st.caption("Tier 2 (Escalations & Warranty) is multi-touch by policy - do not rank it against Tier 1 on volume.")
with tab[2]:
    q = s["quarterly"]; st.dataframe(q.style.format({"refund_rate": "{:.1%}", "refund_inr": "{:,.0f}", "refund_inr_per_ticket": "{:,.0f}", "csat": "{:.2f}"}), use_container_width=True)
    st.line_chart(q[["tickets", "refunds"]])
    st.write("Refunds rose with ticket volume; the share of tickets ending in a refund is flat and CSAT did not rise.")
with tab[3]:
    e = R["exceptions"]
    st.write(f"{h['double_dips_flagged']} tickets carry the replacement flag; {h['double_dips_notes_only']} more have the flag blank but the agent's own note says a unit also went out.")
    st.dataframe(e[["ticket_id", "created_at", "agent_id", "agent_name", "agent_team", "product_sku", "refund_inr", "replacement_cost_inr", "double_dip", "agent_notes"]], use_container_width=True, hide_index=True)
with tab[4]:
    st.markdown(Path(__file__).with_name("outputs").joinpath("qa_report.md").read_text() if Path(__file__).with_name("outputs").joinpath("qa_report.md").exists() else "Run `python run.py` first.")
    x = st.text_area("Try a ticket's text (customer message + note)")
    if x.strip():
        from vireo.pipeline import _model, _text, MERGE
        lab = r[r.reason_filed != DEFAULT_CODE]
        m = _model().fit(_text(lab), lab.reason_filed.replace(MERGE))
        p = m.predict_proba([x.lower()])[0]
        st.write({k: f"{v:.0%}" for k, v in sorted(zip(m.classes_, p), key=lambda kv: -kv[1])[:3]})
