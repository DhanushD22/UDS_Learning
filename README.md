# Automotive UDS Diagnostic Server & Client (ISO 14229)  
**Full ECU Reprogramming + Diagnostics in Pure Python**

### Supported UDS Services

| Service | Implemented | Description |
|---------|-------------|-----------|
| `0x10`  | 	Yes 	| Diagnostic Session Control (Extended) |
| `0x27`  | 	Yes 	| Security Access (Seed/Key) |
| `0x22`  | 	Yes 	| Read Data By Identifier (VIN: F190) |
| `0x19`  | 	Yes 	| Read DTC Information |
|         | 	Yes 	| → 0x01: Number of DTC by Status Mask |
|         | 	Yes 	| → 0x02: Report DTC by Status Mask |
|         | 	Yes 	| → 0x04: Snapshot Record (Freeze Frame: RPM, Speed, Load) |
|         | 	Yes 	| → 0x06: Extended Data (Occurrence Counter) |
| `0x3E`  | 	Yes 	| Tester Present |
| `0x11`  | 	Yes 	| ECU Reset (Hard + Soft) |
| `0x31`  | 	Yes 	| Routine Control (Self-Test Start/Stop) |
| `0x34`  | 	Yes 	| Request Download |
| `0x36`  | 	Yes 	| Transfer Data (50 KB firmware demo) |
| `0x37`  | 	Yes 	| Request Transfer Exit |

**Full ISO-TP multi-frame support** for long responses (VIN, DTC lists, firmware).

### Demo Output (Real Run)

ECU → 59 04 Snapshot for P010000 (Rec 0xFF): RPM=1800
ECU → 59 06 Extended data for P010000: occurrence=12
ECU 34 00 Request Download: 50000 bytes @ 0x08010000
ECU 36 01 Received chunk 3846 bytes → Total: 3846/50000
...
ECU FLASHING COMPLETE! 50000 bytes written to 0x08010000


### How to Run
## 1. Setup virtual CAN
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0

## 2. Run ECU server
python3 uds_server.py

## 3. Run diagnostic client (in new terminal)
python3 uds_client.py


### Requirements
python-can==4.3.1
