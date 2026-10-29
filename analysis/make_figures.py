"""Rebuild every chart and the summary table from the raw files in results/.

Usage (from the repo root):
    pip install -r requirements.txt
    python analysis/make_figures.py

Writes figures/*.png and analysis/summary.csv, and prints the key numbers.
Nothing in results/ is changed.
"""
import csv
import glob
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib import patheffects  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
OUT = os.path.join(ROOT, "analysis")

PEAK_BANDWIDTH_GBS = 34.1  # LPDDR4X-4266 on a 64-bit bus: 4266e6 transfers/s x 8 bytes
MODELS = ["0.8B-Q4_K_M", "0.8B-Q8_0", "2B-Q4_K_M", "2B-Q8_0", "4B-Q4_K_M", "4B-Q8_0"]

# Colours (light surface). One accent blue, one lighter step of the same hue, quiet greys.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e6e5e0"
AXIS = "#b9b8b2"
MUTED = "#a9a8a2"
BLUE = "#2a78d6"
BLUE_LIGHT = "#86b6ef"

if any("Inter" in f.name for f in font_manager.fontManager.ttflist):
    plt.rcParams["font.family"] = "Inter"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 11, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": AXIS,
    "axes.spines.top": False, "axes.spines.right": False,
})


def label(model):
    size, quant = model.split("-", 1)
    return f"{size} {'4-bit' if quant.startswith('Q4') else '8-bit'}"


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def bench_rows(path):
    """llama-bench CSV -> list of dicts with test name, threads, mask, speed, spread, size."""
    out = []
    for r in read_csv(path):
        test = f"pp{r['n_prompt']}" if r["n_gen"] == "0" else f"tg{r['n_gen']}"
        out.append({"test": test, "threads": int(r["n_threads"]), "mask": r["cpu_mask"],
                    "tps": float(r["avg_ts"]), "sd": float(r["stddev_ts"]),
                    "size_gb": int(r["model_size"]) / 1e9, "commit": r["build_commit"]})
    return out


def titles(fig, title, subtitle):
    """Title states the finding; subtitle says what was measured. Subtitle may hold a newline."""
    fig.text(0.03, 0.965, title, fontsize=15, fontweight="bold", color=INK, va="top")
    fig.text(0.03, 0.905, subtitle, fontsize=10.5, color=INK2, va="top", linespacing=1.4)


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"  wrote figures/{name}")


# ---------------------------------------------------------------- Step 7a: threads
def fig_threads():
    rows = bench_rows(os.path.join(RES, "threads.csv"))
    pinned = bench_rows(os.path.join(RES, "threads_pinned.csv"))
    cats = [str(t) for t in (1, 2, 3, 4, 6, 8)] + ["4 on fast\ncores"]

    def series(test):
        vals = [r for r in rows if r["test"] == test] + [r for r in pinned if r["test"] == test]
        return [v["tps"] for v in vals], [v["sd"] for v in vals]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.9))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.72, bottom=0.17, wspace=0.22)
    for ax, test, name in [(axes[0], "tg64", "Writing an answer (tg64)"),
                           (axes[1], "pp256", "Reading a prompt (pp256)")]:
        vals, sds = series(test)
        colours = [MUTED] * (len(vals) - 1) + [BLUE]
        ax.bar(cats, vals, color=colours, width=0.62, yerr=sds, ecolor=INK2,
               error_kw={"elinewidth": 1, "capsize": 3})
        for x, v, sd in zip(range(len(vals)), vals, sds):
            ax.text(x, v + sd + max(vals) * 0.02, f"{v:.1f}", ha="center", fontsize=9.5, color=INK)
        ax.set_title(name, loc="left", fontsize=11.5, color=INK, pad=10)
        ax.set_ylabel("tokens per second")
        ax.set_xlabel("threads")
        ax.set_ylim(0, max(vals) * 1.18)
        ax.yaxis.grid(True, color=GRID)
        ax.set_axisbelow(True)
    titles(fig, "4 threads on the fast cores was the fastest setting for both writing and reading",
           "Qwen3.5 0.8B 4-bit, mean of 3 runs, whiskers = 1 standard deviation.\n"
           "Grey bars let Android place the threads; the blue bar pins 4 threads to the fast cores (4-7).")
    save(fig, "fig1_threads.png")


