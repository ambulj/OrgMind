# Decision Record: Core US Billing Engine & Stripe Checkout

- **Document ID**: DOC_BILLING_SPEC
- **Author**: Bob Martinez (Tech Lead Backend)
- **Date**: 2026-01-20
- **Project**: PRJ_BILLING_STRIPE
- **Status**: Current

## Problem Statement
Legacy credit card storage violates modern PCI requirements and lacks modern fraud detection for Northwind Labs US subscriptions.

## Decision: Adopt Stripe Elements for US Checkout
On 2026-01-20, Bob Martinez and Carol Danvers decided:
1. We will use Stripe Elements for the frontend US subscription flow.
2. Webhooks will be dispatched to an asynchronous queue with idempotency tracking.

## Provenance
- Source ID: `SRC_DOC_BILL_01`
- Decision ratified by: Bob Martinez and Carol Danvers
