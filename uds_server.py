#!/usr/bin/env python3
import can
import time

bus = can.interface.Bus(channel='vcan0', bustype='socketcan', can_filters=[{"can_id": 0x7E0, "can_mask": 0x7FF}])

# Flashing simulation
flash_address = 0
flash_memory = bytearray()      # Will hold the received firmware
expected_length = 0
max_block_length = 4095         # We support up to 4095 bytes per TransferData
flashing_active = False
memory = {0xF190: b'VIN12345678901234'}

"""
A DTC comes in a string of five characters. So, for example, you might run into a code that says P0575. Let’s examine what each of these characters tells us.

The first letter tells us which of the four main parts is at fault.
P = Powertrain
B = Body
C = Chassis
U = Network
The second tells us whether we are looking at a generic OBD-II code or a manufacturer’s code. (If a manufacturer feels there isn’t a generic code covering a specific fault, they can add their own.) A zero denotes a generic code. 
The third character alerts us which vehicle’s system is at fault. Codes include:
1 = Fuel and Air Metering
2 = Fuel and Air Metering (injector circuit malfunction specific)
3 = Ignition System or Misfire
4 = Auxiliary Emissions Controls
5 = Vehicle Speed Control and Idle Control System
6 = Computer Auxiliary Outputs
7, 8, 9 = Various transmission and Gearbox faults
A, B, C = Hybrid Propulsion Faults 
The last two characters tell us the specific fault. These help pinpoint exactly where the problem is located and which part needs attention.
So in the case of P0575, we know that it’s a generic OBD-II powertrain fault. We also know that the specific fault relates to the vehicle speed control or idle control system. By consulting the list of OBD-II codes, we discover that it’s a problem with the cruise control input circuit. 
"""

# DTC Memory: 3-byte DTC → status byte
dtc_memory = {
    0x010000: 0x28,   # P0100 (full 3-byte)
    0x030100: 0x08,   # P0301
    0x042000: 0x2A,   # P0420
}

# Snapshot data: 3-byte DTC → record → {DataID: value}
snapshot_data = {
    0x010000: {0xFF: {0x04: 1800, 0x0C: 65, 0x0D: 2500}},  # P0100 RPM=1800, Speed=65, Load=25%
    0x030100: {0xFF: {0x04: 950,  0x0C: 0,  0x0D: 800}},    # P0301 idle misfire
    0x042000: {0xFF: {0x04: 3200, 0x0C: 120, 0x0D: 4000}},  # P0420 high load
}

# Extended data: 3-byte DTC → record → {DataID: value}
extended_data = {
    0x010000: {0x01: 12},  # occurrence counter
    0x030100: {0x01: 3},
    0x042000: {0x01: 45},
}