# ------------------------------------------------- Step 7b: speed vs memory limit
def speed_table():
    table = []
    for m in MODELS:
        r = bench_rows(os.path.join(RES, f"speed_Qwen_Qwen3.5-{m}.csv"))
        pp = next(x for x in r if x["test"] == "pp512")
        tg = next(x for x in r if x["test"] == "tg128")
        ceiling = PEAK_BANDWIDTH_GBS / tg["size_gb"]
        table.append({"model": m, "label": label(m), "size_gb": tg["size_gb"],
                      "pp512": pp["tps"], "pp512_sd": pp["sd"], "tg128": tg["tps"], "tg128_sd": tg["sd"],
                      "ceiling": ceiling, "pct_of_ceiling": tg["tps"] / ceiling * 100,
                      "effective_gbs": tg["tps"] * tg["size_gb"], "commit": tg["commit"]})
    return table


def fig_bandwidth(table):
    avg_bw = sum(t["effective_gbs"] for t in table) / len(table)
    xs = [0.45 + i * 0.01 for i in range(int((4.85 - 0.45) / 0.01) + 1)]
    fig, ax = plt.subplots(figsize=(10, 5.8))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.78, bottom=0.11)
    ax.plot(xs, [PEAK_BANDWIDTH_GBS / x for x in xs], color=MUTED, lw=1.8,
            label=f"memory limit: {PEAK_BANDWIDTH_GBS} GB/s \u00f7 size")
    ax.plot(xs, [avg_bw / x for x in xs], color=MUTED, lw=1.4, ls=(0, (4, 3)),
            label=f"measured average: {avg_bw:.1f} GB/s \u00f7 size")
    # label offsets in points, chosen so no label sits on a curve: (dx, dy, horizontal alignment)
    offsets = {"0.8B-Q4_K_M": (0, 11, "center"), "0.8B-Q8_0": (-10, -14, "right"),
               "2B-Q4_K_M": (-10, -14, "right"), "2B-Q8_0": (-12, -18, "right"),
               "4B-Q4_K_M": (0, -18, "center"), "4B-Q8_0": (-12, -9, "right")}
    for t in table:
        q4 = "Q4" in t["model"]
        ax.scatter(t["size_gb"], t["tg128"], s=70, color=BLUE if q4 else SURFACE,
                   edgecolor=BLUE, linewidth=2, zorder=3)
        dx, dy, ha = offsets[t["model"]]
        ax.annotate(f"{t['label']}: {t['tg128']:.1f}", (t["size_gb"], t["tg128"]), xytext=(dx, dy),
                    textcoords="offset points", ha=ha, va="center", fontsize=9.5, color=INK,
                    path_effects=[patheffects.withStroke(linewidth=4, foreground=SURFACE)])
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 65)
    ax.set_xlabel("model weights read per token (GB)")
    ax.set_ylabel("writing speed, tokens per second")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    ax.scatter([], [], s=60, color=BLUE, edgecolor=BLUE, label="4-bit model file")
    ax.scatter([], [], s=60, color=SURFACE, edgecolor=BLUE, linewidth=2, label="8-bit model file")
    ax.legend(frameon=False, loc="upper right", fontsize=10)
    lo = min(t["pct_of_ceiling"] for t in table)
    hi = max(t["pct_of_ceiling"] for t in table)
    titles(fig, f"Writing speed follows memory bandwidth ÷ model size, at {lo:.0f}–{hi:.0f}% of the limit",
           "Each dot is one model file, labelled with its writing speed in tokens per second (Step 7b).\n"
           "A model twice as big writes about half as fast.")
    save(fig, "fig2_bandwidth.png")


