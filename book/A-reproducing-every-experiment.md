# Appendix A: Reproducing Every Experiment

Every number in this book came from a command in the repository, and every command wrote its output to `runs/`. This appendix lists the commands in order, what each needs, what it writes, and what you should see. Run everything from the repository's root folder.

## What you need

| Need | For | Notes |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Everything | Each script declares its own dependencies; `uv run` installs them on first use, including a CPU build of PyTorch |
| An Anthropic API key in `.env` | The harness with Sonnet (Ch 11–15) | `cp .env.example .env`, then fill in `ANTHROPIC_API_KEY` |
| [Docker](https://docs.docker.com/get-docker/), running | The production harness, `tasks.py`, and RL (Ch 14–20) | Commands run in a `python:3.13` container; the first run pulls the image |
| Network access | First run of each training stage | Downloads Qwen3-0.6B from Hugging Face (about 1.5 GB), and public datasets |
| Memory | Training Qwen3-0.6B (Ch 8, 9, 17, 18) | Weights, gradients and AdamW's two states in 32-bit come to about 4 × 2.4 GB ≈ 9.6 GB before activations. Plan for 16 GB |
| Disk | Checkpoints | Each stage's checkpoint, saved in bfloat16, is about 1.2 GB, in `models/` (not committed) |

No GPU is needed. Everything in the record was run on a CPU.

## The commands, in order

| # | Command | Chapter | Writes | You should see |
|---|---|---|---|---|
| 1 | `uv run model/model.py` | 5 | `runs/model/check.txt` | `True`, `True`, a largest difference around `1e-04`, and `' Paris. The capital of Germany is Berlin. The capital of'` |
| 2 | `uv run model/train.py pre` | 7 | `runs/training/pretrain.txt` | Held-out loss from about 7.7 to about 5.3 in 20 minutes; Shakespeare-shaped text after |
| 3 | `uv run --env-file .env harness/quark.py` | 11–13 | (interactive) | The five parts; type the shop request in a copy of `harness/shop/` |
| 4 | `uv run harness/tasks.py` | 15 | `runs/harness/tasks-sonnet.txt` | `all 32/32` |
| 4b | `uv run harness/security.py` | 14 | `runs/harness/security.txt` | `security 4/4` |
| 5 | `uv run model/train.py mid` | 8 | `runs/training/midtrain.txt`, `models/midtrain.pt` | Held-out loss 1.896 → about 1.41 |
| 6 | `uv run model/train.py check` | 8 | appends to `midtrain.txt` | Shell check about 48/100 before, about 53/100 after |
| 7 | `uv run harness/tasks.py models/midtrain.pt` | 16 | `runs/training/tasks-midtrain.txt` | `all 2/32`: the two safety tasks |
| 8 | `uv run model/train.py post instruct` | 9, 17 | `runs/training/instruct.txt`, `models/instruct.pt` | Held-out loss falls by more than three quarters; the before/after replies of Chapter 9 |
| 9 | `uv run harness/tasks.py models/instruct.pt` | 17 | `runs/training/tasks-instruct.txt` | About 18/32 |
| 10 | `uv run model/train.py post rl` | 18, 20 | `runs/training/rl.txt`, `models/rl.pt` | Its held-out check before and after, and each step's passes out of 8 |
| 11 | `uv run harness/tasks.py models/rl.pt` | 18 | `runs/training/tasks-rl.txt` | The score after RL |

The `.said.txt` file next to each `tasks-*.txt` holds every transcript: what the agent said and ran on each task. Read them; they're where Chapters 17 to 20 got their diagnoses.

To score any model in the harness, pass its checkpoint to `tasks.py`. To score Qwen's own post-trained model, as in Chapter 19's table, pass its name: `uv run harness/tasks.py Qwen/Qwen3-0.6B`.

## Round one and round two

The code on the main line is round two's (Chapter 20): 26 training kinds, the stricter demonstrations, and the chat-template fix. Its committed data is `data/instruct.pt`. Round one's data is kept in `data/round1/instruct.pt`, and its records in `runs/training/round1/`.

To reproduce round one exactly, check out the commit before round two began, which still has round one's code and its committed data:

```bash
git checkout ab1c92d        # "The training data, committed"
```

Then run steps 8 to 11. Return with `git checkout -` when you're done.

## Restarts

Training stages save every few steps to `models/<stage>.pt`, with a `models/<stage>.progress` file recording how far they got. Run the same command again after an interruption and it carries on from the last save (the optimizer's state starts fresh). Data that's slow to build (the tokenized shell pages, the 2,352 conversations) is built once and kept in `data/*.pt`, and these files are committed, so a reproduction trains on exactly the data the record was made with.

## What will differ

Expect your numbers to be close to the record, not identical:

- **Evaluation is repeatable.** `tasks.py` and the held-out checks run the model at temperature 0, so the same model gives the same score.
- **Training is seeded but not bit-exact.** `train.py` seeds PyTorch and Python's random module, but floating-point results on CPU depend on the number of threads and the library version, and small differences grow over hundreds of steps.
- **Pre-training is time-boxed.** It runs for 20 minutes, not a fixed number of steps, so a faster machine trains further. The record made 1,405 steps.
- **Sonnet is a service.** Its replies at the model's default settings vary from run to run; the harness's scores with it can too.
- **Public datasets can change.** The committed `data/*.pt` files shield the training stages from that; rebuilding the data from scratch (by deleting them) may not reproduce them.
