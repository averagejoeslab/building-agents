# repo_template

The structure of the README, and the files that back it. The README follows a frontier lab's process, from scratch, at the
scale of one computer: the harness and its evaluation first, around a capable model; then a model of our own, built and trained
in stages, each checked on its own held-out data and in the harness; then what fell short, and what would fix it.

## The README

```
Building agents
│
├─ What an agent is
│    ├─ In cognitive science: perceive, remember, decide, act, in a cycle; the kinds of memory
│    ├─ An LLM agent: that cycle around a language model; the model decides, the harness does the rest
│    ├─ The primitives: the model, and the harness's five, each with what it does
│    │    and what it is in cognitive science   [TABLE]
│    ├─ The harness wraps the model; the model outputs one token at a time   [DIAGRAM]
│    └─ Agent = Harness(Model); neither works alone: engine and vehicle
│
├─ How frontier labs build agents
│    ├─ Both, built for each other: harness and evaluations first; the model in stages,
│    │    each checked on held-out data and on the agent's evaluations   [TABLE]
│    └─ Ship them together; the gaps found decide the next round
│
├─ What this repo is
│    ├─ The same process, from scratch, on one computer   [DIAGRAM]
│    └─ Why the harness first; the swaps, said up front (Sonnet; Qwen's numbers); every result real
│
├─ The harness
│    ├─ What it does; its loop   [DIAGRAM]
│    ├─ Building it around Sonnet, one primitive at a time, on one job (shop/)   [CODE + RUN each]
│    │    model interface · input · output · control flow · context (who, where, when) → quark.py
│    ├─ Try it: acts unasked, forgets, can hang, records nothing
│    └─ Making it production-ready: six concerns × five primitives   [TABLE]
│         ├─ 1. Persistence: memory (working, episodic, semantic, procedural), quark's instructions,
│         │       continuing an unfinished session
│         ├─ 2. Safety: sandboxing (a box) and guardrails (never, ask, step limit, Ctrl-C, no half command)
│         ├─ 3. Observability: a record of every step
│         ├─ 4. Resilience: retries, a backup model, timeouts, summaries, surviving a crash
│         ├─ 5. Performance: caching, streaming, trimming, a cheaper model
│         ├─ 6. Evaluation: tasks.py, 32 held-out tasks in four kinds, checked by what was done;
│         │       evaluation only, never trained on   [RESULT: Sonnet 32/32]
│         │    each: how it makes the primitives production-ready [CODE] [RUN],
│         │    and what it changes for the other concerns
│         └─ → quark_production.py; its model is Sonnet: now we build our own
│
├─ The model
│    ├─ What it does: tokens in, the next token out, repeated   [DIAGRAM]
│    ├─ Its seven primitives; how they predict, together   [TABLE] [DIAGRAM]
│    ├─ Building them: each in one line, then its code → model.py, checked against Qwen   [CODE] [CHECK]
│    └─ Training it: one idea; three stages; every stage checked twice, before → after:
│         its own held-out, decontaminated data (did it do its job?)
│         and the agent's 32 tasks in quark (did it help the agent?)
│         ├─ Pre-training: ours, from random numbers, on Shakespeare   [HELD-OUT BEFORE/AFTER]
│         │    → the compute gap → Qwen3-0.6B-Base loaded into our code, every part checked   [RESULT] [CHECK]
│         ├─ Our model in quark: one primitive changes, the model interface   [CODE]
│         │    → Base on tasks.py: the starting point   [RESULT]
│         ├─ Mid-training: shell pages, decontaminated, fixed steps   [DATA] [HELD-OUT] [tasks.py]
│         ├─ Instruction-tuning: six kinds; public sets and verified sessions from training tasks
│         │    kept apart from tasks.py; decontaminated   [DATA] [HELD-OUT] [same requests] [tasks.py]
│         │    → a stop: RL only if the agent does the right thing some of the time
│         ├─ RL in the harness: tries at training tasks, graded by their checks; the same update,
│         │    weighted   [CODE] [HELD-OUT TRAINING TASKS] [tasks.py]
│         └─ Stage by stage: same harness, same tasks, only the model changes   [TABLE]
│
├─ What fell short, and what would fix it: each gap, its likely cause, the remedy   [RESULT]
│
├─ How to build an agent from scratch: a lab's steps beside ours; what we couldn't match is scale   [TABLE]
│
└─ Run it: the harness, then the model, scored after each stage   [COMMANDS]
```

## The files

| File | What it provides | README section |
|---|---|---|
| `README.md` | the walkthrough | all |
| `repo_template.md` | this outline | — |
| `quark.py` | the five primitives, around Sonnet | The harness: building it |
| `quark_production.py` | quark with the six production concerns; `QUARK_MODEL` puts any model in it | Making it production-ready; Our model in quark |
| `shop/` | the job every harness step is shown on: a failing test | The harness |
| `tasks.py` | the evaluation: 32 tasks in four kinds, checked by what was done; never trained on | Evaluation; every training stage |
| `model.py` | the model's seven primitives, Qwen3's design; `Release` loads a model as shipped; `uv run model.py` checks it against Qwen | The model |
| `train.py` | every training stage: `pre`, `mid`, `post instruct`, `post rl`; the training tasks kept apart from `tasks.py`; decontamination | Training it |
| `.env.example` | where the Anthropic key goes | Run it |
