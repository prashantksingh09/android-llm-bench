"""Print the key columns of one or more llama-bench CSV files."""
import csv
import os
import sys

for path in sys.argv[1:]:
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            test = f"pp{r['n_prompt']}" if r["n_gen"] == "0" else f"tg{r['n_gen']}"
            name = os.path.basename(r["model_filename"]).removesuffix(".gguf")
            print(f"{name:30} t={r['n_threads']:>2} mask={r.get('cpu_mask', ''):5} "
                  f"{test:6} {float(r['avg_ts']):8.2f} ± {float(r['stddev_ts']):5.2f} tok/s")
