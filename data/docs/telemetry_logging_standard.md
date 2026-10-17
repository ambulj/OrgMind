# Engineering Standard: OpenTelemetry Structured JSON Logging

- **Document ID**: DOC_TELEMETRY_STANDARD
- **Author**: Bob Martinez (Tech Lead Backend)
- **Date**: 2026-02-18
- **Project**: PRJ_OAUTH_UPGRADE
- **Status**: Current

## Overview
Microservices logging formats currently vary across text, colored console logs, and syslog formats.

## Decision: Standardize on OpenTelemetry Structured JSON
On 2026-02-18, Bob Martinez decided:
> "All backend services must output structured JSON logs with trace_id and span_id injected by OpenTelemetry SDK for distributed request correlation."

## Provenance
- Source ID: `SRC_DOC_TELEMETRY_01`
- Author: Bob Martinez (@bob)
