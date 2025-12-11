def calculate_key(seed: int) -> int:
    """Simple example algorithm used by many OEMs (XOR + rotate)"""
    key = seed ^ 0xDEADBEEF
    key = ((key << 13) | (key >> 19)) & 0xFFFFFFFF
    return key & 0xFFFFFFFF
