# Decision log - what I did, why, and what I changed from the first version

Starting point: your `vireo_refund_review.rar` (Streamlit app + memo + board pack). I re-derived every number from the raw
files instead of trusting the earlier outputs, kept what held up, and changed what did not.

## A. What held up in your original (kept)
| Item | Check I ran | Result |
|---|---|---|
| Legacy Freshdesk money is 100x | On the 125 duplicated pairs carrying money, legacy / helpdesk | exactly 100.000 on all 125 |
| Reconciled total Rs 67,09,932 (2,340 refund tickets) | Rebuilt independently | identical |
| Keep the helpdesk row when a ticket is in both systems | The pairs are identical in every field except money | safe either way once units are fixed |
| Do not rank Tier 2 against Tier 1 on volume | Policy s6 | kept |
| Money is deterministic; ML never changes rupees | design | kept, and now enforced by a test |

## B. What was wrong or weak in the original (changed)
| # | Problem | Evidence | Change |
|---|---|---|---|
| 1 | **GW-OTHER (43% of value) was treated as a deliberate management choice** ("CX told frontline to stop arguing"). | Email thread: GW-OTHER is simply the *first dropdown item*. Notes on those tickets say "double charge", "cancel before dispatch", "return QC passed". Agents' GW-OTHER share is 27-89%, similar across Billing/Returns/Chat. | Re-coded those 991 rows from text. Genuine goodwill is about 10% of value, not 43%. |
| 2 | The classifier was trained **on the agents' codes including GW-OTHER** (circular; 54% accuracy). | Same noisy label on both sides. | Train only on the 1,349 refunds where the agent chose a deliberate code. 5-fold CV accuracy 98.1%. |
| 3 | Refund+replacement counted only where `replacement_issued = Y` (166). | 153 more refund tickets have the flag blank while the agent's own note says a unit also shipped ("refund + rplc, cx escalation avoided", "new unit also going out tomorrow"). I read 30 of the first 118: all true. | 319 tickets (166 flagged + 153 note evidence). Negations ("offered, customer preferred refund", "rplc not applicable") excluded. |
| 4 | Leakage valued as **the full refund, 100% recoverable**. | Only one of the two things the customer got should have been given. | Range: low = replacement cost per policy (unit cost + Rs 340), high = the refund amount. Goal quoted on the low end. |
| 5 | No monthly x agent table, which was literally the ask. | Outputs had by-reason monthly and agent totals only. | Added Month x Agent and Month x Agent x Reason. |
| 6 | The "why did refunds go up" question was not answered. | | Quarterly view: tickets 1,053 -> 2,277 (peak 2,678), refund share of tickets flat at 18-22%, CSAT 3.54 -> 3.46. Refunds rose with volume. |
| 7 | Rs 12.80L vs helpdesk's "about Rs 11L" left unexplained. | Q2-26 refunds on `resolved` tickets alone = Rs 10.82L; closed/open/pending add Rs 1.98L. | Reported both. This is an inference that the helpdesk report counts resolved only; Sameer should confirm. |
| 8 | Recording script quoted 513 duplicates; the data has 638. | | Fixed; all numbers now read from `headline.json`. |
| 9 | Streamlit-only, no tests, `customers.csv` missing from `data/`, nothing proving totals tie. | | `python run.py` (no Streamlit needed), 10 pytest invariants, full pack in `data/`. |
| 10 | Agent table sorted by rupees only. | Returns Desk/Billing top the list by design. | Added refunds per 100 tickets, share filed as default code, and double-dip counts per agent. |

## C. Step-by-step decisions in the new pipeline
1. **Dedupe by ticket_id, keep helpdesk row.** Pairs are identical apart from money, so the choice does not move any number except the unit.
2. **Divide legacy by 100.** Confirmed on pairs (above). Remaining check: after the fix, legacy-only amounts have the same distribution as helpdesk (median Rs 2,249 vs 2,499) and never exceed the order value.
3. **Month = ticket creation month.** The export has no refund date. `resolved_at` is IST for the helpdesk but reconstructed from UTC for legacy rows, so using it would shift some tickets across month ends. Decision: use `created_at`, say so on the memo.
4. **Agent = `agent_id` (resolver), team/tier from roster.** Policy says use the id not the name. Roster has one row per agent here; the code also handles several rows by date.
5. **Reason re-coding.** Trust deliberate codes. For GW-OTHER rows: goodwill/giveaway wording -> `GOODWILL`; else classifier (word + character TF-IDF, logistic regression) with confidence >= 0.60; otherwise `UNCLEAR`. DOA-REPL and WTY-BUYBACK are merged into `HW-FAULT` because the data does not separate them (days-since-order overlaps and order dates are inconsistent - some tickets precede their order by up to 182 days).
6. **Show both columns.** Workbook has Month x Reason *as filed* and *re-coded*, so Finance can see exactly what moved.
7. **Refund + unit.** Flag OR note evidence. Replacement cost per policy s5.
8. **Goal chosen:** cut refund+unit double-dips from **14.0% of refund tickets (last four quarters) to 2%**. 262 cases in those four quarters; at the low replacement-cost basis that is Rs 1.22 lakh a quarter, so reaching 2% is worth **about Rs 1.04 lakh a quarter** (range Rs 1.04-2.05 lakh depending on whether the unit or the refund is the avoidable item). I chose this over "reduce goodwill refunds" because policy states it as a rule (never both), it is checkable ticket by ticket, and it does not punish the CSAT trade Priya describes.

