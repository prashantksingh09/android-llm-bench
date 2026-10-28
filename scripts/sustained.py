"""Generate text nonstop for N minutes; log speed, battery temperature and charge after every round.

Usage: python ~/lab/scripts/sustained.py MODEL.gguf [--minutes 10] [--threads 4] [--mask 0xF0]
Writes ~/lab/results/sustained_<model>.csv
"""
import argparse
import csv
import json
import os
import subprocess
import time

BENCH = os.path.expanduser("~/lab/llama.cpp/build/bin/llama-bench")
GEN_TOKENS = 128

p = argparse.ArgumentParser()
p.add_argument("model")
p.add_argument("--minutes", type=float, default=10)
p.add_argument("--threads", default="4")
p.add_argument("--mask", default="", help="e.g. 0xF0 to pin to the big cores")
p.add_argument("--capacity", type=float, default=4500, help="battery capacity in mAh")
a = p.parse_args()


def battery():
    out = subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=60).stdout
    b = json.loads(out)
    return b.get("temperature"), b.get("percentage"), b.get("current")


cmd = [BENCH, "-m", a.model, "-t", a.threads, "-p", "0", "-n", str(GEN_TOKENS), "-r", "1", "-o", "json"]
if a.mask:
    cmd += ["-C", a.mask, "--cpu-strict", "1"]

name = os.path.basename(a.model).removesuffix(".gguf")
out_path = os.path.expanduser(f"~/lab/results/sustained_{name}.csv")
temp0, pct0, _ = battery()
start = time.time()
rounds, el, pct = 0, 0.0, pct0

with open(out_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["elapsed_s", "gen_tok_per_s", "battery_temp_c", "battery_pct", "current_ua"])
    w.writerow([0, "", temp0, pct0, ""])
    print(f"start: {temp0}°C, {pct0}% battery, running {a.minutes:g} min")
    while time.time() - start < a.minutes * 60:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-1500:])
            raise SystemExit("llama-bench failed - see the error above")
        tps = json.loads(r.stdout)[0]["avg_ts"]
        rounds += 1
        temp, pct, cur = battery()
        el = round(time.time() - start, 1)
        w.writerow([el, round(tps, 2), temp, pct, cur])
        f.flush()
        print(f"{el:7.0f} s  {tps:6.2f} tok/s  {temp}°C  {pct}%")

tokens = rounds * GEN_TOKENS
used = (pct0 or 0) - (pct or 0)
print(f"\n{tokens} tokens in {el:.0f} s, battery {pct0}% -> {pct}% ({used}% used)")
if tokens:
    print(f"battery per 1,000 tokens: {used / tokens * 1000:.2f}% "
          f"= {used / 100 * a.capacity / tokens * 1000:.1f} mAh")
print(f"saved {out_path}")
