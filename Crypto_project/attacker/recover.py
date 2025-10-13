# attacker/recover_128bit.py
# Attacker that queries oracle /get_output several times, constructs linear equations
# over GF(2) to recover initial 128-bit state, then predicts next output.

import requests
from math import ceil

ORACLE = 'http://127.0.0.1:5000'

MASK128 = (1 << 128) - 1

def int_to_bits(x, n):
    return [(x >> i) & 1 for i in range(n)]  # LSB first

def bits_to_int(bits):
    x = 0
    for i,b in enumerate(bits):
        if b:
            x |= (1 << i)
    return x

# We must model the RNG linear transform used in oracle.
# To reconstruct state: we express each observed output bit as linear combination of initial state bits.
# Approach: symbolically propagate basis vectors:
def build_symbolic_map(steps):
    # Represent basis vectors as integers of 128 bits: e0 = 1<<0, e1 = 1<<1, ...
    # We'll compute for each time step t the mapping from initial state to the output bits (full 128 bits).
    # Returns list of length = steps, each entry is a list of 128 integers representing columns:
    maps = []
    # initialize basis: state = vector of 128 basis vectors -> represented as integer with single bit set
    basis = [1 << i for i in range(128)]
    # state as list of 128-bit coefficients for current state words: state_coeffs is length 128 where each element is int mask
    state_coeffs = basis[:]  # at time 0, bit i corresponds to basis[i]
    for step in range(steps):
        # output is the full state (in oracle). So the mapping from initial bits to output bits is state_coeffs itself.
        # For convenience, we store mapping as list of 128 ints, where mapping[j] is integer mask (128 bits)
        maps.append(state_coeffs.copy())
        # Now advance state: apply linear transform t = s ^ (s<<7) ^ (s>>13) ^ rotl(s,37)
        # We must compute how each bit of new state depends on initial bits.
        new_state_coeffs = [0] * 128
        # For all bits b in 0..127, compute contributions:
        for i in range(128):
            # s bit i contributes to:
            # - s ^ (s<<7): to bit i (s), bit i+7 (from <<7) if i+7<128
            # - (s>>13) contributes to bit i-13 if i-13>=0
            # - rotl(s,37): contributes to bit (i+37)%128
            # We'll collect coefficients by XORing the corresponding basis masks.
            mask = 0
            # original s contributes to bit i
            mask ^= state_coeffs[i]
            # s << 7 contributes to bit i+7 (i maps to i+7)
            j = i + 7
            if j < 128:
                new_state_coeffs[j] ^= state_coeffs[i]
            else:
                # out-of-range simply ignored for << beyond 128 (we masked in oracle)
                pass
            # s >> 13 contributes to bit i-13
            j2 = i - 13
            if j2 >= 0:
                new_state_coeffs[j2] ^= state_coeffs[i]
            # rotl: bit i maps to (i+37) % 128
            j3 = (i + 37) % 128
            new_state_coeffs[j3] ^= state_coeffs[i]
            # and we also had mask (the original s) contribute to bit i:
            new_state_coeffs[i] ^= state_coeffs[i]
        # Now new_state_coeffs ready
        state_coeffs = new_state_coeffs
    return maps  # maps[step][bit_index] -> integer mask of length 128 indicating which initial bits affect that output bit.

# Helper: construct linear system from observed outputs
def construct_system(observed_outputs):
    # observed_outputs: list of integers (each is 128-bit output)
    steps = len(observed_outputs)
    maps = build_symbolic_map(steps)
    # We'll create equations: for each output bit position b (0..127) at time t,
    # sum_{i in initial bits where maps[t][b] has bit i set} x_i = observed_bit (mod 2)
    rows = []
    rhs = []
    for t, out in enumerate(observed_outputs):
        for b in range(128):
            mask = maps[t][b]  # integer mask: which initial bits contribute to this output bit
            if mask == 0:
                continue
            bit = (out >> b) & 1
            rows.append(mask)
            rhs.append(bit)
    return rows, rhs

# Gaussian elimination over GF(2) with rows as integer masks (length 128)
def solve_gf2(rows, rhs):
    n_eq = len(rows)
    # copy
    rows = rows[:]
    rhs = rhs[:]
    pivot_pos = {}
    row = 0
    for col in reversed(range(128)):  # try to pivot from high to low (arbitrary)
        # find a row with bit col set
        sel = None
        for r in range(row, n_eq):
            if (rows[r] >> col) & 1:
                sel = r
                break
        if sel is None:
            continue
        # swap
        rows[row], rows[sel] = rows[sel], rows[row]
        rhs[row], rhs[sel] = rhs[sel], rhs[row]
        pivot_pos[col] = row
        # eliminate others
        for r in range(n_eq):
            if r != row and ((rows[r] >> col) & 1):
                rows[r] ^= rows[row]
                rhs[r] ^= rhs[row]
        row += 1
        if row >= n_eq:
            break
    # back-substitute to get solution vector of 128 bits (unknowns)
    sol = 0
    for col, r in pivot_pos.items():
        if rhs[r]:
            sol |= (1 << col)
    # verify solution
    for r_mask, r_val in zip(rows, rhs):
        lhs = bin(r_mask & sol).count('1') & 1
        if lhs != r_val:
            # inconsistent or underdetermined; return None
            return None
    return sol

def query_oracle(n):
    outs = []
    for _ in range(n):
        r = requests.get(ORACLE + '/get_output')
        o = r.json()['output']
        outs.append(int(o, 16))
    return outs

if __name__ == '__main__':
    print("Querying oracle for 2 outputs (need at least 2 to get 256 bits -> enough linear eqs)")
    obs = query_oracle(2)  # 2 outputs give us up to 256 equations (we need >=128 independents)
    print("Observed outputs:")
    for o in obs:
        print(format(o, '032x'))
    rows, rhs = construct_system(obs)
    print(f"Constructed {len(rows)} equations.")
    sol = solve_gf2(rows, rhs)
    if sol is None:
        print("Failed to solve linear system (insufficient independent equations). Try more outputs.")
    else:
        print("Recovered initial state (128-bit) as hex:")
        print(format(sol & ((1<<128)-1), '032x'))
        # Predict next: we need to simulate RNG forward from recovered state to produce next output.
        # Let's implement the same linear transform as oracle used, and run steps = len(obs) to get to next output.
        def advance_once(state):
            s = state
            def rotl(x, r, bits=128):
                r %= bits
                return ((x << r) & ((1 << bits) - 1)) | (x >> (bits - r))
            t = s ^ ((s << 7) & ((1<<128)-1)) ^ (s >> 13) ^ rotl(s, 37)
            t &= ((1<<128)-1)
            return t
        st = sol
        for _ in range(len(obs)):
            st = advance_once(st)
        predicted_next = st
        print("Predicted next output (hex):", format(predicted_next, '032x'))
        # Validate with oracle
        r = requests.post(ORACLE + '/validate', json={'candidate': format(predicted_next, '032x')})
        print("Validation response:", r.json())