# ----------------------------------------------------------- Step 8: heat run
def sustained(model):
    rows = [r for r in read_csv(os.path.join(RES, f"sustained_Qwen_Qwen3.5-{model}.csv")) if r["gen_tok_per_s"]]
    t = [float(r["elapsed_s"]) for r in rows]
    s = [float(r["gen_tok_per_s"]) for r in rows]
    temp = [float(r["battery_temp_c"]) for r in rows]
    first = s[0]
    minutes = []
    for m in range(10):
        idx = [i for i, x in enumerate(t) if m * 60 < x <= (m + 1) * 60]
        if idx:
            minutes.append({"minute": m + 1,
                            "pct": sum(s[i] for i in idx) / len(idx) / first * 100,
                            "tps": sum(s[i] for i in idx) / len(idx),
                            "temp": max(temp[i] for i in idx)})
    hot = next((x for x, c in zip(t, temp) if c >= 40), None)
    raw = read_csv(os.path.join(RES, f"sustained_Qwen_Qwen3.5-{model}.csv"))
    pct_used = int(raw[0]["battery_pct"]) - int(raw[-1]["battery_pct"])
    tokens = len(rows) * 128
    return {"model": model, "first": first, "minutes": minutes, "hot_s": hot,
            "late": sum(x["tps"] for x in minutes[5:]) / len(minutes[5:]),
            "tokens": tokens, "pct_used": pct_used,
            "mah_per_1k": pct_used / 100 * 4500 / tokens * 1000}


def fig_heat(runs):
    fig, (ax, axt) = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True,
                                  gridspec_kw={"height_ratios": [2.2, 1]})
    fig.subplots_adjust(left=0.08, right=0.84, top=0.80, bottom=0.09, hspace=0.12)
    hot_min = sum(r["hot_s"] for r in runs) / len(runs) / 60
    for a in (ax, axt):
        a.axvline(hot_min, color=INK2, lw=1, ls=(0, (4, 3)))
        a.yaxis.grid(True, color=GRID)
        a.set_axisbelow(True)
    ax.text(hot_min + 0.1, 104, "battery reaches 40 °C", color=INK2, fontsize=10)
    for r, colour in zip(runs, (BLUE, BLUE_LIGHT)):
        xs = [m["minute"] - 0.5 for m in r["minutes"]]
        ax.plot(xs, [m["pct"] for m in r["minutes"]], color=colour, lw=2, marker="o", ms=5)
        axt.plot(xs, [m["temp"] for m in r["minutes"]], color=colour, lw=2, marker="o", ms=4)
        end = r["minutes"][-1]
        ax.text(9.8, end["pct"] + (4 if colour == BLUE else -7),
                f"{label(r['model'])}\n{r['first']:.1f} → {r['late']:.1f} tok/s",
                color=INK, fontsize=9.5, va="center")
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_ylabel("speed, % of first reading")
    axt.set_ylim(28, 42)
    axt.set_ylabel("battery °C (max)")
    axt.set_xlim(0, 10)
    axt.set_xticks(range(0, 11, 2))
    axt.set_xlabel("minutes of nonstop writing")
    titles(fig, "Both models drop to about half speed once the battery reaches 40 °C",
           "Step 8: 10 minutes of nonstop writing on battery, 4 threads on the fast cores. Points are per-minute averages;\n"
           "labels give the first reading and the average over minutes 6-10.")
    save(fig, "fig3_heat.png")


# ------------------------------------------------------ Step 9: quality vs speed
def quality_scores():
    scores = {}
    for m in MODELS:
        rows = read_csv(os.path.join(RES, f"quality_Qwen_Qwen3.5-{m}.csv"))
        scores[m] = sum(int(r["correct"]) for r in rows if r["correct"] != "")
    return scores


