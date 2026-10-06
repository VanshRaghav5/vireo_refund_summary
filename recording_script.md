# 3-minute screen-recording script

## 0:00–0:30 — Prompt / brief
Show the task pack and say:
“I treated the email thread as context, not as a specification. The first decision was to reconcile the export before blaming agents.”

## 0:30–1:05 — Data problems found
Show the reconciliation screen.
“Legacy Freshdesk values are 100x the rupee amounts: for example, the legacy row says 212,400 while the note says Rs 2,124. I divide legacy monetary exports by 100. I also found 513 duplicated ticket IDs caused by migration re-imports and prefer the current helpdesk row where both exist.”

## 1:05–1:45 — Board output
Show By Reason, then By Agent.
“The corrected total is Rs 67.10 lakh over 18 months. Q2 2026 is Rs 12.80 lakh. GW-OTHER is the largest reason, but I am not calling it waste because the CX email explicitly says frontline was told to stop arguing with customers.”

## 1:45–2:25 — What I would act on
Show Policy Exceptions.
“166 tickets contain both a refund and a replacement, Rs 5.74 lakh in value. That directly conflicts with policy. The exception rate is 7.1% of refund tickets. My target is 2%, worth about Rs 64,650 per quarter using the recent quarterly run-rate.”

## 2:25–2:50 — AI component
Show Local AI Reviewer.
“I added a lightweight local TF-IDF/logistic-regression reviewer to flag possible reason-code mismatches. Its held-out accuracy is 54%, so I deliberately did not let it overwrite financial numbers or agent codes.”

## 2:50–3:00 — What I discarded
Show the project README.
“I discarded any approach that treated the raw export as trustworthy, any ranking that compared Tier 2 with Tier 1 on volume, and any attempt to call GW-OTHER automatically waste. Those conclusions were not supported by the source pack.”
