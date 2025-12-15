#!/usr/bin/env python3
import can
import time

bus = can.interface.Bus(
    channel='vcan0',
    bustype='socketcan',
    can_filters=[{"can_id": 0x7E0, "can_mask": 0x7FF}]
)

#ECU MEMORY / SIMULATION DATA

flash_address = 0
flash_memory = bytearray()
expected_length = 0
max_block_length = 4095
flashing_active = False

memory = {0xF190: b'VIN12345678901234'}

dtc_memory = {
    0x010000: 0x28,
    0x030100: 0x08,
    0x042000: 0x2A,
}

snapshot_data = {
    0x010000: {0xFF: {0x04: 1800, 0x0C: 65,   0x0D: 2500}},
    0x030100: {0xFF: {0x04: 950,  0x0C: 0,    0x0D: 800}},
    0x042000: {0xFF: {0x04: 3200, 0x0C: 120,  0x0D: 4000}},
}

extended_data = {
    0x010000: {0x01: 12},
    0x030100: {0x01: 3},
    0x042000: {0x01: 45},
}


# ISO-TP RESPONSE API

def send_response(data):
    """Send UDS Data using ISO-TP SF/FF/CF correctly"""

    # ---------------- SINGLE FRAME ----------------
    if len(data) <= 7:
        sf = bytearray([len(data)])  # PCI
        sf.extend(data)
        sf.extend(b'\x00' * (8 - len(sf)))
        msg = can.Message(arbitration_id=0x7E8, data=sf, is_extended_id=False)
        bus.send(msg)
        print(msg)
        return

    # ---------------- FIRST FRAME ----------------
    total_len = len(data)
    ff = bytearray()
    ff.append(0x10 | (total_len >> 8))
    ff.append(total_len & 0xFF)
    ff.extend(data[:6])

    msg = can.Message(arbitration_id=0x7E8, data=ff, is_extended_id=False)
    bus.send(msg)
    print(msg)
    time.sleep(0.01)

    # ---------------- CONSECUTIVE FRAMES ----------------
    remaining = data[6:]
    seq = 1

    for i in range(0, len(remaining), 7):
        chunk = remaining[i:i+7]
        cf = bytearray([0x20 | (seq & 0x0F)])
        cf.extend(chunk)
        cf.extend(b'\x00' * (8 - len(cf)))

        msg = can.Message(arbitration_id=0x7E8, data=cf, is_extended_id=False)
        bus.send(msg)
        print(msg)

        seq = (seq + 1) & 0x0F
        time.sleep(0.01)

print("Virtual ECU listening on vcan0 (0x7E0 → 0x7E8) – multi-frame ready")


#MAIN LOOP

while True:
    msg = bus.recv(timeout=10)
    if not msg or msg.arbitration_id != 0x7E0:
        continue

    data = msg.data
    pci_type = data[0] >> 4

    # ------------------ ISO-TP SINGLE FRAME ------------------
    if pci_type == 0x0:
        length = data[0] & 0x0F
        payload = data[1:1+length]

    # ------------------ ISO-TP FIRST FRAME -------------------
    elif pci_type == 0x1:
        total_len = ((data[0] & 0x0F) << 8) | data[1]
        payload = data[2:]  # Only the first 6 bytes

    # ------------------ ISO-TP CONSECUTIVE FRAME --------------
    elif pci_type == 0x2:
        payload = data[1:]

    else:
        continue

    sid = payload[0]

    # =================================================================================
    #                               UDS HANDLING LOGIC
    # =================================================================================

    # ---------------------- 0x10 Diagnostic Session ----------------------
    if sid == 0x10:
        sub = payload[1]
        print(f"[ECU] ← 10 {sub:02X} Diagnostic Session")
        send_response(bytes([0x50, sub]))
        continue

    # ---------------------- 0x27 Security Access ----------------------
    if sid == 0x27 and payload[1] == 0x01:
        print("[ECU] ← 27 01 Request Seed")
        send_response(bytes([0x67, 0x01, 0xCA, 0xFE, 0xBA, 0xBE]))
        continue

    if sid == 0x27 and payload[1] == 0x02:
        key = payload[2:6]
        if key == b'\x12\x34\x56\x78':
            send_response(bytes([0x67, 0x02]))
        else:
            send_response(bytes([0x7F, 0x27, 0x35]))
        continue

    # ---------------------- 0x22 ReadDataByIdentifier ----------------------
    if sid == 0x22:
        did = (payload[1] << 8) | payload[2]
        print(f"[ECU] ← 22 {did:04X} Read DID")

        if did == 0xF190:
            vin = memory[0xF190]
            resp = bytes([0x62, payload[1], payload[2]]) + vin
            send_response(resp)
        else:
            send_response(bytes([0x7F, 0x22, 0x31]))
        continue

    # ---------------------- 0x19 DTC Services ----------------------
    if sid == 0x19:
        sub = payload[1]
        print(f"[ECU] ← 19 {sub:02X} DTC Service")

        # 19 01 — DTC count
        if sub == 0x01:
            mask = payload[2]
            count = sum(1 for s in dtc_memory.values() if (s & mask))
            resp = bytearray([0x59, 0x01, mask, 0x02]) + count.to_bytes(2, 'big')
            send_response(resp)
            continue

        # 19 02 — DTC list
        if sub == 0x02:
            mask = payload[2]
            resp = bytearray([0x59, 0x02, mask, 0x02])
            for dtc, status in dtc_memory.items():
                if status & mask:
                    resp.extend(dtc.to_bytes(3, 'big'))
                    resp.append(status)
            send_response(resp)
            continue

        # 19 04 — Snapshot
        if sub == 0x04:
            dtc = (payload[2] << 16) | (payload[3] << 8) | payload[4]
            rec = payload[5]
            if dtc not in snapshot_data:
                send_response(bytes([0x7F, 0x19, 0x10]))
                continue
            resp = bytearray([0x59, 0x04]) + dtc.to_bytes(3, 'big') + bytes([rec])
            for did, val in snapshot_data[dtc][rec].items():
                resp.append(did)
                resp.extend(val.to_bytes(2, 'big'))
            send_response(resp)
            continue

        # 19 06 — Extended data
        if sub == 0x06:
            dtc = (payload[2] << 16) | (payload[3] << 8) | payload[4]
            rec = payload[5]
            resp = bytearray([0x59, 0x06]) + dtc.to_bytes(3, 'big') \
                   + bytes([rec, 0x01, extended_data[dtc][rec]])
            send_response(resp)
            continue

        continue

    # ---------------------- 0x11 ECU Reset ----------------------
    if sid == 0x11:
        sub = payload[1]
        print(f"[ECU] ← 11 {sub:02X} ECU Reset")
        send_response(bytes([0x51, sub]))
        continue

    # ---------------------- 0x34 Request Download ----------------------
    if sid == 0x34:
        length = int.from_bytes(payload[2:6], 'big')
        expected_length = length
        flash_memory = bytearray()
        flashing_active = True

        resp = bytearray([0x74, 0x00]) + max_block_length.to_bytes(2, 'big')
        send_response(resp)
        continue

    # ---------------------- 0x36 Transfer Data ----------------------
    if sid == 0x36:
        seq = payload[1]
        chunk = payload[2:]
        flash_memory.extend(chunk)
        send_response(bytes([0x76, seq]))
        continue

    # ---------------------- 0x37 Request Transfer Exit ----------------------
    if sid == 0x37:
        send_response(bytes([0x77]))
        flashing_active = False
        continue
