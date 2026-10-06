import os, glob
from pathlib import Path
import pandas as pd
import streamlit as st
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

st.set_page_config(page_title="Vireo Audio — Refund Review", layout="wide")
st.title("Vireo Audio — Refund Review")
st.caption("Deterministic financial reconciliation + local AI-assisted reason-code review")

DATA_DIR = Path(os.getenv("VIREO_DATA_DIR", Path(__file__).parent / "data"))

def pick(pattern):
    matches = list(DATA_DIR.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"Missing {pattern} in {DATA_DIR}")
    return matches[0]

@st.cache_data
def load_data():
    tickets = pd.read_csv(pick("*tickets.csv"))
    agents = pd.read_csv(pick("*agents.csv"))
    tickets["created_at"] = pd.to_datetime(tickets["created_at"])
    tickets["first_response_at"] = pd.to_datetime(tickets["first_response_at"])
    tickets["resolved_at"] = pd.to_datetime(tickets["resolved_at"])
    tickets["month"] = tickets["created_at"].dt.to_period("M").astype(str)
    tickets["quarter"] = tickets["created_at"].dt.to_period("Q").astype(str)

    # Freshdesk stored monetary values in its native unit. The pack's notes
    # and values show that the legacy export is 100x the rupee amount.
    tickets["refund_corrected"] = tickets["refund_amount_inr"].where(
        tickets["source_system"].ne("legacy_fd"),
        tickets["refund_amount_inr"] / 100
    )

    # Migration re-imports can appear under both systems. Prefer current
    # helpdesk row when the same ticket_id exists.
    tickets["source_preference"] = tickets["source_system"].eq("helpdesk").astype(int)
    ded = (tickets.sort_values(["ticket_id","source_preference"], ascending=[True,False])
           .drop_duplicates("ticket_id", keep="first").copy())
    ded["both_refund_replacement"] = (
        ded["refund_corrected"].notna() & ded["replacement_issued"].eq("Y")
    )
    ded = ded.merge(
        agents[["agent_id","name","team","tier"]].drop_duplicates("agent_id"),
        on="agent_id", how="left"
    )
    return tickets, ded

tickets, df = load_data()

st.sidebar.header("Filters")
months = sorted(df["month"].dropna().unique())
month_sel = st.sidebar.multiselect("Month", months, default=months)
teams = sorted(df["team"].dropna().unique())
team_sel = st.sidebar.multiselect("Team", teams, default=teams)

view = df[df["month"].isin(month_sel) & df["team"].isin(team_sel)].copy()
refunds = view[view["refund_corrected"].notna()].copy()

raw_total = tickets["refund_amount_inr"].sum()
corrected_total = df["refund_corrected"].sum()
dup_count = len(tickets) - len(df)
legacy_raw = tickets.loc[tickets["source_system"].eq("legacy_fd"), "refund_amount_inr"].sum()
exceptions = view[view["both_refund_replacement"]]

c1,c2,c3,c4 = st.columns(4)
c1.metric("Corrected refunds", f"₹{refunds['refund_corrected'].sum():,.0f}")
c2.metric("Refund tickets", f"{len(refunds):,}")
c3.metric("Refund + replacement", f"{len(exceptions):,}")
c4.metric("Exception rate", f"{(len(exceptions)/len(refunds) if len(refunds) else 0):.1%}")

st.subheader("1. Monthly refunds by reason")
monthly = (refunds.groupby(["month","refund_reason_code"])["refund_corrected"]
           .sum().reset_index().pivot(index="month", columns="refund_reason_code", values="refund_corrected").fillna(0))
st.line_chart(monthly)

st.subheader("2. Board-pack tables")
tab1,tab2,tab3 = st.tabs(["By reason","By agent","Policy exceptions"])

with tab1:
    reason=(refunds.groupby("refund_reason_code")
            .agg(refund_tickets=("ticket_id","count"), refund_inr=("refund_corrected","sum"),
                 avg_refund_inr=("refund_corrected","mean"))
            .reset_index().sort_values("refund_inr",ascending=False))
    reason["share_of_value"]=reason["refund_inr"]/reason["refund_inr"].sum()
    st.dataframe(reason, use_container_width=True)

with tab2:
    agent=(refunds.groupby(["agent_id","name","team","tier"])
           .agg(refund_tickets=("ticket_id","count"), refund_inr=("refund_corrected","sum"),
                avg_refund_inr=("refund_corrected","mean"),
                double_refund_replacement=("both_refund_replacement","sum"))
           .reset_index().sort_values("refund_inr",ascending=False))
    st.dataframe(agent, use_container_width=True)
    st.caption("Do not compare Tier 2 with Tier 1 on volume; the policy explicitly says Tier 2 is multi-touch and not a volume metric.")

with tab3:
    cols=["ticket_id","created_at","agent_id","name","team","refund_corrected",
          "refund_reason_code","replacement_issued","order_id","product_sku","agent_notes"]
    st.dataframe(exceptions[cols].sort_values("refund_corrected",ascending=False), use_container_width=True)

st.subheader("3. Reconciliation / data-quality proof")
proof = pd.DataFrame({
    "Check":[
        "Raw exported refund total",
        "Legacy raw subtotal",
        "Corrected + de-duplicated total",
        "Migration duplicate rows removed",
        "Refund + replacement cases"
    ],
    "Value":[
        raw_total, legacy_raw, corrected_total, dup_count, len(df[df["both_refund_replacement"]])
    ]
})
st.dataframe(proof, hide_index=True, use_container_width=True)
st.info("The financial source of truth is the deterministic reconciliation above. The AI component is a reviewer, not the calculator.")

st.subheader("4. Local AI reviewer")
st.write("A TF-IDF + logistic-regression classifier is trained on the labeled refund tickets and evaluated on a held-out 25% split. It is intentionally advisory.")
@st.cache_resource
def train_ai():
    r=df[df["refund_reason_code"].notna()].copy()
    r["text"]=(r["customer_message"].fillna("")+" "+r["agent_notes"].fillna("")).str.lower()
    Xtr,Xte,ytr,yte=train_test_split(r["text"],r["refund_reason_code"],test_size=.25,random_state=42,stratify=r["refund_reason_code"])
    m=Pipeline([
        ("tfidf",TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=30000,sublinear_tf=True)),
        ("clf",LogisticRegression(max_iter=1000,class_weight="balanced"))
    ])
    m.fit(Xtr,ytr)
    acc=accuracy_score(yte,m.predict(Xte))
    return m,acc
model,acc=train_ai()
st.metric("Held-out reason-code accuracy", f"{acc:.1%}")
st.caption("Because the classifier is only ~54% accurate, it must not overwrite the agent's code automatically. Its useful role is to surface tickets for human review, especially when the predicted reason disagrees with the dropdown code.")

text=st.text_area("Review a ticket's text", height=120, placeholder="Paste customer message + closing note here")
if text.strip():
    probs=model.predict_proba([text.lower()])[0]
    classes=model.classes_
    order=probs.argsort()[::-1][:3]
    st.write([(classes[i], f"{probs[i]:.1%}") for i in order])

st.subheader("How to use this for the board")
st.markdown("""
- Use **By reason** for the monthly board-pack summary.
- Use **By agent** to identify high-dollar or high-exception cases, but control for role/volume.
- Use **Policy exceptions** as the first operational action list.
- Keep the reconciliation logic deterministic; never let the AI model change rupee totals.
""")
