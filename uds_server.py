#!/usr/bin/env python3
import can
import time

bus = can.interface.Bus(channel='vcan0', bustype='socketcan', can_filters=[{"can_id": 0x7E0, "can_mask": 0x7FF}])

memory = {0xF190: b'VIN12345678901234'}

# DTC Memory – Format: DTC (3-byte int) → status byte
# Example real-world DTCs:
# P0100 = Mass Air Flow Circuit Malfunction
# P0301 = Cylinder 1 Misfire Detected
# P0420 = Catalyst System Efficiency Below Threshold
dtc_memory = {
    0x0100: 0x28,   # testFailed + confirmed
    0x0301: 0x08,   # testFailed this cycle only
    0x0420: 0x2A,   # testFailed + confirmed + warningIndicatorRequested
}

def send_response(data):
    # Split long responses into 8-byte chunks (simple ISO-TP like)
    if len(data) <= 8:
        bus.send(can.Message(arbitration_id=0x7E8, data=data, is_extended_id=False))
        return

    # First frame (has length in first byte)
    first_frame = bytearray([0x10 | (len(data) >> 8), len(data) & 0xFF]) + data[:6]
    bus.send(can.Message(arbitration_id=0x7E8, data=first_frame, is_extended_id=False))
    time.sleep(0.01)

    # Flow control from tester (we assume tester sends 30 00 00...)
    # In real ISO-TP we'd wait, but for demo we just continue after tiny delay
    time.sleep(0.05)

    remaining = data[6:]
    seq = 0x21
    for i in range(0, len(remaining), 7):
        chunk = remaining[i:i+7]
        frame = bytearray([seq]) + chunk + b'\x00'*(7-len(chunk))
        bus.send(can.Message(arbitration_id=0x7E8, data=frame[:8], is_extended_id=False))
        seq = 0x20 if seq == 0x2F else seq + 1
        time.sleep(0.01)

print("Virtual ECU listening on vcan0 (0x7E0 → 0x7E8) – multi-frame ready")

while True:
    msg = bus.recv(timeout=10)
    if not msg or msg.arbitration_id != 0x7E0:
        continue

    data = msg.data
    sid = data[0]

    if sid == 0x10:
        print(f"[ECU] ← 10 {data[1]:02X} Extended session")
        send_response(bytes([0x50, data[1]]))

    elif sid == 0x27 and data[1] == 0x01:
        print("[ECU] ← 27 01 Request seed → sending CAFEBABE")
        send_response(bytes([0x67, 0x01, 0xCA, 0xFE, 0xBA, 0xBE]))

    elif sid == 0x27 and data[1] == 0x02:
        if data[2:6] == b'\x12\x34\x56\x78':
            print("[ECU] ← 27 02 Key correct → ACCESS GRANTED")
            send_response(bytes([0x67, 0x02]))
        else:
            print("[ECU] ← 27 02 Wrong key!")
            send_response(bytes([0x7F, 0x27, 0x35]))

    elif sid == 0x22:
        did = (data[1] << 8) | data[2]
        print(f"[ECU] ← 22 {did:04X} Read DID")
        if did == 0xF190:
            resp = bytes([0x62, data[1], data[2]]) + memory[0xF190]
            send_response(resp)
        else:
            send_response(bytes([0x7F, 0x22, 0x31]))

    elif sid == 0x3E:
        print("[ECU] ← 3E 00 Tester present")
        send_response(bytes([0x7E, 0x00]))
    
    elif sid == 0x19:  # ReadDTCInformation
        subfunc = data[1]
        print(f"[ECU] ← 19 {subfunc:02X}  Read DTC Information")

        if subfunc == 0x01:  # Report Number of DTC by Status Mask
            status_mask = data[2] if len(data) >= 3 else 0xFF
            count = sum(1 for status in dtc_memory.values() if (status & status_mask))
            # Response: 59 01 [AvailMask] [Format=0x02] [Count 2 bytes]
            resp = bytes([0x59, 0x01, 0xFF, 0x02]) + count.to_bytes(2, 'big')
            send_response(resp)
            print(f"[ECU] → 59 01  DTC count = {count} for mask 0x{status_mask:02X}")

        elif subfunc == 0x02:  # Report DTC by Status Mask
            status_mask = data[2] if len(data) >= 3 else 0xFF
            matching_dtcs = [(dtc, status) for dtc, status in dtc_memory.items() if (status & status_mask)]
            if not matching_dtcs:
                send_response(bytes([0x7F, 0x19, 0x78]))  # requestCorrectlyReceived-ResponsePending (or 0x10 no DTC)
                continue

            # Build response: 59 02 [AvailMask] [Format=0x02] + [DTC(3)+Status(1)] for each
            payload = bytearray([0x59, 0x02, 0xFF, 0x02])  # Availability mask + 3-byte DTC format
            for dtc, status in matching_dtcs:
                payload.extend(dtc.to_bytes(3, 'big'))
                payload.append(status)
            send_response(payload)
            print(f"[ECU] → 59 02  Reported {len(matching_dtcs)} DTC(s): {[f'P{dtc:04X}' for dtc,_ in matching_dtcs]}")
