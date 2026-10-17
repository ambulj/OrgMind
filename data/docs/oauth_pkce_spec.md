# Technical Specification: OAuth 2.1 PKCE Code Exchange Flow

- **Document ID**: DOC_OAUTH_PKCE_SPEC
- **Author**: Alice Chen (Principal Architect)
- **Date**: 2026-01-28
- **Project**: PRJ_OAUTH_UPGRADE
- **Status**: Current

## Implementation Details
All client single-page applications (SPA) must generate a cryptographically random code verifier (minimum 43 characters) and compute code challenge using SHA-256 (`code_challenge_method=S256`).

## Decision: Reject Plain Code Challenges
On 2026-01-28, Alice Chen decided that Keycloak will strictly reject any authorization request that uses `code_challenge_method=plain`. Only `S256` is permitted across Northwind Labs systems.

## Provenance
- Source ID: `SRC_DOC_PKCE_01`
- Approved by: Alice Chen and Elena Rostova
