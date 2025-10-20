# oracle/config.py
# Configuration for the oracle (RNG service)

# Network config
HOST = '127.0.0.1'
PORT = 5000

OUTPUT_MODE = 'hmac' # 'raw' or 'hmac'
# Seed configuration:
# - SEED_MODE:
#     'fixed'  : use the integer in SEED (if SEED is None, falls back to deterministic constant)
#     'random' : use os.urandom(16) at startup (non-deterministic each run)
#     'time'   : use current unix time (int(time.time())) as seed - low entropy (for demo)
SEED_MODE = 'fixed'   # 'fixed' | 'random' | 'time'

# If SEED_MODE == 'fixed', use this SEED (128-bit integer).
# If None, a default deterministic 128-bit constant will be used.
SEED = 0x1234567890ABCDEF1234567890ABCDEF  # or None

# If SEED_MODE == 'time', this controls whether we use seconds or milliseconds.
# 's' -> int(time.time()), 'ms' -> int(time.time() * 1000)
TIME_GRANULARITY = 's'  # 's' or 'ms'

# How many bits the oracle reveals on each /get_output call (1..128)
OUTPUT_BITS = 128
OUTPUT_SELECT = 'high'   # 'high' or 'low'

# Optional rate limit (requests per second). None or 0 means no limit.
RATE_LIMIT_RPS = None

# Logging level
LOG_LEVEL = 'INFO'
