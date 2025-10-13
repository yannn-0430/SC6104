# experiments/plot_heatmap.py
"""
绘制热力图：横轴 = samples（oracle 输出个数），纵轴 = output_bits（oracle 返回的位数），
格子值 = 成功率 (mean success = successes / trials).

CSV expected columns: samples, output_bits, trial, success
 - samples: int (e.g. 2,3,4...)
 - output_bits: int (e.g. 128,96,64...)
 - trial: int (trial id)
 - success: 0 or 1

用法:
    python plot_heatmap.py --csv results/experiments_XXXX.csv --out heatmap.png
"""

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

def prepare_pivot(df):
    # compute mean success rate for each (samples, output_bits)
    agg = df.groupby(['output_bits','samples'], as_index=False)['success'].mean()
    # pivot so rows = output_bits (sorted desc), cols = samples (sorted asc)
    pivot = agg.pivot(index='output_bits', columns='samples', values='success')
    # sort rows descending so larger output_bits on top (optional)
    pivot = pivot.sort_index(ascending=False)
    return pivot

def plot_heatmap(pivot, title='Attack Success Rate Heatmap', out_file=None, annotate=True):
    # pivot is DataFrame with rows=output_bits, cols=samples
    rows = pivot.index.tolist()
    cols = pivot.columns.tolist()
    data = pivot.values  # may contain NaN for missing combos

    fig, ax = plt.subplots(figsize=(0.8*len(cols)+3, 0.6*len(rows)+2))
    # imshow with default colormap; vmin/vmax set to [0,1] for success rate
    im = ax.imshow(data, aspect='auto', interpolation='nearest', vmin=0.0, vmax=1.0)

    # ticks
    ax.set_xticks(np.arange(len(cols)))
    ax.set_yticks(np.arange(len(rows)))
    ax.set_xticklabels(cols)
    ax.set_yticklabels(rows)
    ax.set_xlabel('Number of Samples (queries to oracle)')
    ax.set_ylabel('Output bits returned by oracle')
    ax.set_title(title)

    # rotate xtick labels if many
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

    # annotate each cell with the success rate (percent)
    if annotate:
        for i in range(len(rows)):
            for j in range(len(cols)):
                val = data[i, j]
                if np.isnan(val):
                    txt = 'N/A'
                    ax.text(j, i, txt, ha='center', va='center', color='gray', fontsize=9)
                else:
                    txt = f"{val:.2f}"  # decimal fraction 0.00-1.00
                    ax.text(j, i, txt, ha='center', va='center', color='white' if val>0.5 else 'black', fontsize=9)

    # colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Mean success rate (0–1)')

    plt.tight_layout()
    if out_file:
        os.makedirs(os.path.dirname(out_file) or '.', exist_ok=True)
        plt.savefig(out_file, dpi=300)
        print(f"Heatmap saved to {out_file}")
    plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True, help='Path to experiments CSV')
    parser.add_argument('--out', default='results/heatmap_success_rate.png', help='Output PNG path')
    parser.add_argument('--title', default='Attack Success Rate Heatmap', help='Plot title')
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    # basic validation
    required = {'samples','output_bits','trial','success'}
    if not required.issubset(set(df.columns)):
        raise SystemExit(f"CSV must contain columns: {required}. Found: {df.columns.tolist()}")

    # ensure numeric and success in {0,1}
    df['samples'] = df['samples'].astype(int)
    df['output_bits'] = df['output_bits'].astype(int)
    df['success'] = df['success'].astype(float)

    pivot = prepare_pivot(df)
    plot_heatmap(pivot, title=args.title, out_file=args.out, annotate=True)

if __name__ == '__main__':
    main()
