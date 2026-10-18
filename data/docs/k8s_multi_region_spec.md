# Infrastructure Architecture: Multi-Region Kubernetes Topology

- **Document ID**: DOC_K8S_SPEC
- **Decision ID**: DEC_K8S_2026_01
- **Topic**: Kubernetes
- **Author**: David Kim (DevOps Engineer)
- **Date**: 2026-02-05
- **Project**: PRJ_K8S_MIGRATION
- **Status**: Current

## Problem Statement
Single-region AWS deployment in us-east-1 represents a single point of failure for Northwind Labs API gateways.

## Decision: Active-Passive Multi-Region EKS Deployment
On 2026-02-05, David Kim and Alice Chen decided:
> "We will operate primary Kubernetes clusters in us-east-1 and an active-passive standby cluster in eu-central-1 using Route53 latency routing and automatic health checks."

## Provenance
- Source ID: `SRC_DOC_K8S_01`
- Approved by: David Kim (@davidk) and Alice Chen (@alice)
