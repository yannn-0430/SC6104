import os
import hmac
import hashlib

MASK128 = (1 << 128) - 1

class HMAC_DRBG_Simple:
    def __init__(self, key=None, seed=None):
        # key: bytes
        # seed: 128-bit int or None
        if key is None:
            # demo: fixed key for reproducible demo; in production key must be secret
            key = b'demo_hmac_key_16b'
        self.key = key
        if seed is None:
            seed = int.from_bytes(os.urandom(16), 'big')
        self.state = seed & MASK128

    def _hmac_bytes(self, data_bytes):
        return hmac.new(self.key, data_bytes, hashlib.sha256).digest()  # 32 bytes

    def next_raw(self):
        # compute mac = HMAC(key, state_bytes)
        state_bytes = self.state.to_bytes(16, 'big')
        mac = self._hmac_bytes(state_bytes)  # 256-bit output
        # update internal state as integer derived from mac (nonlinear)
        new_state = int.from_bytes(mac[:16], 'big')  # take first 128 bits of mac
        self.state = new_state & MASK128
        # return full mac as int so caller can decide to truncate bits
        return int.from_bytes(mac, 'big')  # 256-bit int