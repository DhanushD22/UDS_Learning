#!/usr/bin/env python3
import can
import time

bus = can.interface.Bus(channel='vcan0', bustype='socketcan')

print("Starting UDS session...\n")

# 10 03 – Extended session
bus.send(can.Message(arbitration_id=0x7E0, data=[0x10, 0x03], is_extended_id=False))
print("→ 10 03  Extended session")
time.sleep(0.5)

# 27 01 – Request seed
bus.send(can.Message(arbitration_id=0x7E0, data=[0x27, 0x01], is_extended_id=False))
print("→ 27 01  Request seed")
time.sleep(0.5)

# 27 02 – Send key (mock correct key)
bus.send(can.Message(arbitration_id=0x7E0, data=[0x27, 0x02, 0x12, 0x34, 0x56, 0x78], is_extended_id=False))
print("→ 27 02  Send key")
time.sleep(0.5)

# 22 F1 90 – Read VIN
bus.send(can.Message(arbitration_id=0x7E0, data=[0x22, 0xF1, 0x90], is_extended_id=False))
print("→ 22 F1 90  Read VIN")
time.sleep(0.5)

# 19 01 08 – Report Number of DTC by Status Mask (testFailedThisCycle)
bus.send(can.Message(arbitration_id=0x7E0, data=[0x19, 0x01, 0x08], is_extended_id=False))
print("→ 19 01 08  Report Number of DTC by Status Mask")
time.sleep(0.7)

# 19 02 08 – Report DTC by Status Mask (list them)
bus.send(can.Message(arbitration_id=0x7E0, data=[0x19, 0x02, 0x08], is_extended_id=False))
print("→ 19 02 08  Report DTC by Status Mask")
time.sleep(1.0)


# 3E 00 – Tester present
bus.send(can.Message(arbitration_id=0x7E0, data=[0x3E, 0x00], is_extended_id=False))
print("→ 3E 00  Tester present")

print("\nUDS session completed! Check server terminal for ECU logs.")
