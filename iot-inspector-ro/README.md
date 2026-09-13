# IoT Inspector RO

Android diagnostic app for read-only NFC/BLE/GATT inspection.

## v1.4.0
- NFC-V / ISO15693 raw read diagnostics
- ST25DV read-only dynamic register probe
- Mailbox status and non-consuming mailbox peek (does not read the final byte)
- Public memory map with ISO15693 error decoding
- Automatic BLE scan correlated with NFC taps
- GATT remains read-only
- No NFC write, lock, password/authentication, actuator or motor-control commands
