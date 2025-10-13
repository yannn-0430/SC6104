# oracle/rng128.py
# 128-bit linear RNG implementation used by oracle/app.py
# State: single 128-bit integer.
# Update: linear transform over GF(2) using XORs, shifts and rotate (all linear w.r.t bits).

MASK128 = (1 << 128) - 1

def rotl(x, r, bits=128):
    r %= bits
    return ((x << r) & ((1 << bits) - 1)) | (x >> (bits - r))

class Linear128RNG:
    def __init__(self, seed=None):
        import os
        if seed is None:
            seed = int.from_bytes(os.urandom(16), 'big')
        self.state = seed & MASK128

    def next_raw(self):
        s = self.state
        # linear transform (all ops are XOR/shift/rot -> linear over GF(2))
        t = s
        t ^= ((s << 7) & MASK128)
        t ^= (s >> 13)
        t ^= rotl(s, 37)
        t &= MASK128
        self.state = t
        return t

    def peek_next(self):
        # return next value without consuming (for validation convenience)
        s = self.state
        t = s
        t ^= ((s << 7) & MASK128)
        t ^= (s >> 13)
        t ^= rotl(s, 37)
        t &= MASK128
        return t
