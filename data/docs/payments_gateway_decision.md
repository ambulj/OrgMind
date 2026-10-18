# Meeting Notes: European Payment Rail Ratification

- **Document ID**: DOC_PAYMENTS_GATEWAY_DECISION
- **Decision ID**: DEC_PAYMENTS_2026_03_PAYNOVA
- **Topic**: Paynova
- **Author**: Priya Sharma (Payments Engineering Lead)
- **Date**: 2026-03-01
- **Project**: PRJ_BILLING_STRIPE
- **Status**: Current (Subject to live reversal)

## Attendees
Priya Sharma (@pri), Neha Kapoor (@neha), Bob Martinez (@bob), Rohan Iyer (@ro)

## Context & Evaluation
While Rohan Iyer's evaluation draft (DOC_BILLING_GATEWAY_EVAL_DRAFT) advised using Stripe or Adyen, Paynova offered a 45 basis point interchange discount and direct SEPA Direct Debit integration.

## Decision: Adopt Paynova Gateway for European Recurring Subscriptions
On 2026-03-01, Priya Sharma and Neha Kapoor ratified the decision:
> "Northwind Labs adopts Paynova as the primary gateway rail for EU customer subscriptions, deploying their SDK across the billing services for Q2."

## Provenance
- Source ID: `SRC_DOC_PAYNOVA_DECISION_01`
- Decision Ratified by: Priya Sharma and Neha Kapoor
- Confirmed in #payments chat on 2026-03-02 (MSG_PAY_001)
