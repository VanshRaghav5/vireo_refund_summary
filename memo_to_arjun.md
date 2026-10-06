# Memo — Refunds are not a ₹1 crore/quarter problem

**To:** Arjun Mehta, Finance Controller, Vireo Audio  
**Date:** 4 October 2026  
**Subject:** Refund reconciliation, drivers and immediate leakage control

## Bottom line

The export is overstating refunds. After correcting the legacy Freshdesk monetary unit and removing migration re-import duplicates, the 18-month file contains **₹67.10 lakh** of refunds across **2,340 refund tickets**. Q2 2026 is **₹12.80 lakh**, which is much closer to the helpdesk estimate of roughly ₹11 lakh/quarter than the raw Finance export.

The clearest controllable leakage is a policy breach: **166 tickets (7.1% of refund tickets) show both a refund and a replacement**, worth **₹5.74 lakh**. The policy says a customer must not receive both for the same order.

## What is driving the money

**GW-OTHER** is the largest refund reason at **₹29.07 lakh (43.3% of refund value)**. This should not automatically be treated as agent misconduct: the CX team explicitly changed frontline behaviour to reduce arguments, and the stated trade-off was higher refunds for higher CSAT.

The agent table therefore separates volume from exception behaviour. The highest-dollar agents are largely in Billing/Returns, where refunds are expected. Tier 2 is not ranked against Tier 1 because the operating policy explicitly says Tier 2 is multi-touch and should not be compared on ticket volume.

## Recommended target

Reduce refund+replacement exceptions from **7.1% to 2.0%** within one quarter. Using the average quarterly refund value for Q1–Q2 2026, that is approximately **₹64,650 per quarter / ₹2.59 lakh annualised** of avoidable refund leakage, if the prevented refunds are fully recoverable.

## Actions

1. Add a hard stop before refund approval when `replacement_issued = Y`.
2. Require Team Lead review for any exception and report the exception rate weekly by agent/team.
3. Keep goodwill refunds visible as a separate management choice rather than labelling them as agent waste.
4. Use the monthly reason/agent tables in the board pack; use the AI reviewer only to flag tickets for human review, not to calculate money.

**Confidence:** High for the financial reconciliation and policy-exception count; moderate for the AI reason-code reviewer. The local reviewer achieved **54.0% held-out accuracy**, so it is advisory only.
