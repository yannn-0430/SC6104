# attacker/recover_128bit.py
# Query oracle for outputs, build linear system over GF(2), solve for 128-bit initial state,
# then predict next output and validate via /validate

import requests
import math
from collections import deque
import argparse
import time

ORACLE = 'http://127.0.0.1:5000'
BITS = 128

def int_to_bits_lsb(x, n):
    return [(x >> i) & 1 for i in range(n)]

def bits_to_int_lsb(bits):
    x = 0
    for i,b in enumerate(bits):
        if b:
            x |= (1 << i)
    return x

# Build symbolic mapping for the linear transform used in oracle.
# We'll track how each output bit at each step depends on initial 128 bits.
def rotl_mask(x_mask, r, bits=128):
    r %= bits
    left = (x_mask << r) & ((1<<bits)-1)
    right = x_mask >> (bits - r)
    return (left | right) & ((1<<bits)-1)

def build_maps(steps):
    # state_coeffs[i] is an integer mask (128-bit) telling which initial bits
    # contribute to bit i of current state.
    state_coeffs = [1 << i for i in range(BITS)]
    maps = []
    for step in range(steps):
        maps.append(state_coeffs.copy())
        # advance state by linear transform: t = s ^ (s<<7) ^ (s>>13) ^ rotl(s,37)
        new_coeffs = [0] * BITS
        for i in range(BITS):
            coeff = state_coeffs[i]
            # s contributes to bit i
            new_coeffs[i] ^= coeff
            # s << 7 contributes to bit i+7
            j = i + 7
            if j < BITS:
                new_coeffs[j] ^= coeff
            # s >> 13 contributes to bit i-13
            j2 = i - 13
            if j2 >= 0:
                new_coeffs[j2] ^= coeff
            # rotl by 37 contributes to bit (i+37)%128
            j3 = (i + 37) % BITS
            new_coeffs[j3] ^= coeff
        state_coeffs = new_coeffs
    return maps

def construct_equations(observed, output_bits):
    # observed: list of integers (each is truncated output if OUTPUT_BITS<128)
    steps = len(observed)
    maps = build_maps(steps)
    rows = []  # integer masks (length 128)
    rhs = []
    # output_bits is number of bits returned by oracle (<=128)
    for t, out in enumerate(observed):
        for b in range(output_bits):
            mask = maps[t][b]  # which initial bits affect this output bit
            if mask == 0:
                continue
            rows.append(mask)
            rhs.append((out >> b) & 1)
    return rows, rhs

# Gaussian elimination over GF(2) with integer row masks of <=128 bits
def solve_gf2(rows, rhs):
    rows = rows[:]  # copy
    rhs = rhs[:]
    n_eq = len(rows)
    pivot = {}
    row = 0
    for col in reversed(range(BITS)):
        sel = None
        for r in range(row, n_eq):
            if (rows[r] >> col) & 1:
                sel = r
                break
        if sel is None:
            continue
        rows[row], rows[sel] = rows[sel], rows[row]
        rhs[row], rhs[sel] = rhs[sel], rhs[row]
        pivot[col] = row
        # eliminate other rows
        for r in range(n_eq):
            if r != row and ((rows[r] >> col) & 1):
                rows[r] ^= rows[row]
                rhs[r] ^= rhs[row]
        row += 1
        if row >= n_eq:
            break
    # form solution
    sol = 0
    for col, r in pivot.items():
        if rhs[r]:
            sol |= (1 << col)
    # verify
    for rmask, rval in zip(rows, rhs):
        lhs = bin(rmask & sol).count('1') & 1
        if lhs != rval:
            return None
    return sol

def query_oracle(n, output_bits):
    outs = []
    for _ in range(n):
        r = requests.get(ORACLE + '/get_output', timeout=5)
        o = r.json()['output']
        outs.append(int(o, 16))
    return outs

def predict_next_from_state(state, steps=1):
    # apply same linear transform steps times
    def rotl(x, r, bits=128):
        r %= bits
        return ((x << r) & ((1<<bits)-1)) | (x >> (bits - r))
    st = state
    for _ in range(steps):
        t = st
        t ^= ((st << 7) & ((1<<128)-1))
        t ^= (st >> 13)
        t ^= rotl(st, 37)
        t &= ((1<<128)-1)
        st = t
    return st

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=2, help='number of outputs to collect')
    parser.add_argument('--output_bits', type=int, default=128, help='bits returned by oracle (<=128)')
    args = parser.parse_args()

    t0 = time.time()
    print(f"[attacker] Querying oracle for {args.samples} outputs (output_bits={args.output_bits})...")
    obs = query_oracle(args.samples, args.output_bits)
    for i,o in enumerate(obs):
        print(f" obs[{i}]: {format(o, '0{}x'.format((args.output_bits+3)//4))}")
    rows, rhs = construct_equations(obs, args.output_bits)
    print(f"[attacker] Constructed {len(rows)} linear equations. Solving...")
    sol = solve_gf2(rows, rhs)
    if sol is None:
        print("[attacker] Failed to find unique solution. Try increasing samples or output_bits.")
    else:
        print("[attacker] Recovered initial 128-bit state (hex):")
        print(format(sol & ((1<<128)-1), '032x'))
        # simulate forward by len(obs) steps to get next output
        predicted = predict_next_from_state(sol, steps=len(obs))
        print("[attacker] Predicted next output (full 128-bit hex):")
        print(format(predicted & ((1<<128)-1), '032x'))
        # if oracle returns truncated bits, truncate to compare
        if args.output_bits < 128:
            if args.output_bits == 0:
                truncated = 0
            else:
                truncated = (predicted >> (128 - args.output_bits)) & ((1<<args.output_bits)-1)
            cand_hex = format(truncated, '0{}x'.format((args.output_bits+3)//4))
        else:
            cand_hex = format(predicted & ((1<<128)-1), '032x')
        # validate with oracle
        resp = requests.post(ORACLE + '/validate', json={'candidate': cand_hex})
        print("[attacker] Validate response:", resp.json())
    print(f"[attacker] Done in {time.time()-t0:.2f}s")
