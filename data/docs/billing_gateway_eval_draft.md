# Evaluation Draft: European Payment Gateway Options

- **Document ID**: DOC_BILLING_GATEWAY_EVAL_DRAFT
- **Draft ID**: DRAFT_PAYNOVA_EVAL
- **Topic**: Paynova
- **Author**: Rohan Iyer (Senior Backend Engineer)
- **Date**: 2026-02-24
- **Project**: PRJ_BILLING_STRIPE
- **Status**: Draft (Proposal Disagreed With Final Decision)

## Executive Summary
This draft evaluates third-party providers for our Q2 European recurring billing launch.

## Recommendation: Strongly Advise Against Paynova
On 2026-02-24, Rohan Iyer recommended against adopting Paynova:
> "Based on benchmark tests, Paynova's SDK lacks robust multi-currency idempotency and their sandbox exhibited intermittent timeout spikes. I strongly recommend expanding Stripe Billing V2 or Adyen to Europe rather than introducing Paynova."

## Provenance
- Source ID: `SRC_DOC_DRAFT_PAYNOVA_EVAL`
- Author: Rohan Iyer (@ro)
- Note: This recommendation was formally reviewed but rejected in favor of Paynova during the March 1 architecture meeting.