def perplexity():
    out = {}
    for m in MODELS:
        text = open(os.path.join(RES, f"ppl_Qwen_Qwen3.5-{m}.txt"), errors="replace").read()
        hit = re.search(r"Final estimate: PPL = ([\d.]+) \+/- ([\d.]+)", text)
        out[m] = (float(hit.group(1)), float(hit.group(2))) if hit else None
    return out


def fig_quality(table, scores):
    best = max(scores.values())
    fig, ax = plt.subplots(figsize=(10, 5.4))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.80, bottom=0.12)
    sides = {"0.8B-Q4_K_M": 1, "0.8B-Q8_0": -1, "2B-Q4_K_M": 1, "2B-Q8_0": -1, "4B-Q4_K_M": 1, "4B-Q8_0": 1}
    for t in table:
        q = scores[t["model"]]
        top = q == best
        ax.scatter(t["tg128"], q, s=90, color=BLUE if top else MUTED, zorder=3)
        side = sides[t["model"]]
        ax.annotate(f"{t['label']} · {q}/20", (t["tg128"], q), xytext=(10 * side, -4),
                    textcoords="offset points", ha="left" if side > 0 else "right",
                    fontsize=10, color=INK if top else INK2, fontweight="bold" if top else "normal")
    ax.set_xlim(0, 40)
    ax.set_ylim(0, 20.8)
    ax.set_yticks([0, 5, 10, 15, 20])
    ax.set_xlabel("writing speed, tokens per second (Step 7b)")
    ax.set_ylabel("questions right, out of 20")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    titles(fig, "Bigger models get more answers right but write more slowly",
           "Step 9: the same 20 questions for every model file, temperature 0. "
           "One question = 5 percentage points, so gaps of 1-2 are a tie.")
    save(fig, "fig4_quality_vs_speed.png")


# ---------------------------------------------- Step 7c: longer context (2B 4-bit)
def depth_runs():
    """Writing speed at each context depth, plus the KV cache size from the llama.cpp log."""
    rows = []
    for path in glob.glob(os.path.join(RES, "depth_2B_*.csv")):
        for r in read_csv(path):
            rows.append({"depth": int(r["n_depth"]), "tps": float(r["avg_ts"]), "sd": float(r["stddev_ts"]),
                         "size_gb": int(r["model_size"]) / 1e9})
    rows.sort(key=lambda r: r["depth"])
    log = open(os.path.join(RES, "kvcache_2B_ctx8192.log"), errors="replace").read()
    hit = re.search(r"llama_kv_cache: size =\s+([\d.]+) MiB \(\s*(\d+) cells,\s+(\d+) layers", log)
    kv_mib, cells, layers = float(hit.group(1)), int(hit.group(2)), int(hit.group(3))
    n_layer = int(re.search(r"print_info: n_layer\s+=\s+(\d+)", log).group(1))
    return rows, kv_mib * 2**20 / cells, layers, n_layer


def fig_context(rows, kv_per_token, kv_layers, n_layer):
    base = rows[0]
    eff_bw = base["tps"] * base["size_gb"] * 1e9  # bytes/s achieved with an empty context
    predicted = [eff_bw / (base["size_gb"] * 1e9 + kv_per_token * r["depth"]) for r in rows]
    xs = [r["depth"] for r in rows]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    fig.subplots_adjust(left=0.08, right=0.80, top=0.76, bottom=0.12)
    ax.plot(xs, predicted, color=MUTED, lw=1.6, ls=(0, (4, 3)), marker="o", ms=4)
    ax.errorbar(xs, [r["tps"] for r in rows], yerr=[r["sd"] for r in rows], color=BLUE, lw=2,
                marker="o", ms=6, capsize=3, ecolor=INK2, elinewidth=1)
    for r in rows:
        ax.annotate(f"{r['tps']:.1f}", (r["depth"], r["tps"]), xytext=(0, -18), textcoords="offset points",
                    ha="center", fontsize=9.5, color=INK)
    end_pred, end = predicted[-1], rows[-1]
    ax.text(8500, end_pred, "if only reading the\nextra cache mattered", color=INK2, fontsize=9.5, va="center")
    ax.text(8500, end["tps"], "measured", color=BLUE, fontsize=10, va="center", fontweight="bold")
    ax.set_xlim(-300, 8400)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x:,}" for x in xs])
    ax.set_ylim(0, 20)
    ax.set_yticks([0, 5, 10, 15, 20])
    ax.set_xlabel("tokens already in context")
    ax.set_ylabel("writing speed, tokens per second")
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    share = (1 / end_pred - 1 / base["tps"]) / (1 / end["tps"] - 1 / base["tps"]) * 100
    titles(fig, f"Long context cuts writing speed by a third; reading the cache explains only {share:.0f}% of that",
           f"Qwen3.5 2B 4-bit, mean of 3 runs per depth, cooldown between depths. Only {kv_layers} of its {n_layer} layers keep a "
           f"cache ({kv_per_token / 1024:.0f} KB per token).\nThe grey line adds reading that cache to the weights, "
           f"at the bandwidth measured with an empty context.")
    save(fig, "fig5_context.png")
    return predicted, share


