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




### New component: uds_tester.py — Manual ISO-TP Educational Tester (SF/FF/CF/FC)

This is a low-level transport-layer test tool that:

1. Manually sends Single Frames (SF)

2. Manually constructs First Frames (FF)

3. Sends Flow Control Frames (FC)

4. Sends sequential Consecutive Frames (CF)

5. Reassembles incoming multi-frame responses

6. Prints sequence numbers, payload chunking, PCI types

## This script is used to learn and validate ISO 15765-2 behavior:

1. Why large UDS messages require segmentation

2. How FF announces payload length

3. Why CF frames have sequence numbers

4. When FC frames must be sent

5. How the tester reassembles long responses (VIN, DTC lists, snapshots, etc.)

It is NOT a diagnostic tool.
Instead, it is a teaching/debugging tool that exposes the raw ISO-TP flow.

## Use this when you want to:

1. understand FF/CF/FC deeply

2. validate ECU segmentation logic

3. debug multi-frame behaviors



### Why Both Clients Are Needed
| Script            | Purpose                         | Layer                    | Users                |
| ----------------- | ------------------------------- | ------------------------ | -------------------- |
| **uds_client.py** | Real diagnostics + flashing     | UDS application layer    | Engineers, testers   |
| **uds_tester.py** | Learn/debug ISO-TP segmentation | Transport layer (ISO-TP) | Developers, students |
| **uds_server.py** | ECU simulation                  | Server side              | Embedded developers  |


Together these components replicate the workflow used in real automotive OEM diagnostic stacks.



### How to Run
## 1. Run ECU server
python3 uds_server.py

## 2. Run diagnostic tester (in new terminal)
python3 uds_tester.py

###Expected Output (Sample)

UDS Tester (Manual ISO-TP FF / CF / FC Mode)

→ 10 03 Diagnostic Session
→ SF: 0210030000000000
← SF: 0250030000000000
   UDS Response: 5003
→ 27 01 Request Seed
→ SF: 0227010000000000
← SF: 066701CAFEBABE00
   UDS Response: 6701CAFEBABE
→ 22 F1 90 Read VIN
→ SF: 0322F19000000000
← FF: 101462F19056494E  (Total=20)
→ FC: 3000000000000000
← CF[1]: 2131323334353637
← CF[2]: 2238393031323334
   UDS Response: 62F19056494E3132333435363738393031323334


> 🔗 For hardware-level CAN bring-up using MCP2515 and ESP32,
> see: [[https://github.com//mcp2515-can-bench]](https://github.com/DhanushD22/mcp2515-can-bench)

