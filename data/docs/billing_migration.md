# Decision Record: Billing Engine & Payment Gateway

- **Document ID**: DOC_BILLING_SPEC
- **Author**: Bob Martinez (Tech Lead Backend)
- **Date**: 2026-01-20
- **Status**: Historical (See live update)

## Problem Statement
Our in-house credit card processor has high maintenance overhead and lacks multi-currency support for our EU expansion.

## Decision: Adopt Stripe Elements with Custom Webhook Queue
On 2026-01-20, Bob Martinez and Carol Danvers decided:
1. We will use Stripe Elements for the frontend checkout flow.
2. We will handle webhook events using an in-memory Redis FIFO queue.
3. Database chosen for transaction reconciliation is PostgreSQL.

## Ownership
- **Lead Engineer**: Bob Martinez (@bob)
- **Product Manager**: Carol Danvers (@carol)
