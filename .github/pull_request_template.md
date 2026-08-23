## Engineering change
Describe the research/engineering problem, the contract affected and the implementation strategy.

## Artifact class
- [ ] Protocol/RFC
- [ ] OpenAPI/API contract
- [ ] Synthetic telemetry contract
- [ ] Deterministic simulator/tooling
- [ ] Architecture/security documentation
- [ ] Conformance/regression testing
- [ ] Documentation only

## Contract and compatibility
- Contract/schema version:
- Previous behavior:
- New behavior:
- Backward compatibility:
- Migration/deprecation plan:

## Protocol/parser analysis
Where applicable, document:

- byte/field bounds;
- endianness;
- version handling;
- malformed/truncated input rejection;
- unknown type/version behavior;
- integrity/error semantics;
- allocation/resource bounds.

## Failure analysis
- Expected failure modes:
- Duplicate/out-of-order behavior:
- Timeout/cancellation behavior:
- Retry/idempotency behavior:
- Degraded-mode behavior:

## Public safety boundary
- [ ] Synthetic data only
- [ ] No real user/customer data
- [ ] No real fleet/device identifiers
- [ ] No production credentials or endpoints
- [ ] No unrestricted device-control path
- [ ] No bypass/unlock procedure
- [ ] No third-party proprietary code

## Verification
- [ ] Valid fixture tested
- [ ] Boundary values tested
- [ ] Malformed input tested
- [ ] Unknown version/type tested where applicable
- [ ] Truncation tested where applicable
- [ ] Duplicate/out-of-order behavior tested where applicable
- [ ] Regression fixture added where applicable

## Observability
Describe deterministic diagnostics, correlation fields or signals used to understand behavior without exposing sensitive data.

## Rollback
Describe how the contract/artifact can be reverted without leaving ambiguous compatibility behavior.

## Review gate
Do not approve until contract, bounds, failure semantics, compatibility, verification and public safety boundaries are explicit.
