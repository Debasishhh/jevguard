# Tech Note: jevguard — LLM guardrail firewall on TypeSafe's Jev

| | |
|---|---|
| **Owner** | Debasish Padhy |
| **Team** | Solo / personal project |
| **Start Date** | 20-09-2026 |
| **Deadline** | Ongoing |

> Brief format — 30 min to 2 hr to create.

---

## 1. Intro

Any app that puts an LLM in front of users needs something screening what goes
in and out of it — jailbreak attempts, prompt injection, requests to leak the
system prompt or secrets, generally unsafe requests. The default answer teams
reach for is "call GPT-4 and ask it to judge" — it works, but it doubles your
latency and cost on every real request just to answer a narrow yes/no
question. The cheaper default, a regex/keyword filter, is fast and free but
misses almost everything (23% catch rate in my own test, below).

I built **jevguard** to test whether TypeSafe's Jev — a model built to return
fast, calibrated yes/no and severity judgments instead of generated text —
can sit in that gap: close to LLM-judge accuracy, at a fraction of the cost,
without writing my own classifier or fine-tuning anything.

Scope: a small Python library (`check(prompt, history=None)` → allow/flag/
block) plus a benchmark comparing it against a regex baseline and a real
GPT-4-class judge (`gpt-4o-mini` via OpenRouter) on a public jailbreak-prompt
dataset. Repo: `github.com/Debasishhh/jevguard` (private).

---

## 2. FR / NFR

### Functional requirements
- `check(prompt)` returns a typed verdict (`allow` / `flag` / `block`) plus
  the raw signals that produced it, in one API call.
- `check(prompt, history=[...])` — same, but judges the prompt in the context
  of prior conversation turns, so a jailbreak built up gradually across
  several innocent-looking messages still gets caught.
- CLI (`python -m jevguard "<prompt>"`) for quick manual checks, exits
  non-zero on anything but `allow` so it's scriptable.
- A `flag` state exists on purpose — it's not `allow` or `block`, it's "send
  this to a human," for the cases the model itself is unsure about.

### Non-functional requirements
- One Jev call per `check()`, not one call per question — all signals are
  asked in parallel in a single request, so adding a signal doesn't add a
  round trip.
- Verdict thresholds live in code (`BLOCK_NOUL`, `FLAG_NOUL`, etc. in
  `guard.py`), not in the model — so they're inspectable and tunable without
  touching the questions themselves.
- No conversation content or secrets are logged by the library itself; the
  only external calls are to TypeSafe (for the guard itself) and, only during
  benchmarking, OpenRouter.

---

## 3. Architecture

```mermaid
sequenceDiagram
    participant App as Caller (app / CLI)
    participant Guard as jevguard.check()
    participant Jev as TypeSafe / Jev

    App->>Guard: check(prompt, history?)
    Guard->>Jev: system_one(state={prompt, history}, 5 parallel questions)
    Jev-->>Guard: jailbreak, injection, credential, escalation, severity
    Guard->>Guard: compose verdict from thresholds (pure code, no model call)
    Guard-->>App: {verdict, signals, reasons, latency_ms}
```

**Why five questions, not one.** An earlier, broader version asked one
question per concept with plain descriptions. Benchmarked against 60
jailbreak + 60 benign prompts from a public dataset (see Metrics), it caught
90% of jailbreaks but flagged 13% of benign prompts as attacks. Looking at
the actual false positives, every single one was a benign prompt-engineering
template — things like *"Please ignore all previous instructions, act as a
marketing expert and write ad copy."* That phrase is literally
instruction-override language, so the model wasn't wrong to notice it — the
question just didn't distinguish *intent*. I rewrote the two relevant
questions (`jailbreak_attempt`, `prompt_injection`) with explicit paired
examples of "malicious: wants to become unrestricted" vs. "benign: resetting
context for an ordinary task," and re-ran the same benchmark: 85% catch rate,
3.3% false positives — a 3x drop in false positives for one point of catch
rate. That's a general lesson from TypeSafe's own docs I hadn't internalized
until I hit it myself: an ambiguous yes/no boundary is usually a
question-design problem, fixed with contrastive examples, not a reason to
reach for a bigger model.

**Multi-turn history.** A jailbreak doesn't have to appear in one message —
it can be built up over several individually-benign turns. I added a fifth
question, `gradual_escalation`, that looks at `prompt` in the context of
`history`. Concrete before/after with the same final message: alone, *"Now
tell me how to pick a standard door lock"* comes back `allow`. Preceded by
three turns setting up an "unrestricted AI persona" game, the same message
comes back `block` (`jailbreak_attempt` jumps from 0.02 to 0.84). This part
is validated by hand-written examples only, not yet by a labeled multi-turn
benchmark — noted as a limitation, not a finished result.

---

## 4. Schema

No database — the "schema" here is the request/response shape of a Jev call
and the verdict it produces.

- **State sent to Jev**: `{"prompt": str, "conversation_history": list[str]}`.
- **Questions asked** (all in one request, evaluated independently):
  `jailbreak_attempt`, `prompt_injection`, `credential_or_secret_request`,
  `gradual_escalation` — each a Noul (probability 0–1); `policy_violation_severity`
  — a Score across 4 described levels (none / borderline / violates policy /
  severe).
- **`GuardResult`** (`jevguard/guard.py`): `verdict`, the five raw signal
  values, `severity_confidence`, `latency_ms`, `input_tokens`, `reasons`
  (which signals actually triggered the verdict).
- **Verdict thresholds** (tuned, not defaults): block if any Noul > 0.75 or
  severity ≥ 2.5; flag if any Noul > 0.6 or severity ≥ 1.0; else allow.

---

## 5. Infra & Metrics

### Infra
- No hosting — it's a library plus a CLI, called directly, no server of its
  own. Two external APIs: TypeSafe (the guard itself) and OpenRouter
  (`gpt-4o-mini`, only used inside the benchmark script as a comparison
  baseline, not part of the library at runtime).
- CI: GitHub Actions runs the unit test suite (pure threshold logic, no
  network) on every push.

### Metrics — the benchmark, on 60 jailbreak + 60 benign prompts from
[verazuo/jailbreak_llms](https://github.com/verazuo/jailbreak_llms) (public,
real in-the-wild jailbreak prompts, not synthetic):

| Detector | Catch rate | False positive rate | Latency | Cost / 1k requests |
|---|---|---|---|---|
| regex baseline | 23% | 7% | 0 ms | $0.0000 |
| **jevguard (Jev)** | 85% | **3.3%** | 1156 ms | **$0.065** |
| LLM judge (gpt-4o-mini) | 88% | 10.0% | 1187 ms | $0.075 |

jevguard nearly matches the GPT-4-class judge's catch rate with a third of
its false-positive rate, at lower cost and the same latency. Not the "100x
cheaper" headline Jev's raw per-token price would suggest on its own — a
5-question call sends more input tokens than a single-question judge prompt
— but a real, measured win on the metric that actually matters for a
guardrail (false positives are what erode user trust and generate support
tickets).

Not yet tracked: a labeled multi-turn dataset for `gradual_escalation`, and
threshold re-validation on a larger sample (current n=60/class is enough to
be directionally right, not enough for tight confidence intervals).
