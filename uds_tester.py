#!/usr/bin/env python3
import can
import time

bus = can.interface.Bus(
    channel="vcan0",
    bustype="socketcan"
)

TX_ID = 0x7E0   # tester → ECU
RX_ID = 0x7E8   # ECU → tester

print("UDS Tester (Manual ISO-TP FF / CF / FC Mode)\n")

# -------------------------------------------------------
# SEND UDS REQUEST (manual ISO-TP)
# -------------------------------------------------------
def send_uds(payload):
    # --- SINGLE FRAME ---
    if len(payload) <= 7:
        frame = bytearray([0x00 | len(payload)]) + payload + b"\x00"*(7-len(payload))
        bus.send(can.Message(arbitration_id=TX_ID, data=frame, is_extended_id=False))
        print(f"→ SF: {frame.hex().upper()}")
        return

    # --- FIRST FRAME ---
    length = len(payload)
    FF = bytearray()
    FF.append(0x10 | (length >> 8))   # high nibble=1 → FF
    FF.append(length & 0xFF)
    FF.extend(payload[:6])            # first 6 bytes
    bus.send(can.Message(arbitration_id=TX_ID, data=FF, is_extended_id=False))
    print(f"→ FF: {FF.hex().upper()}")

    # --- SEND FLOW CONTROL (tester → ECU) ---
    FC = bytes([0x30, 0x00, 0x00] + [0x00]*5)
    bus.send(can.Message(arbitration_id=TX_ID, data=FC, is_extended_id=False))
    print(f"→ FC: {FC.hex().upper()}")

    # --- SEND CONSECUTIVE FRAMES ---
    seq = 1
    remaining = payload[6:]

    for i in range(0, len(remaining), 7):
        chunk = remaining[i:i+7]
        CF = bytearray([0x20 | seq]) + chunk + b"\x00"*(7-len(chunk))
        bus.send(can.Message(arbitration_id=TX_ID, data=CF, is_extended_id=False))
        print(f"→ CF: {CF.hex().upper()}")
        seq = (seq + 1) & 0x0F
        time.sleep(0.01)

# -------------------------------------------------------
# RECEIVE UDS RESPONSE (manual ISO-TP)
# -------------------------------------------------------
def recv_uds(timeout=2.0):
    start = time.time()
    buffer = bytearray()
    expected_len = None
    seq_expected = 1

    while time.time() - start < timeout:
        msg = bus.recv(0.1)
        if not msg:
            continue

        data = msg.data
        pci = data[0]

        # SINGLE FRAME
        if pci >> 4 == 0x0:
            length = pci & 0x0F
            payload = data[1:1+length]
            print(f"← SF: {data.hex().upper()}")
            return payload

        # FIRST FRAME
        if pci >> 4 == 0x1:
            expected_len = ((pci & 0x0F) << 8) | data[1]
            buffer.extend(data[2:8])
            print(f"← FF: {data.hex().upper()}  (Total={expected_len})")

            # send FC
            FC = bytes([0x30, 0x00, 0x00] + [0x00]*5) 
            bus.send(can.Message(arbitration_id=TX_ID, data=FC, is_extended_id=False))
            print(f"→ FC: {FC.hex().upper()}")
            continue

        # CONSECUTIVE FRAME
        if pci >> 4 == 0x2:
            seq = pci & 0x0F
            buffer.extend(data[1:8])
            print(f"← CF[{seq}]: {data.hex().upper()}")

            if expected_len and len(buffer) >= expected_len:
                return buffer[:expected_len]

    print("← Timeout – No response")
    return None

# ---------------------- TEST CASES -----------------------------

def uds_request(payload):
    send_uds(payload)
    resp = recv_uds()
    if resp:
        print("   UDS Response:", resp.hex().upper())
    return resp


print("→ 10 03 Diagnostic Session")
uds_request(b'\x10\x03')

print("→ 27 01 Request Seed")
seed = uds_request(b'\x27\x01')

print("→ 22 F1 90 Read VIN")
vin = uds_request(b'\x22\xF1\x90')

print("→ 19 01 08 DTC Count")
uds_request(b'\x19\x01\x08')

print("→ 19 02 08 Report DTCs")
uds_request(b'\x19\x02\x08')

print("→ 19 04 Snapshot for P0100")
uds_request(b'\x19\x04\x01\x00\x00\xFF')

print("→ 11 03 ECU Reset")
uds_request(b'\x11\x03')
