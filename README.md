# Vireo Audio — Support Tickets (Set C)

## Quick start

1. Install Python 3.10+.
2. Open this folder in a terminal.
3. Run:
   - Windows: `run_windows.bat`
   - Other systems: `python -m pip install -r requirements.txt` then `streamlit run app.py`
4. The app reads the files in `data/`.

No API key or internet connection is required.

## What the tool does

- Corrects legacy Freshdesk refund amounts by dividing the legacy monetary export by 100.
- Removes migration re-import duplicates by ticket ID, preferring the current helpdesk row where both exist.
- Produces monthly refunds by reason and refunds by agent.
- Flags tickets where both refund and replacement were issued.
- Trains a local TF-IDF + logistic-regression reviewer to suggest reason codes. It is advisory only.
- Keeps all financial calculations deterministic.

## Important assumptions

1. The legacy unit correction is supported by the email thread, policy and ticket notes; it is not an arbitrary currency conversion.
2. Duplicate reconciliation prefers the current helpdesk record when the same ticket ID exists in both source systems.
3. Tier 2 agents are not compared with Tier 1 on ticket volume, per policy.
4. The savings estimate assumes prevented duplicate refunds are fully recoverable. Treat this as a planning estimate, not booked savings.

## Files

- `app.py` — working Streamlit tool
- `outputs/vireo_refund_board_pack.xlsx` — board-ready tables
- `memo_to_arjun.md` — one-page business memo
- `recording_script.md` — <=3 minute recording plan
- `submission-form-draft.md` — draft only because the official submission form was not included