## D. What I tried and threw away
- **Stripping the giveaway boilerplate from the text before classifying.** I hoped it would stop "not delivered + free replacement" tickets being read as hardware faults. CV accuracy fell from 98.1% to 96.5% (LOST-TRANSIT 83% -> 66%). Reverted; routed that language to `GOODWILL` instead.
- **A keyword rule for lost-in-transit.** On labelled rows it caught 46 true cases but also 169 return cases (reverse-pickup notes mention couriers). Dropped.
- **Using order age to separate DOA from warranty.** Distributions overlap; merged the two codes.
- **Per-agent "league table" of goodwill.** Share filed as GW-OTHER is similar across teams, i.e. a dropdown habit, so it would blame the wrong thing.
- **An LLM re-coder.** Cost would be small (below) but a local model reaches 98% agreement and keeps the tool runnable offline.

## E. How I checked it
- **Deterministic money (tests, run every time):** no duplicate ids; legacy factor exactly 100 on every pair; bridge from raw to reconciled adds up to the rupee; monthly-by-reason, monthly-by-agent, agent table, long table all equal the total; no refund exceeds its order value; every ticket has an agent.
- **Reason model:** 5-fold CV on 1,349 deliberate-code refunds: 98.1% (CANCEL, DUP-PAYMENT, RETURN-QC-OK about 100%, PRICE-ADJ 99%, HW-FAULT 93%, LOST-TRANSIT 83%); 98.9% on the 97% of rows above confidence 0.60.
- **Reading by hand (me, not Vireo):** 40 GW-OTHER re-codes from the first version: 2 clear errors ("not delivered + free unit" tickets labelled hardware fault) and 1 ambiguous - the cause of the routing change. Fresh sample of 30 model re-codes after the changes (seed 77): 0 clear errors, 1 ambiguous (transit damage: HW-FAULT vs LOST-TRANSIT). So roughly 97% (29-30 of 30); with n=30 the plausible range is about 83-100%. Not a substitute for a Vireo reviewer.
- **Double-dip detector:** 30 note-only detections (drawn from the first 118 found, before I added four more phrasings that brought it to 153) read by hand: all true; the 35 extra were not re-read. Recall unknown: refunds whose note mentions a replacement but with no matching phrase were not reviewed.
- **Where it is likely wrong:** HW-FAULT vs LOST-TRANSIT when damage happened in transit; rows with empty or one-word notes ("done", "cx ok") - those get `UNCLEAR` or a low-evidence guess.

## F. What is wrong with this (honest list)
1. CV measures agreement with the agents' deliberate codes, not truth. GW-OTHER rows are drawn from a different mix and may be harder.
2. `HW-FAULT` merges DOA and warranty buy-back; Finance cannot see the split.
3. The 153 note-only double-dips are my reading of free text; the flag is the agent's. I did not review recall.
4. Replacement cost uses unit cost + Rs 340 and ignores refurbishment recovery (policy says not to assume it).
5. Refunds on `open`/`pending` tickets (115 tickets over the 18 months; Rs 0.55 lakh in Q2-26 alone) are included as "raised"; they may not have been paid.
6. Month is the creation month, so a refund raised the next month is booked to the earlier one.
7. `orders_refunded_more_than_value.csv` (98 orders, Rs 2.5 lakh over order value) is a review list only: a genuine double payment legitimately refunds more than one order value, and order_id is blank on 34% of refund tickets.
8. Goodwill-cap check: all 181 goodwill-type refunds exceed the Rs 500 cap; the data has no approval field, so I cannot say which lacked Team Lead approval.
9. The helpdesk "Rs 11 lakh" reconciliation is an inference.
10. Windows/macOS not tested; Linux only. The Streamlit app was compile-checked, not clicked through.

## G. What I deliberately left out
SLA breach credits (Rs 350 each) and their agent attribution; transfer cost; first-contact-resolution and repeat-contact costing; handle time (legacy `resolved_at` is UTC); shift/site analysis; customer-level repeat refunders. None of them is in the ask; each is a day of work; the refund-by-reason-and-agent question needed the data cleaning and the GW-OTHER finding first.

## H. Anything nobody asked for
The GW-OTHER finding, the refund + unit finding (319 cases; the flag undercounts by about half), the goodwill-cap observation, the refunds-rose-with-volume finding, and that the CSAT claim (+0.4) is not visible in the data (3.48 in Q3-25, 3.51 in Q4-25).

## I. Pushback on the brief
- "Who is giving away money" - the data does not support naming individuals for goodwill: GW-OTHER share is a dropdown artefact. I report agents on rates and on the one rule that is checkable (refund + unit).
- Agents are not comparable across tiers (policy s6), so the agent sheet carries Tier and team beside every row.
- Neha's note that the Returns Desk does most refunds: it handles 26% of refunds and 28 of 319 double-dips. The concentration is in Logistics and the frontlines.
