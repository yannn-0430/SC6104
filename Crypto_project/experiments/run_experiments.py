# experiments/run_experiments.py
# Automate experiments: vary samples and output truncation, collect success/time statistics
# Requires that oracle is running (adjust ORACLE_BASE if needed).

import subprocess
import requests
import time
import csv
import os
import argparse
import math

ORACLE = 'http://127.0.0.1:5000'
ATTACKER_SCRIPT = os.path.join('..', 'attacker', 'recover_128bit.py')  # adjust if running from experiments/
OUT_CSV = 'results/experiments_results.csv'

def run_single(samples, output_bits):
    # call attacker script as subprocess, capture stdout for success detection
    cmd = ['python', os.path.join('..', 'attacker', 'recover_128bit.py'),
           '--samples', str(samples), '--output_bits', str(output_bits)]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    elapsed = time.time() - t0
    stdout = p.stdout + p.stderr
    success = 'Recovered initial 128-bit state' in stdout
    return success, elapsed, stdout

def ensure_results_dir():
    os.makedirs('results', exist_ok=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples_list', type=str, default='2,3,4,5,6', help='comma list')
    parser.add_argument('--output_bits_list', type=str, default='128,96,64,48', help='comma list')
    parser.add_argument('--trials', type=int, default=10, help='repeats per combo')
    args = parser.parse_args()

    samples_list = [int(x) for x in args.samples_list.split(',')]
    output_bits_list = [int(x) for x in args.output_bits_list.split(',')]
    ensure_results_dir()
    csv_path = os.path.join('results', f'experiments_{int(time.time())}.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['samples', 'output_bits', 'trial', 'success', 'time_s'])
        for samples in samples_list:
            for output_bits in output_bits_list:
                for trial in range(args.trials):
                    print(f"Running samples={samples}, output_bits={output_bits}, trial={trial}")
                    success, elapsed, out = run_single(samples, output_bits)
                    writer.writerow([samples, output_bits, trial, int(success), f"{elapsed:.3f}"])
                    f.flush()
    print("Experiments complete. CSV saved at:", csv_path)
