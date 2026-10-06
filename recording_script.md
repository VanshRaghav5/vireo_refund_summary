# 3-minute screen recording (outline)
0:00-0:25 The brief: Finance sees > Rs 1 crore a quarter, helpdesk says Rs 11 lakh. Show outputs/qa_report.md and sheet 1 of the workbook (the bridge).
0:25-1:00 Prompt v1 -> v3 (reason re-coding): v1 trained on agents' codes incl. GW-OTHER (54% accuracy, circular) -> v2 trained only on deliberate codes (98%) -> v3 stripped giveaway boilerplate (accuracy fell, thrown away) -> v4 routed giveaway language to GOODWILL.
1:00-1:40 Show decision.md "what I threw away" and the 40-row read-through that found delivery+free-replacement tickets mis-coded.
1:40-2:20 Board pack: Month x Reason (final vs as filed), Month x Agent, then Refund+unit sheet (319 tickets).
2:20-2:50 `pytest -q` green; `python run.py` from a clean venv.
2:50-3:00 Limits: reason re-coding is a model, DOA vs warranty merged, replacement cost is a range.
