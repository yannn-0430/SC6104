# oracle/config.py
# Configuration for oracle service

HOST = '127.0.0.1'
PORT = 5000

# If seed is None, oracle will seed from os.urandom (random each run).
# For reproducible demos set deterministic seed (hex int).
SEED = 0x1234567890ABCDEF1234567890ABCDEF  # None or int

# How many bits does oracle reveal per /get_output call?
# Set to 128 to reveal full state; set to <128 to simulate truncation.
OUTPUT_BITS = 128  # e.g., 128 or 64

# If OUTPUT_BITS < 128, which bits to reveal? Options: 'high' or 'low'
OUTPUT_SELECT = 'high'
