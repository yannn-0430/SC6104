# oracle/app.py
# Simple Flask oracle that runs a linear 128-bit RNG.
# Each call to /get_output returns a 128-bit hex string (32 hex chars).
# /validate accepts a hex and returns success if matches next output.

from flask import Flask, jsonify, request
import os
import threading

app = Flask(__name__)

# We'll implement a simple linear 128-bit LFSR-like generator (XOR & shifts),
# that updates a 128-bit state and returns the state as output.
# Represent state as Python int in [0, 2^128).

MASK128 = (1 << 128) - 1

def rotate_left(x, r, bits=128):
    r %= bits
    return ((x << r) & ((1 << bits) - 1)) | (x >> (bits - r))

class Linear128RNG:
    def __init__(self, seed=None):
        if seed is None:
            # seed from os.urandom (secure). For demo we can set deterministic.
            seed = int.from_bytes(os.urandom(16), 'big')
        self.state = seed & MASK128
    def next_raw(self):
        # a linear update (all XORs and shifts -> linear over GF(2))
        s = self.state
        # example linear transform: s = (s ^ (s << 7) ^ (s >> 13) ^ rotate_left(s, 37)) & MASK128
        t = s ^ ((s << 7) & MASK128) ^ (s >> 13) ^ rotate_left(s, 37)
        t &= MASK128
        self.state = t
        # output: full 128-bit state (we return the integer)
        return t

RNG = Linear128RNG(seed=0x1234567890abcdef1234567890abcdef)  # deterministic seed for reproducibility

from flask import Response

@app.route('/get_output', methods=['GET'])
def get_output():
    out = RNG.next_raw()
    # return 32-hex-digit string (128 bits)
    return jsonify({'output': format(out, '032x')})

@app.route('/validate', methods=['POST'])
def validate():
    data = request.get_json()
    if not data or 'candidate' not in data:
        return jsonify({'ok': False, 'reason': 'need candidate'}), 400
    candidate_hex = data['candidate']
    try:
        candidate = int(candidate_hex, 16)
    except:
        return jsonify({'ok': False, 'reason': 'bad hex'}), 400
    # compute next true output without advancing RNG permanently: peek
    # For simplicity, advance and accept; in real demo this simulates consuming token.
    true = RNG.next_raw()
    ok = (candidate & MASK128) == (true & MASK128)
    return jsonify({'ok': ok, 'expected': format(true, '032x')})

if __name__ == '__main__':
    # Use a thread to run Flask in background or run directly.
    app.run(host='127.0.0.1', port=5000, debug=False)
