# VOE LAB Engineering Contribution Standard

This repository is a public systems-engineering sandbox. Contributions must preserve the boundary between reproducible research artifacts and production/physical control systems.

## 1. Scope

Accepted changes include:

- public protocol specifications;
- synthetic telemetry contracts;
- deterministic simulators;
- OpenAPI schemas;
- architecture decision records;
- parser/codec research using synthetic frames;
- conformance tests;
- observability and failure-model documentation.

Not accepted in this public repository:

- production credentials;
- real customer/user data;
- private infrastructure topology;
- real fleet identifiers;
- operational device-control commands;
- bypass/unlock procedures;
- proprietary code obtained from third parties.

## 2. Contract-first workflow

Any externally consumed artifact must begin with a versioned contract. A change to a protocol, schema, event envelope or API must identify:

1. contract version;
2. invariants;
3. field bounds;
4. compatibility behavior;
5. failure semantics;
6. migration path;
7. rollback path;
8. conformance tests.

## 3. Protocol requirements

Protocol research must use bounded lengths, deterministic parsing, explicit endianness, version fields, reserved-bit semantics, integrity/error handling and rejection behavior for malformed input. Parsers must never trust length or type fields before validating bounds.

## 4. API requirements

HTTP contracts must define stable error envelopes, request correlation, pagination bounds, validation rules, compatibility policy and rate-limit semantics where relevant. Do not publish reachable production server URLs.

## 5. Telemetry requirements

Telemetry examples must remain synthetic. Event envelopes should keep schema identity, event identity, sequence, timestamp, source and payload separate. Sequence numbers are diagnostic ordering material, never authentication material.

## 6. Testing

Changes should cover valid cases, boundary values, malformed input, unknown versions/types, truncation, duplicate events, out-of-order events and deterministic regression fixtures where applicable.

## 7. Security

Public artifacts must fail closed and minimize attack surface. Never commit secrets, production endpoint inventories, real device identifiers, real geolocation traces or unrestricted control interfaces.

## 8. Review gate

A change is merge-ready only when its contract, compatibility, tests, failure behavior, security boundary and rollback implications are explicit.
