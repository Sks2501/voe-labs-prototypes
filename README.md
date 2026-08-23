# VOE LAB / Systems Engineering Sandbox

![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0.3-111827?style=flat-square&logo=openapiinitiative)
![Protocols](https://img.shields.io/badge/protocols-versioned-111827?style=flat-square)
![Architecture](https://img.shields.io/badge/architecture-failure_oriented-111827?style=flat-square)
![Data](https://img.shields.io/badge/data-synthetic_only-111827?style=flat-square)
![Security](https://img.shields.io/badge/security-no_production_secrets-111827?style=flat-square)

Public systems-engineering laboratory for protocol design, deterministic telemetry contracts, API compatibility, failure semantics and reproducible sandbox tooling.

This repository is intentionally designed as a **technical lab**, not a personal profile and not a production control repository.

## System model

```text
┌───────────────────────────────────────────────────────────────┐
│                       PUBLIC API CONTRACT                     │
│       OpenAPI · pagination · errors · correlation IDs        │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                    APPLICATION DATA MODEL                     │
│       synthetic resources · states · compatibility           │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                     TELEMETRY ENVELOPES                       │
│     schema · event identity · sequence · source · time        │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                      PROTOCOL RESEARCH                        │
│ framing · validation · bounded parsing · integrity semantics  │
└──────────────────────────────┬────────────────────────────────┘
                               │
                               ▼
┌───────────────────────────────────────────────────────────────┐
│                    SYNTHETIC LOCAL TOOLING                    │
│ deterministic generators · fixtures · diagnostics · tests     │
└───────────────────────────────────────────────────────────────┘
```

## Repository topology

```text
voe-labs-prototypes/
├── README.md
├── SECURITY.md
├── api/
│   └── openapi.yaml
├── dashboard/
│   └── index.html
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROTOCOLS.md
│   └── RFC-0001-SYNTHETIC-FRAME.md
└── telemetry/
    └── simulator.js
```

## Contracts

### HTTP surface

`api/openapi.yaml` defines the public read-only sandbox interface.

Current contract families:

```text
GET /v1/status
GET /v1/vehicles
GET /v1/vehicles/{vehicleId}
GET /v1/telemetry/events
```

The contract includes:

- explicit API versioning;
- pagination bounds;
- deterministic error envelopes;
- correlation identifiers;
- strict resource states;
- bounded query parameters;
- rate-limit semantics;
- machine-readable schemas.

### Telemetry envelope

Current event family:

```text
voe.lab.telemetry.demo.v1
```

Defined synthetic observation types:

```text
heartbeat.demo
battery.sample.demo
position.sample.demo
state.sample.demo
```

A telemetry event carries independent envelope metadata:

```text
schema
├── eventId
├── eventType
├── sequence
├── vehicleId
├── recordedAt
├── source
└── payload
```

Sequence numbers exist for ordering diagnostics and duplicate detection. They are not authentication material.

## Architecture documentation

### `docs/ARCHITECTURE.md`

Defines:

- logical system boundaries;
- failure classes;
- compatibility rules;
- data classification;
- reliability properties;
- observability requirements;
- explicit non-goals.

### `docs/PROTOCOLS.md`

Defines:

- protocol families;
- public resource identity;
- event semantics;
- state models;
- validation expectations;
- compatibility behavior;
- threat assumptions.

### `docs/RFC-0001-SYNTHETIC-FRAME.md`

Defines an experimental sandbox-only binary framing model used to discuss:

- fixed-width headers;
- bounded payloads;
- explicit versions;
- deterministic parsing;
- integrity checks;
- parser error taxonomy;
- allocation-free decoding principles.

The RFC intentionally contains **no operational actuation message family**.

## Failure-oriented design

The sandbox treats failure as part of the contract.

```text
invalid input
    → reject before interpretation

unsupported major version
    → fail closed

integrity mismatch
    → discard frame

external dependency failure
    → bounded timeout / explicit error

duplicate event
    → consumer must remain idempotent
```

## Compatibility rules

1. Existing field semantics do not change silently.
2. Breaking semantics require a major-version decision.
3. Optional application-level extensions must not redefine existing fields.
4. Unknown required protocol behavior is rejected instead of guessed.
5. Public examples remain independent from production infrastructure.

## Security boundary

Public material may include:

- architecture documents;
- RFCs;
- synthetic identifiers;
- synthetic telemetry;
- non-routable example endpoints;
- local simulators;
- schema and compatibility concepts;
- failure-mode documentation.

Public material does not intentionally include:

- production credentials;
- private keys;
- authentication secrets;
- internal production hostnames;
- customer information;
- personal profile information;
- real fleet identifiers;
- firmware secrets;
- operational device-control interfaces.

See `SECURITY.md` for the repository security policy.

## Engineering invariants

```text
explicit contracts       > implicit coupling
bounded parsing          > unbounded input
fail-closed semantics    > permissive guessing
idempotent processing    > duplicate side effects
observable failures      > invisible state
reproducible fixtures    > environment-dependent examples
synthetic public data    > production-data exposure
```

## Local simulator

The telemetry simulator runs locally:

```bash
node telemetry/simulator.js
```

It produces synthetic events for contract and observability experiments and does not connect to production services or physical devices.

## Scope

This repository is for public systems-engineering demonstrations, contract design and safe experimentation. It is not an operational fleet system and is not intended to control real hardware.
