# Incident Postmortem: Paynova European Settlement Discrepancy (INC-409)

- **Document ID**: DOC_INCIDENT_409_POSTMORTEM
- **Author**: Priya Sharma (Payments Engineering Lead) & Aarav Mehta (QA Engineer)
- **Date**: 2026-05-29
- **Project**: PRJ_BILLING_STRIPE
- **Severity**: P1 Outage

## Summary
On 2026-05-28, Paynova's European settlement clearing endpoint failed silently, causing 42% of customer recurring renewals to fail with erroneous `settlement_timeout` codes.

## Root Cause
Paynova infrastructure suffered a multi-region database lockup, and their sandbox was out of sync with production API behaviors.

## Corrective Action Recommendation
Priya Sharma and Rohan Iyer recommend terminating the Paynova gateway integration and immediately migrating European recurring subscriptions to Stripe Billing V2.
