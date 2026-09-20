"""Download and sample the verazuo/jailbreak_llms prompt dataset.

Source: https://github.com/verazuo/jailbreak_llms (in-the-wild jailbreak prompts,
CCS'24 "Do Anything Now" paper). Same CSV schema for both files, distinguished
only by the `jailbreak` boolean column, so the "regular" file doubles as our
benign / false-positive control set.
"""

import csv
import io
import random
from pathlib import Path

import requests

BASE_URL = (
    "https://raw.githubusercontent.com/verazuo/jailbreak_llms/main/data/prompts/"
)
JAILBREAK_FILE = "jailbreak_prompts_2023_12_25.csv"
REGULAR_FILE = "regular_prompts_2023_12_25.csv"

DATA_DIR = Path(__file__).parent / "data"


def _download(filename: str) -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cached = DATA_DIR / filename
    if cached.exists():
        return cached.read_text()
    response = requests.get(BASE_URL + filename, timeout=30)
    response.raise_for_status()
    cached.write_text(response.text)
    return response.text


def _prompts(filename: str) -> list[str]:
    text = _download(filename)
    reader = csv.DictReader(io.StringIO(text))
    return [row["prompt"] for row in reader if row.get("prompt")]


def load_sample(n_per_class: int, seed: int = 0) -> tuple[list[str], list[str]]:
    """Return (jailbreak_prompts, benign_prompts), each length n_per_class."""
    rng = random.Random(seed)
    jailbreak = _prompts(JAILBREAK_FILE)
    benign = _prompts(REGULAR_FILE)
    return (
        rng.sample(jailbreak, min(n_per_class, len(jailbreak))),
        rng.sample(benign, min(n_per_class, len(benign))),
    )