def main():
    os.makedirs(FIG, exist_ok=True)
    print("Building figures from results/ ...")
    fig_threads()
    table = speed_table()
    fig_bandwidth(table)
    runs = [sustained("0.8B-Q4_K_M"), sustained("4B-Q4_K_M")]
    fig_heat(runs)
    scores = quality_scores()
    ppl = perplexity()
    fig_quality(table, scores)
    depth, kv_per_token, kv_layers, n_layer = depth_runs()
    predicted, kv_share = fig_context(depth, kv_per_token, kv_layers, n_layer)

    path = os.path.join(OUT, "summary.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "weights_gb", "read_pp512_tok_s", "write_tg128_tok_s", "memory_limit_tok_s",
                    "pct_of_limit", "effective_bandwidth_gb_s", "questions_right_of_20", "perplexity"])
        for t in table:
            p = ppl[t["model"]]
            w.writerow([t["label"], f"{t['size_gb']:.3f}", f"{t['pp512']:.1f}", f"{t['tg128']:.2f}",
                        f"{t['ceiling']:.1f}", f"{t['pct_of_ceiling']:.0f}", f"{t['effective_gbs']:.1f}",
                        scores[t["model"]], f"{p[0]:.2f}" if p else "did not fit in memory"])
    print("  wrote analysis/summary.csv\n")

    print(f"llama.cpp commit: {table[0]['commit']}")
    for t in table:
        p = ppl[t["model"]]
        print(f"{t['label']:11} {t['size_gb']:.3f} GB  read {t['pp512']:6.1f}  write {t['tg128']:5.2f} tok/s  "
              f"limit {t['ceiling']:4.1f}  {t['pct_of_ceiling']:3.0f}%  eff {t['effective_gbs']:4.1f} GB/s  "
              f"{scores[t['model']]:2d}/20  ppl {p[0] if p else '-'}")
    for r in runs:
        print(f"heat {label(r['model'])}: {r['first']:.2f} -> {r['late']:.2f} tok/s after 5 min "
              f"({r['late'] / r['first'] * 100:.0f}%), 40 C at {r['hot_s']:.0f} s, "
              f"{r['tokens']} tokens, {r['pct_used']}% battery, {r['mah_per_1k']:.0f} mAh per 1,000 tokens")
    print(f"context (2B 4-bit): KV cache {kv_per_token:.0f} bytes per token in {kv_layers} of {n_layer} layers")
    for r, p in zip(depth, predicted):
        print(f"  depth {r['depth']:5d}: {r['tps']:5.2f} tok/s measured ({r['tps'] / depth[0]['tps'] * 100:3.0f}%), "
              f"{p:5.2f} if only cache reads mattered")
    print(f"  cache reads explain {kv_share:.0f}% of the slowdown at {depth[-1]['depth']:,} tokens")


if __name__ == "__main__":
    main()
