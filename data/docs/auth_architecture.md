# Architecture Decision Record: Authentication & Identity Strategy

- **Document ID**: DOC_AUTH_SPEC
- **Author**: Alice Chen (Principal Architect)
- **Date**: 2026-01-15
- **Status**: Active

## Context & Problem Statement
Northwind Labs has historically used monolithic stateful sessions stored in Memcached. As we scale to microservices across Kubernetes clusters, session replication is causing latency spikes and auth failures.

## Decision 1: Migrate to OAuth 2.1 & Keycloak
We have decided to adopt **OAuth 2.1 with PKCE** for all user-facing web and mobile applications, backed by Keycloak as our Identity Provider.
- Tokens will be short-lived RS256 JWTs (15-minute expiry).
- Refresh tokens will be stored in secure HTTP-only cookies with rotation enabled.

## Decision 2: Service-to-Service mTLS
For internal inter-service communication within the Kubernetes cluster, services will authenticate using mutual TLS (mTLS) managed by Istio service mesh rather than passing end-user tokens directly.

## Ownership & Approvals
- **Decision Owner**: Alice Chen (@alice)
- **Approved By**: Architecture Review Board (Elena Rostova, Bob Martinez)
- **Target Completion**: 2026-03-31
