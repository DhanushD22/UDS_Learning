# Automotive UDS Diagnostic Server (ISO 14229)

Full UDS client + server over virtual CAN (vcan0) in pure Python.

## Supported Services
- `0x10` – Diagnostic Session Control
- `0x27` – Security Access (seed/key)
- `0x22` – Read Data By Identifier (VIN)
- `0x19` – Read DTC Information:
  - `0x01` – Number of DTC by Status Mask
  - `0x02` – Report DTC by Status Mask
  - `0x04` – DTC Snapshot Record (Freeze Frame)
  - `0x06` – DTC Extended Data (Occurrence Counter)
- `0x3E` – Tester Present

## Features
- Multi-frame ISO-TP support (for long VIN, DTC lists, snapshots)
- Real-world DTCs (P0100, P0301, P0420)
- Freeze-frame data (RPM, Speed, Load)
- Extended data counters

## How to Run
```bash
python3 uds_server.py   # Terminal 1
python3 uds_client.py   # Terminal 2
