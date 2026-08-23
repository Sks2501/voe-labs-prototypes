# Architecture

## 1. Purpose

VOE LAB Public Sandbox is a non-production systems-engineering environment used to study deterministic protocol design, telemetry contracts, embedded framing, service boundaries and failure semantics using synthetic data only.

The repository deliberately separates specification from implementation. A consumer must be able to understand a contract without reading implementation code, while implementations must remain testable against the contract.

## 2. Architectural constraints

The public sandbox follows these invariants:

1. No production credentials or private endpoints.
2. No real fleet identifiers or personal data.
3. No operational actuation commands.
4. Every public message format has an explicit version.
5. Every binary frame has bounded length.
6. Parsers reject malformed input before interpreting payloads.
7. Network-facing schemas use strict validation.
8. Events are designed for idempotent consumers.
9. Correlation identifiers are opaque and non-sensitive.
10. Failure is represented explicitly rather than inferred from missing data.

## 3. Logical topology

```text
┌───────────────────────────────┐
│        API CONTRACTS          │
│ OpenAPI · errors · pagination │
└───────────────┬───────────────┘
                │
                v
┌───────────────────────────────┐
│      APPLICATION MODEL        │
│ vehicles · telemetry · health │
└───────────────┬───────────────┘
                │
                v
┌───────────────────────────────┐
│       EVENT ENVELOPES         │
│ id · sequence · time · source │
└───────────────┬───────────────┘
                │
                v
┌───────────────────────────────┐
│        PROTOCOL CODEC         │
│ framing · bounds · integrity  │
└───────────────┬───────────────┘
                │
                v
┌───────────────────────────────┐
│      SYNTHETIC TRANSPORT      │
│ local simulator / test bytes  │
└───────────────────────────────┘
```

## 4. Boundary model

### API boundary

Responsibilities:

- validate path/query parameters;
- normalize error responses;
- enforce pagination limits;
- attach request correlation metadata;
- expose read-only synthetic resources.

### Event boundary

Responsibilities:

- preserve event identity;
- preserve monotonic sequence within a synthetic stream;
- carry schema version;
- separate envelope metadata from payload;
- allow duplicate detection.

### Binary protocol boundary

Responsibilities:

- validate magic bytes;
- validate protocol version;
- validate message type;
- validate declared payload length against hard limits;
- validate frame integrity before payload consumption;
- reject trailing or truncated data.

## 5. Failure model

The system distinguishes four failure classes.

### Contract failure

Input violates OpenAPI, JSON Schema or binary framing requirements.

Result: deterministic rejection with no partial interpretation.

### Compatibility failure

A consumer receives an unsupported major protocol/schema version.

Result: fail closed and report unsupported version.

### Integrity failure

A frame's integrity field does not match the received bytes.

Result: discard the frame. No payload fields are exposed to downstream logic.

### Runtime failure

A simulator or local tool encounters an execution error unrelated to message validity.

Result: terminate or report a bounded error without mutating external systems.

## 6. Compatibility policy

Version numbers use `MAJOR.MINOR` semantics for protocol families.

- Major changes may break compatibility.
- Minor changes may add optional behavior without redefining existing fields.
- Unknown optional fields must be ignored by tolerant application-level consumers.
- Unknown binary message types are rejected by the reference codec unless explicitly registered.
- Existing field meaning must never change inside the same major version.

## 7. Data classification

Every public fixture is classified as `synthetic-public-demo`.

The repository does not require collection, storage or processing of personal information.

## 8. Reliability properties

Reference implementations favor:

- bounded buffers;
- explicit integer widths;
- no dynamic allocation in the C codec;
- deterministic return codes;
- complete frame-length verification;
- reproducible unit tests;
- schema validation in CI.

## 9. Observability model

Synthetic events include:

- event identifier;
- sequence number;
- schema identifier;
- timestamp;
- source;
- synthetic vehicle identifier.

Application responses include a request identifier and generation timestamp.

These fields are intended to make message flow inspectable without exposing private infrastructure.

## 10. Repository responsibilities

```text
api/                 HTTP contract
schemas/             machine-readable application contracts
protocol/            reference binary framing implementation
telemetry/           deterministic synthetic producers
docs/                architecture, RFCs and protocol policy
.github/workflows/   automated contract and codec verification
```

## 11. Non-goals

This repository does not implement:

- vehicle unlocking;
- remote motor control;
- battery-management commands;
- firmware update mechanisms;
- provisioning of real devices;
- production authentication;
- production fleet management.

Those exclusions are architectural boundaries, not missing implementation work.
