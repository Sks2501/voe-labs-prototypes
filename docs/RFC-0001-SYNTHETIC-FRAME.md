# RFC-0001 — VLP/1 Synthetic Binary Frame

Status: Experimental  
Audience: public sandbox consumers and test tooling  
Security classification: synthetic-public-demo

## 1. Abstract

VLP/1 defines a deterministic binary envelope for transporting synthetic telemetry fixtures inside the public laboratory. It exists to exercise framing, bounded parsing, version negotiation and integrity validation. It is not a production device protocol and intentionally defines no actuation operations.

## 2. Design goals

- fixed-width header;
- network-independent byte order;
- bounded payload size;
- explicit version field;
- explicit sequence field;
- integrity verification;
- allocation-free reference decoding;
- deterministic error taxonomy;
- no operational control message types.

## 3. Integer representation

All multi-byte integers are unsigned and encoded in big-endian byte order.

## 4. Frame layout

```text
Offset  Size  Field
0       2     magic = 0x56 0x4C (ASCII "VL")
2       1     major_version
3       1     message_type
4       4     sequence
8       2     payload_length
10      N     payload
10+N    4     crc32
```

Minimum frame length: 14 bytes.  
Maximum payload length: 512 bytes.  
Maximum frame length: 526 bytes.

## 5. Version

`major_version` MUST equal `1` for VLP/1.

A decoder receiving an unknown major version MUST reject the frame with `VLP_ERR_VERSION`.

## 6. Message types

Only synthetic observation messages are defined:

| Value | Symbol | Meaning |
|---:|---|---|
| `0x01` | `VLP_MSG_HEARTBEAT` | synthetic liveness sample |
| `0x02` | `VLP_MSG_BATTERY_SAMPLE` | synthetic battery percentage sample |
| `0x03` | `VLP_MSG_POSITION_SAMPLE` | synthetic position fixture |
| `0x04` | `VLP_MSG_STATE_SAMPLE` | synthetic state fixture |

Values outside this table are rejected by the reference implementation.

No unlock, lock, motor, firmware, provisioning or maintenance-control messages exist in VLP/1.

## 7. Sequence semantics

`sequence` is an unsigned 32-bit stream-local counter. Wraparound from `0xFFFFFFFF` to `0x00000000` is valid.

Consumers may use it for diagnostics and duplicate detection. Sequence alone MUST NOT be treated as authentication or authorization data.

## 8. Payload

The payload is opaque to the frame codec. Message-specific payload interpretation belongs to higher-level synthetic schemas.

A payload may have zero bytes.

`payload_length` MUST NOT exceed 512. A decoder MUST verify that the received frame length exactly matches `14 + payload_length`.

## 9. CRC-32

The final four bytes contain IEEE CRC-32 calculated over all bytes from offset 0 through the final payload byte. The CRC field itself is excluded from the calculation.

Parameters:

```text
polynomial: 0xEDB88320
initial:    0xFFFFFFFF
reflect-in: true
reflect-out:true
xor-out:    0xFFFFFFFF
```

CRC detects accidental corruption only. It is not an authentication mechanism.

## 10. Validation order

A compliant decoder validates in this order:

1. input pointers;
2. minimum frame length;
3. magic;
4. protocol version;
5. message type;
6. payload length upper bound;
7. exact total frame length;
8. CRC;
9. output assignment.

No decoded payload pointer or metadata may be returned after an earlier validation failure.

## 11. Error taxonomy

```text
VLP_OK               successful operation
VLP_ERR_ARGUMENT     null/invalid function argument
VLP_ERR_BUFFER       destination buffer too small
VLP_ERR_LENGTH       malformed or unsupported length
VLP_ERR_MAGIC        invalid magic bytes
VLP_ERR_VERSION      unsupported protocol major version
VLP_ERR_TYPE         unsupported message type
VLP_ERR_CRC          integrity mismatch
```

## 12. Parser safety

The reference decoder:

- performs no dynamic allocation;
- never copies payload bytes during decode;
- exposes payload as a bounded view into caller-owned input;
- does not read beyond the supplied frame length;
- writes output only after all validation succeeds.

## 13. Compatibility

VLP/1 reserves no implicit extension bytes. A future incompatible header requires a new major version.

New message types may be documented for future sandbox experiments, but a VLP/1 decoder that does not recognize a type rejects it rather than guessing its structure.

## 14. Security considerations

VLP/1 deliberately lacks authentication, encryption and device authorization because it is a local synthetic laboratory protocol. It MUST NOT be represented as a secure production transport.

Real-world systems require authenticated peers, replay protection, key lifecycle management and transport-specific threat analysis outside the scope of this repository.

## 15. Reference implementation

The allocation-free reference codec is located under `protocol/vlp1/` and is continuously compiled and tested by repository CI.
