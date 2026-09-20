# Benchmark results

Sample: 60 jailbreak prompts + 60 benign prompts from [verazuo/jailbreak_llms](https://github.com/verazuo/jailbreak_llms).

| Detector | Catch rate | False positive rate | Avg latency | Cost / 1k requests |
|---|---|---|---|---|
| regex baseline | 23% | 7% | 0 ms | $0.0000 |
| jevguard (Jev) | 88% | 10% | 1221 ms | $0.0460 |
| LLM judge (openai/gpt-4o-mini) | 87% | 8% | 1286 ms | $0.0754 |
