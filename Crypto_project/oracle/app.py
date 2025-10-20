# oracle/app.py
# Flask oracle exposing /get_output and /validate
# Supports SEED_MODE = 'fixed' | 'random' | 'time'

from flask import Flask, jsonify, request
import config
from RNG128 import Linear128RNG, MASK128
from RNG_hmac import HMAC_DRBG_Simple     # new non-linear RNG

import os, time, logging

app = Flask(__name__)



# Setup logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger('oracle')

def derive_seed():
    """
    Derive a 128-bit seed integer according to config.SEED_MODE.
    Priority:
      - If SEED_MODE == 'fixed' and config.SEED is int -> use it
      - If SEED_MODE == 'fixed' and config.SEED is None -> use deterministic default
      - If SEED_MODE == 'random' -> use os.urandom(16)
      - If SEED_MODE == 'time' -> use current time (seconds or ms) expanded into 128 bits
    """
    mode = (config.SEED_MODE or 'fixed').lower()
    print(mode)
    if mode == 'fixed':
        if config.SEED is not None:
            seed = int(config.SEED) & MASK128
            logger.info(f"Using fixed SEED from config: {seed:032x}")
            return seed
        else:
            # deterministic default value
            seed = 0x1234567890ABCDEF1234567890ABCDEF
            logger.info(f"Using default fixed SEED: {seed:032x}")
            return seed
    elif mode == 'random':
        b = os.urandom(16)
        seed = int.from_bytes(b, 'big') & MASK128
        logger.info(f"Using random SEED (os.urandom): {seed:032x}")
        return seed
    elif mode == 'time':
        if config.TIME_GRANULARITY == 'ms':
            t = int(time.time() * 1000)
        else:
            t = int(time.time())
        # expand time into a 128-bit value via simple mixing (demo only)
        # Note: this is intentionally low-entropy (for demo of weak seed)
        seed = (t & ((1 << 64) - 1))  # start with time low 64 bits
        # mix with a deterministic constant to fill 128 bits
        const = 0xDEADBEEFCAFEBABEDEADBEEFCAFEBABE
        seed = ((seed << 64) ^ const) & MASK128
        logger.info(f"Using time-derived SEED (granu={config.TIME_GRANULARITY}): {seed:032x}")
        return seed
    else:
        # fallback to deterministic
        seed = 0x1234567890ABCDEF1234567890ABCDEF
        logger.warning(f"Unknown SEED_MODE '{config.SEED_MODE}', falling back to default SEED: {seed:032x}")
        return seed

# Initialize RNG with derived seed
SEED_VAL = derive_seed()
RNG = Linear128RNG(seed=SEED_VAL)

# initialize two RNG（任选其一根据 config.CONTROL)
if config.OUTPUT_MODE == 'raw':
    SEED_VAL = derive_seed()
    RNG = Linear128RNG(seed=SEED_VAL)
elif config.OUTPUT_MODE == 'hmac':
    # HMAC key 从环境或 config 读取（演示可固定）
    hkey = getattr(config, 'HMAC_KEY', None)
    if hkey is None:
        # demo key; in production keep secret
        hkey = b'demo_hmac_key_16b'
    # seed might be random/fixed/time as before
    SEED_VAL = derive_seed()
    RNG = HMAC_DRBG_Simple(key=hkey, seed=SEED_VAL)
else:
    # fallback
    SEED_VAL = derive_seed()
    RNG = Linear128RNG(seed=SEED_VAL)


def mask_output(x, bits=config.OUTPUT_BITS, select=config.OUTPUT_SELECT):
    if bits >= 128:
        return x & MASK128
    if select == 'high':
        return (x >> (128 - bits)) & ((1 << bits) - 1)
    else:
        return x & ((1 << bits) - 1)

@app.route('/get_output', methods=['GET'])
def get_output():
    # if RNG provides large output (HMAC returns 256 bit), mask/truncate accordingly
    val = RNG.next_raw()
    if config.OUTPUT_MODE == 'hmac':
        # val is 256-bit; we want to return config.OUTPUT_BITS bits
        # take high bits of mac for consistency
        total_bits = 256
        if config.OUTPUT_BITS >= total_bits:
            out = val
        else:
            out = (val >> (total_bits - config.OUTPUT_BITS)) & ((1 << config.OUTPUT_BITS) - 1)
        hexdigits = (config.OUTPUT_BITS + 3) // 4
        return jsonify({'output': format(out, '0{}x'.format(hexdigits))})
    else:
        # old behavior (raw 128-bit RNG)
        out = mask_output(val)
        hexdigits = (config.OUTPUT_BITS + 3) // 4
        return jsonify({'output': format(out, '0{}x'.format(hexdigits))})

@app.route('/validate', methods=['POST'])
def validate():
    data = request.get_json()
    if not data or 'candidate' not in data:
        return jsonify({'ok': False, 'reason': 'need candidate'}), 400
    try:
        candidate = int(data['candidate'], 16)
    except:
        return jsonify({'ok': False, 'reason': 'bad hex'}), 400
    true = RNG.next_raw()
    expected = mask_output(true)
    ok = (candidate & ((1 << config.OUTPUT_BITS) - 1)) == expected
    return jsonify({'ok': ok, 'expected': format(expected, '0{}x'.format((config.OUTPUT_BITS+3)//4))})

if __name__ == '__main__':
    logger.info(f"Starting oracle at http://{config.HOST}:{config.PORT} with SEED_MODE={config.SEED_MODE}")
    app.run(host=config.HOST, port=config.PORT, debug=False)
