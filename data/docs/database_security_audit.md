# Security Policy: Database Connection IAM Authentication

- **Document ID**: DOC_DB_SECURITY_AUDIT
- **Decision ID**: DEC_SEC_2026_01
- **Topic**: Security
- **Author**: Elena Rostova (Staff Security Engineer)
- **Date**: 2026-02-12
- **Project**: PRJ_K8S_MIGRATION
- **Status**: Current

## Security Finding
Static database passwords stored in Kubernetes Secrets present an unnecessary credential leakage vector.

## Decision: Mandatory IAM Role-Based Authentication
On 2026-02-12, Elena Rostova decided:
> "All database clients connecting from Kubernetes pods must authenticate using short-lived IAM IRSA tokens instead of static passwords."

## Provenance
- Source ID: `SRC_DOC_SEC_IAM_01`
- Security Auditor: Elena Rostova (@elena)
