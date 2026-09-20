# Benchmark results

Sample: 200 jailbreak prompts + 200 benign prompts from [verazuo/jailbreak_llms](https://github.com/verazuo/jailbreak_llms).

| Detector | Catch rate | False positive rate | Avg latency | Cost / 1k requests |
|---|---|---|---|---|
| regex baseline | 24% | 8% | 0 ms | $0.0000 |
| jevguard (Jev) | 83% | 16% | 1097 ms | $0.0653 |
| LLM judge (openai/gpt-4o-mini) | 84% | 19% | 1238 ms | $0.0760 |
