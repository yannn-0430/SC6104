安装依赖：pip install -r requirements.txt

启动 oracle：python oracle/app.py（或 sh oracle/run.sh）

运行攻击（demo）：python attacker/recover_128bit.py（或 sh attacker/demo_run.sh）

自动化实验：python experiments/run_experiments.py --out_bits 128 --max_samples 6 --truncation 64

生成图表：python experiments/analyze_results.py results/experiments_2025-10-13.csv
