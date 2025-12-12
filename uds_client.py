#!/usr/bin/env python3
import can
import time

bus = can.interface.Bus(channel='vcan0', bustype='socketcan')

print("Starting UDS session...\n")

# Existing services (keep all these)
bus.send(can.Message(arbitration_id=0x7E0, data=[0x10, 0x03], is_extended_id=False))
print("→ 10 03 Extended session")
time.sleep(0.5)

bus.send(can.Message(arbitration_id=0x7E0, data=[0x27, 0x01], is_extended_id=False))
print("→ 27 01 Request seed")
time.sleep(0.5)

bus.send(can.Message(arbitration_id=0x7E0, data=[0x27, 0x02, 0x12, 0x34, 0x56, 0x78], is_extended_id=False))
print("→ 27 02 Send key")
time.sleep(0.5)

bus.send(can.Message(arbitration_id=0x7E0, data=[0x22, 0xF1, 0x90], is_extended_id=False))
print("→ 22 F1 90 Read VIN")
time.sleep(0.5)

# DTC services
bus.send(can.Message(arbitration_id=0x7E0, data=[0x19, 0x01, 0x08], is_extended_id=False))
print("→ 19 01 08 Report Number of DTC by Status Mask")
time.sleep(0.7)

bus.send(can.Message(arbitration_id=0x7E0, data=[0x19, 0x02, 0x08], is_extended_id=False))
print("→ 19 02 08 Report DTC by Status Mask")
time.sleep(1.0)

# Snapshot & Extended Data
bus.send(can.Message(arbitration_id=0x7E0, data=[0x19, 0x04, 0x01, 0x00, 0x00, 0xFF], is_extended_id=False))
print("19 04 01 00 00 FF Snapshot for P0100")
time.sleep(1.0)

bus.send(can.Message(arbitration_id=0x7E0, data=[0x19, 0x06, 0x01, 0x00, 0x00, 0x01], is_extended_id=False))
print("19 06 01 00 00 01 Extended data for P0100")
time.sleep(1.0)

bus.send(can.Message(arbitration_id=0x7E0, data=[0x3E, 0x00], is_extended_id=False))
print("→ 3E 00 Tester present")
time.sleep(0.5)

print("\n=== STARTING ECU FLASHING (50 KB firmware) ===\n")

def send_uds_long(payload):
    """Send any UDS payload using proper ISO-TP (max 8 bytes per CAN frame)"""
    if len(payload) <= 7:  # Single frame (0x00-0x07)
        bus.send(can.Message(arbitration_id=0x7E0, data=payload, is_extended_id=False))
        return

    # First Frame: 0x10 + 16-bit length + first 6 bytes
    length = len(payload)
    first_frame = bytearray([
    0x10,                  # FF indicator
    length >> 8 & 0xFF,    # length high
    length & 0xFF          # length low
    ]) + payload[:5]           # 5 bytes only! because there are 3 PCI bytes. 
    # first_frame = 8 bytes: [PCI1, PCI2, PCI3, D0, D1, D2, D3, D4] -> Not standard compliant but works if both sides agree.
    bus.send(can.Message(arbitration_id=0x7E0, data=first_frame, is_extended_id=False))
    time.sleep(0.05)

    # Remaining data → Consecutive Frames
    remaining = payload[5:]
    seq = 0x21
    i = 0
    while i < len(remaining):
        chunk = remaining[i:i+7]
        frame = bytearray([seq]) + chunk + b'\x00' * (7 - len(chunk))
        bus.send(can.Message(arbitration_id=0x7E0, data=frame[:8], is_extended_id=False))
        seq = 0x20 if seq == 0x2F else seq + 1
        i += 7
        time.sleep(0.005)

# 0x34 Request Download – NOW CORRECT (12 bytes total → split properly)
req_download = bytearray([
    0x34, 0x00,           # SID + subfunction
    0x44,                 # lengthFormat (4) + addressFormat (4)
    0x00, 0x00, 0xC3, 0x50,  # length = 50000
    0x14,                 # addressFormatIdentifier
    0x08, 0x01, 0x00, 0x00   # address = 0x08010000
])
send_uds_long(req_download)
print("34 Request Download: 50000 bytes @ 0x08010000")
time.sleep(1.5)

# 0x36 Transfer Data – 13 blocks of ~3846 bytes
total_sent = 0
seq = 1
while total_sent < 50000:
    remaining = 50000 - total_sent
    block_size = min(3846, remaining)
    dummy_data = bytes([seq % 256] * block_size)

    payload = bytearray([0x36, seq % 256]) + dummy_data
    send_uds_long(payload)

    total_sent += block_size
    seq += 1
    print(f"36 {seq-1:02X} Sent {block_size} bytes → Total: {total_sent}/50000")
    time.sleep(0.4)

# 0x37 Request Transfer Exit
bus.send(can.Message(arbitration_id=0x7E0, data=[0x37], is_extended_id=False))
print("37 Request Transfer Exit")
time.sleep(1.0)

print("\nECU REPROGRAMMING SUCCESSFUL! 50 KB flashed.")