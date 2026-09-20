"""Benchmark jevguard against a regex baseline and a GPT-4-class LLM judge.

Usage:
    python -m benchmark.run_benchmark [--n-per-class 75]

Requires TYPESAFE_API_KEY and OPENROUTER_API_KEY in the environment (.env).
"""

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.baselines import (  # noqa: E402
    OPENROUTER_MODEL,
    llm_judge_baseline,
    regex_baseline,
)
from benchmark.datasets import load_sample  # noqa: E402
from jevguard.guard import check  # noqa: E402

JEV_PROMPT_PRICE_PER_TOKEN = 0.042 / 1_000_000  # $0.042 / 1M input tokens, output free

OUT_DIR = Path(__file__).parent


def evaluate_detector(name, run_one, jailbreak_prompts, benign_prompts):
    caught = 0
    false_positives = 0
    total_latency_ms = 0.0
    total_cost_usd = 0.0
    errors = 0

    for prompt in jailbreak_prompts:
        try:
            flagged, latency_ms, cost_usd = run_one(prompt)
        except Exception:
            errors += 1
            continue
        caught += int(flagged)
        total_latency_ms += latency_ms
        total_cost_usd += cost_usd

    for prompt in benign_prompts:
        try:
            flagged, latency_ms, cost_usd = run_one(prompt)
        except Exception:
            errors += 1
            continue
        false_positives += int(flagged)
        total_latency_ms += latency_ms
        total_cost_usd += cost_usd

    n_total = len(jailbreak_prompts) + len(benign_prompts) - errors
    n_total = max(n_total, 1)

    return {
        "name": name,
        "catch_rate": caught / max(len(jailbreak_prompts), 1),
        "false_positive_rate": false_positives / max(len(benign_prompts), 1),
        "avg_latency_ms": total_latency_ms / n_total,
        "cost_per_1k_usd": (total_cost_usd / n_total) * 1000,
        "errors": errors,
    }


def run_regex(prompt: str):
    result = regex_baseline(prompt)
    return result.is_flagged, result.latency_ms, result.cost_usd


def run_jevguard(prompt: str):
    result = check(prompt)
    flagged = result.verdict.value != "allow"
    cost_usd = result.input_tokens * JEV_PROMPT_PRICE_PER_TOKEN
    return flagged, result.latency_ms, cost_usd


def run_llm_judge(prompt: str):
    result = llm_judge_baseline(prompt)
    return result.is_flagged, result.latency_ms, result.cost_usd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-per-class", type=int, default=75)
    args = parser.parse_args()

    load_dotenv()

    print(f"Loading {args.n_per_class} jailbreak + {args.n_per_class} benign prompts...")
    jailbreak_prompts, benign_prompts = load_sample(args.n_per_class)

    detectors = [
        ("regex baseline", run_regex),
        ("jevguard (Jev)", run_jevguard),
        (f"LLM judge ({OPENROUTER_MODEL})", run_llm_judge),
    ]

    results = []
    for name, run_one in detectors:
        print(f"Running {name}...")
        start = time.time()
        results.append(evaluate_detector(name, run_one, jailbreak_prompts, benign_prompts))
        print(f"  done in {time.time() - start:.1f}s")

    (OUT_DIR / "results.json").write_text(json.dumps(results, indent=2))
    write_results_md(results, args.n_per_class)
    write_chart(results)
    print(f"\nWrote {OUT_DIR / 'results.md'}, results.json, results_chart.png")


def write_results_md(results, n_per_class):
    lines = [
        "# Benchmark results\n",
        f"Sample: {n_per_class} jailbreak prompts + {n_per_class} benign prompts from "
        "[verazuo/jailbreak_llms](https://github.com/verazuo/jailbreak_llms).\n",
        "| Detector | Catch rate | False positive rate | Avg latency | Cost / 1k requests |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['catch_rate']:.0%} | {r['false_positive_rate']:.0%} "
            f"| {r['avg_latency_ms']:.0f} ms | ${r['cost_per_1k_usd']:.4f} |"
        )
    (OUT_DIR / "results.md").write_text("\n".join(lines) + "\n")


def write_chart(results):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed, skipping chart (pip install jevguard[benchmark])")
        return

    names = [r["name"] for r in results]
    catch = [r["catch_rate"] * 100 for r in results]
    fp = [r["false_positive_rate"] * 100 for r in results]

    x = range(len(names))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - width / 2 for i in x], catch, width, label="Catch rate %")
    ax.bar([i + width / 2 for i in x], fp, width, label="False positive rate %")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=15, ha="right")
    ax.set_ylabel("%")
    ax.set_title("jevguard vs baselines")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "results_chart.png", dpi=150)


if __name__ == "__main__":
    main()