def send_response(data):
    if len(data) <= 8:
        bus.send(can.Message(arbitration_id=0x7E8, data=data, is_extended_id=False))
        return
    first_frame = bytearray([0x10 | (len(data) >> 8), len(data) & 0xFF]) + data[:6]
    bus.send(can.Message(arbitration_id=0x7E8, data=first_frame, is_extended_id=False))
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

    # ------------------ BASIC SERVICES ------------------
    if sid == 0x10:
        print(f"[ECU] ← 10 {data[1]:02X} Extended session")
        send_response(bytes([0x50, data[1]]))
        continue

    if sid == 0x27 and data[1] == 0x01:
        print("[ECU] ← 27 01 Request seed → sending CAFEBABE")
        send_response(bytes([0x67, 0x01, 0xCA, 0xFE, 0xBA, 0xBE]))
        continue
    if sid == 0x27 and data[1] == 0x02:
        if len(data) >= 6 and data[2:6] == b'\x12\x34\x56\x78':
            print("[ECU] ← 27 02 Key correct → ACCESS GRANTED")
            send_response(bytes([0x67, 0x02]))
        else:
            print("[ECU] ← 27 02 Wrong key!")
            send_response(bytes([0x7F, 0x27, 0x35]))
        continue

    if sid == 0x22:
        did = (data[1] << 8) | data[2]
        print(f"[ECU] ← 22 {did:04X} Read DID")
        if did == 0xF190:
            resp = bytes([0x62, data[1], data[2]]) + memory[0xF190]
            send_response(resp)
        else:
            send_response(bytes([0x7F, 0x22, 0x31]))
        continue

    if sid == 0x3E:
        print("[ECU] ← 3E 00 Tester present")
        send_response(bytes([0x7E, 0x00]))
        continue

    # ------------------ 0x19 DTC SERVICES ------------------
    if sid == 0x19:
        if len(data) < 2:
            send_response(bytes([0x7F, 0x19, 0x13]))
            continue
        subfunc = data[1]
        print(f"[ECU] ← 19 {subfunc:02X} Read DTC Information")

        if subfunc == 0x01:  # Number of DTC by Status Mask
            mask = data[2] if len(data) >= 3 else 0xFF
            count = sum(1 for s in dtc_memory.values() if (s & mask))
            resp = bytearray([0x59, 0x01, 0xFF, 0x02]) + count.to_bytes(2, 'big')
            send_response(resp)
            print(f"[ECU] → 59 01 DTC count = {count} (mask 0x{mask:02X})")
            continue

        if subfunc == 0x02:  # Report DTC by Status Mask
            mask = data[2] if len(data) >= 3 else 0xFF
            matching = [(d, s) for d, s in dtc_memory.items() if (s & mask)]
            payload = bytearray([0x59, 0x02, 0xFF, 0x02])
            for d, s in matching:
                payload.extend(d.to_bytes(3, 'big'))
                payload.append(s)
            send_response(payload)
            print(f"[ECU] → 59 02 Reported {len(matching)} DTC(s): {[f'P{d:04X}' for d,_ in matching]}")
            continue

        if subfunc == 0x04:  # Snapshot
            if len(data) < 6:
                send_response(bytes([0x7F, 0x19, 0x13]))
                continue
            dtc = (data[2] << 16) | (data[3] << 8) | data[4]
            rec = data[5]
            if dtc not in snapshot_data or rec not in snapshot_data[dtc]:
                send_response(bytes([0x7F, 0x19, 0x10]))
                continue
            payload = bytearray([0x59, 0x04]) + dtc.to_bytes(3, 'big') + bytes([rec])
            for did, val in snapshot_data[dtc][rec].items():
                payload.append(did)
                payload.extend(val.to_bytes(2, 'big'))
            send_response(payload)
            print(f"[ECU] → 59 04 Snapshot for P{dtc:04X} (Rec 0x{rec:02X}): RPM={snapshot_data[dtc][rec].get(0x04)}")
            continue

        if subfunc == 0x06:  # Extended Data
            if len(data) < 6:
                send_response(bytes([0x7F, 0x19, 0x13]))
                continue
            dtc = (data[2] << 16) | (data[3] << 8) | data[4]
            rec = data[5]
            if dtc not in extended_data or rec not in extended_data[dtc]:
                send_response(bytes([0x7F, 0x19, 0x10]))
                continue
            payload = bytearray([0x59, 0x06]) + dtc.to_bytes(3, 'big') + bytes([rec, 0x01, extended_data[dtc][rec]])
            send_response(payload)
            print(f"[ECU] → 59 06 Extended data for P{dtc:04X}: occurrence={extended_data[dtc][rec]}")
            continue

        send_response(bytes([0x7F, 0x19, 0x12]))  # sub-function not supported
        continue
    

        # ------------------ ECU Reset (0x11) ------------------
    if sid == 0x11:
        subfunc = data[1]
        if subfunc in [0x01, 0x03]:
            print(f"[ECU] ← 11 {subfunc:02X} ECU Reset requested")
            # Positive response: 0x51 + subfunction
            send_response(bytes([0x51, subfunc]))
            print("[ECU] → 51 {:02X} Resetting ECU... (simulated)".format(subfunc))
            if subfunc == 0x01:
                print("[ECU] Simulated power-on reset – all sessions lost")
            else:
                print("[ECU] Reset complete – diagnostic session preserved")
        else:
            send_response(bytes([0x7F, 0x11, 0x12]))  # subFunctionNotSupported
        continue

    # ------------------ Routine Control (0x31) ------------------
    if sid == 0x31:
        if len(data) < 4:
            send_response(bytes([0x7F, 0x31, 0x13]))
            continue
        subfunc = data[1]
        routine_id = (data[2] << 8) | data[3]
        print(f"[ECU] ← 31 {subfunc:02X} {routine_id:04X} Routine Control")

        if routine_id == 0xFFFB:  # Self-test / Clear DTCs
            if subfunc == 0x01:
                print("[ECU] Starting self-test routine...")
                send_response(bytes([0x71, 0x01, 0xFF, 0xFB]))
                print("[ECU] → 71 01 FFFB Self-test started")
            elif subfunc == 0x03:
                print("[ECU] Stopping self-test routine...")
                send_response(bytes([0x71, 0x03, 0xFF, 0xFB]))
                print("[ECU] → 71 03 FFFB Self-test stopped")
            else:
                send_response(bytes([0x7F, 0x31, 0x12]))
        else:
            send_response(bytes([0x7F, 0x31, 0x31]))  # requestOutOfRange
        continue

        # ------------------ 0x34 Request Download ------------------
    if sid == 0x34:
        if len(data) < 6:
            send_response(bytes([0x7F, 0x34, 0x13]))
            continue
        print(f"[ECU] ← 34 00 Request Download")

        # Parse length and address (simplified: assume 4-byte len + 4-byte addr)
        length = int.from_bytes(data[2:6], 'big')
        address = int.from_bytes(data[6:10], 'big') if len(data) >= 10 else 0x08010000

        flash_address = address
        expected_length = length
        flash_memory = bytearray()  # Reset buffer
        flashing_active = True

        # Response: 74 00 [maxNumberOfBlockLength (2 bytes)]
        resp = bytearray([0x74, 0x00])
        resp.extend(max_block_length.to_bytes(2, 'big'))
        send_response(resp)
        print(f"[ECU] → 74 00 Download accepted: {length} bytes @ 0x{address:08X}")
        print(f"[ECU] Ready to receive {length} bytes (max {max_block_length} per block)")
        continue

    # ------------------ 0x36 Transfer Data ------------------
    if sid == 0x36:
        if not flashing_active:
            send_response(bytes([0x7F, 0x36, 0x24]))  # requestSequenceError
            continue

        seq_num = data[1]
        chunk = data[2:]

        flash_memory.extend(chunk)
        received = len(flash_memory)
        print(f"[ECU] ← 36 {seq_num:02X} Received chunk {len(chunk)} bytes → Total: {received}/{expected_length}")

        # Positive response: 76 + sequence number
        send_response(bytes([0x76, seq_num]))

        if received >= expected_length:
            print(f"[ECU] FLASHING COMPLETE! {received} bytes written to 0x{flash_address:08X}")
            flashing_active = False
        continue

    # ------------------ 0x37 Request Transfer Exit ------------------
    if sid == 0x37:
        if flashing_active:
            print(f"[ECU] ← 37 Request Transfer Exit (partial)")
        else:
            print(f"[ECU] ← 37 Request Transfer Exit – {len(flash_memory)} bytes flashed")
        send_response(bytes([0x77]))
        flashing_active = False
        continue