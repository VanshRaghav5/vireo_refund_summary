# Vireo Audio - refund review (v2)

Monthly refunds by reason code and by agent, reconciled to one total, with the data problems that made the
raw export unusable fixed and documented. No API keys, no internet, no paid calls.

## Run it (clean machine)

Needs Python 3.10+.

    python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    python run.py                                            # ~15 s; writes ./outputs
    python -m pytest -q                                      # 10 invariant tests, all must pass
    streamlit run app.py                                     # optional dashboard

`data/` already holds the client pack (tickets, agents, orders, products, customers, policy, README, email thread).
To point at other files: `python run.py --data /path/to/folder --out /path/to/out` (file names are matched by suffix,
so the UUID prefixes in the export do not matter).

## What you get in `outputs/`

| File | Use |
|---|---|
| `vireo_refund_board_pack.xlsx` | The board-pack workbook. Sheet 1 is the bridge from the raw export to the reconciled total; sheets 3-5 are Month x Reason (re-coded and as-filed) and Month x Agent with live `=SUM` total rows. |
| `monthly_by_reason_final.csv`, `monthly_by_reason_as_filed.csv`, `monthly_by_agent.csv`, `monthly_agent_reason_long.csv` | The same tables as CSV. |
| `agents.csv` | One row per agent: refunds, rupees, refunds per 100 tickets, share filed as the dropdown default. |
| `refund_plus_unit_exceptions.csv` | Refunds where a unit also shipped (policy s5 forbids both), with replacement cost per policy. |
| `orders_refunded_more_than_value.csv` | Review list, not a leakage claim (see decision.md). |
| `quarterly.csv`, `headline.json`, `qa_report.md` | Volume/refund-rate/CSAT by quarter; every number quoted in the memo; reconciliation + model QA. |

## How it works (4 steps, all in `vireo/pipeline.py`)

1. **Clean** - drop the 638 re-imported duplicates (keep the helpdesk row); divide the remaining legacy Freshdesk refunds by 100
   (verified: legacy = exactly 100x helpdesk on all 125 duplicated pairs that carry money).
2. **Re-code reason** - 43% of refund value was filed as `GW-OTHER`, the first item in the agents' dropdown. For those rows only,
   the reason is taken from goodwill/giveaway language in the note, else from a text classifier trained **only on tickets where the agent
   chose a deliberate code**; low confidence -> `UNCLEAR`. Amounts are never touched.
3. **Exceptions** - refund + replacement (flag, or the agent's own note says a unit also shipped).
4. **Report** - every cut sums to the same total (enforced by tests).

## Known limits
See `decision.md` section "What is wrong with this".
