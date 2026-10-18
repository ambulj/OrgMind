# Architecture Decision Record: OAuth 2.1 & Keycloak Migration

- **Document ID**: DOC_AUTH_SPEC
- **Decision ID**: DEC_AUTH_2026_01
- **Topic**: OAuth
- **Author**: Alice Chen (Principal Architect)
- **Date**: 2026-01-15
- **Project**: PRJ_OAUTH_UPGRADE
- **Status**: Current

## Context
Northwind Labs has historically used monolithic stateful sessions stored in Memcached. As we scale microservices across Kubernetes clusters, session replication is causing latency spikes and auth failures.

## Decision: Adopt OAuth 2.1 with PKCE & Keycloak
We have decided to adopt **OAuth 2.1 with PKCE** for all user-facing web and mobile applications, backed by Keycloak as our Identity Provider.
- Tokens will be short-lived RS256 JWTs (15-minute expiry).
- Refresh tokens will be stored in secure HTTP-only cookies with rotation enabled.

## Provenance
- Source ID: `SRC_DOC_AUTH_01`
- Ratified on 2026-01-15 by Alice Chen (@alice) and Elena Rostova (@elena).
