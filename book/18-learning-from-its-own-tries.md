## 18. Learning from Its Own Tries: Reinforcement Learning

**Goal:** do the work reliably.

The second way to teach a model its body is practice: **reinforcement learning**, or RL. Instead of copying examples, the model tries the work itself, each try is graded, and tries that earned a good grade are made more likely. For an agent, a try is a task done in its harness. The harness had to exist first because the practice happens in it.

This chapter explains the idea from first principles, derives the update, shows our implementation, and then reports what happened, including three tries that failed.

### The vocabulary

RL has its own words for things this book already has:

| RL term | Here |
|---|---|
| **Policy** π | The model: given a context, a probability for every possible reply |
| **Action** | A whole reply the model writes (text and tool calls) |
| **Episode** / **trajectory** τ | One try at a task: every reply and every tool result, until the agent hands back |
| **Environment** | The harness, the box, and the task's folder |
| **Reward** R(τ) | The task's check: 1 if the folder ends up right, 0 if not |

The goal is to change the policy's parameters θ so that the expected reward goes up:

```
J(θ) = E_{τ ~ π_θ} [ R(τ) ]
```

"Expected reward" means: if the agent tried this task many times, sampling as it does, what fraction of tries would pass.

### Why this is harder than instruction-tuning

In instruction-tuning, the right text is given, and gradient descent makes it more likely. In RL there is no right text, only a grade on whatever the model wrote. And the grade isn't a differentiable function of the parameters. The check runs `python -m unittest` in a folder; you can't take its derivative.

RL works because you don't need to differentiate the reward. You only need to differentiate the probability of what the model did, which you can, because it's the same log-probability instruction-tuning uses.

### The policy gradient

Here is the derivation, in four lines. The expected reward is a sum over every possible trajectory, weighted by how likely the policy makes it:

```
J(θ)   = Σ_τ  π_θ(τ) · R(τ)
∇J(θ)  = Σ_τ  ∇π_θ(τ) · R(τ)                       -- R doesn't depend on θ
       = Σ_τ  π_θ(τ) · ∇log π_θ(τ) · R(τ)          -- since ∇π = π · ∇log π
       = E_{τ ~ π_θ} [ R(τ) · ∇log π_θ(τ) ]
```

The last line is the **policy gradient** (this form is called **REINFORCE**). It says: to estimate which way to move θ, sample some tries, and for each, take the gradient of its log-probability, scaled by its reward. A try that passed pulls the parameters toward making it more likely. A try that failed, with reward 0, contributes nothing.

And log π_θ(τ) is the sum of the log-probabilities of the tokens the model wrote, which is what `logprob` from Chapter 9 computes, with the tool results masked out because the model didn't write them. So one RL step is:

```
for each task:
    tries   ← sample G trajectories from the current model, in the harness
    rewards ← check each one
    loss    ← − Σ_i  reward_i · logprob(try_i)  /  G
    θ       ← θ − η · ∇loss
```

That's the same `update` function as instruction-tuning, with the reward as the weight. Instruction-tuning is the special case where every weight is 1 and the texts come from someone else. RL is the case where the texts are the model's own and the weights come from the grader.

### Baselines: why a group of tries

With rewards of 0 and 1, plain REINFORCE only ever pushes *toward* the passes. Better is to compare each try with the others: a pass when most tries failed is very informative; a pass when every try passed says little. So labs subtract a **baseline**, usually the average reward of the group, and often divide by its spread:

```
advantage_i = (reward_i − mean(rewards)) / std(rewards)
```

Now a pass in a group that mostly failed gets a large positive weight, a fail in a group that mostly passed gets a negative one (making it *less* likely), and a group where every try got the same reward gets zero weight on everything. The expected gradient is unchanged by the baseline; its noise is much lower. Using the group's own average as the baseline, with no separate value model, is the approach called **GRPO** (group relative policy optimization).

If all tries pass, or all fail, there is nothing to learn. RL learns from the difference between a try that worked and one that didn't.

### Keeping the policy anchored

Pushing a model toward its own words is unstable. It can drift into text that scores well on the grader but stops being sensible, or lose its formatting, and once every try fails there's no signal left to bring it back. Labs add two safeguards:

- **A KL penalty.** A frozen copy of the model from before RL (the *reference*) is kept, and the loss adds a penalty for how far the new model's token probabilities have moved from the reference's.
- **Clipped updates.** The change in each token's probability per step is capped (the idea behind **PPO**), so no single step can move the policy far.

Both cost something. The reference is a second copy of the model in memory; clipping needs the old probabilities stored for every token of every try.

### A worked step, by hand

Take one task and a group of four tries, with rewards (1, 0, 0, 1). Suppose the model gave each try these log-probabilities (summed over the tokens it wrote): (−12, −8, −9, −15).

**Plain REINFORCE, weights = rewards:**

```
loss = −(1·(−12) + 0·(−8) + 0·(−9) + 1·(−15)) / 4 = 6.75
```

The gradient raises the log-probability of tries 1 and 4, and ignores 2 and 3.

**With a group baseline:** mean = 0.5, std = 0.5, so the advantages are (+1, −1, −1, +1):

```
loss = −(1·(−12) − 1·(−8) − 1·(−9) + 1·(−15)) / 4 = 2.5
```

Now tries 1 and 4 are pushed up *and* tries 2 and 3 are pushed down. With rewards (1, 1, 1, 1), every advantage is 0 and the step does nothing, which is correct: the group has no information about what to change.

### Our implementation

Each try is a real run of the production harness, in a box, on a training task (Chapter 17's kinds, never the evaluation's), with our model inside:

```python
def attempt(model, quark, kind, seed):          # one try: what was said, and did it pass?
    where, ask, _, _, check = training_task(seed, kind)   # same seed → same folder for every try in the group
    os.chdir(where)
    try:
        quark.start_box()                       # the try's commands run in a container
        conversation = [{"role": "user", "content": ask}]
        quark.act(conversation)                 # the harness's own loop, our model inside, until it hands back
        said = final words of the conversation
        return quark.as_prompt(quark.assemble_context(conversation), prompt=False), check(said)
    finally:
        remove the container and the folder
```

*Shortened from `model/train.py`, where the full version is.*

`as_prompt(..., prompt=False)` renders the whole finished trajectory through the chat template, so `logprob` can score exactly the tokens the model wrote. The loop:

```python
def rl(steps=78, group=8):
    model = ours("models/instruct.pt")
    quark.allowed = lambda command: True        # as tasks.py runs it: yes to every approval
    quark.MAX_STEPS = 10                        # a try that hasn't finished in 10 steps has failed
    before = held_out_tasks(model, quark)       # its own check first
    if before.startswith("0/"):
        sys.exit("RL needs the agent to pass some of the time: improve instruction-tuning first")
    optimizer = trainable(model.model, lr=1e-6)
    for step in range(1, steps + 1):
        kind = TRAINING[(step - 1) % len(TRAINING)]          # cycle through the training kinds
        tries = [attempt(model, quark, kind, seed=step) for _ in range(group)]
        reward = torch.tensor([float(ok) for _, ok in tries])
        if reward.std() > 0:                                 # some passed, some failed
            update(model, optimizer, [text for text, _ in tries], reward.tolist(), most=1536)
    log("held-out training tasks after:", held_out_tasks(model, quark))
```

*Shortened from `model/train.py`, where the full version is.*

Three choices, all forced by running on one computer:

- **The weights are the raw rewards**, 1 for a pass and 0 for a fail, not centered advantages. That's REINFORCE without a baseline, and it only ever pushes *toward* passes. It's also known as *rejection-sampling fine-tuning*: imitation of the model's own successes.
- **No reference model, no clipping.** There isn't memory for a second copy of a 600-million-parameter model alongside its optimizer state.
- **A tiny learning rate**, 1 × 10⁻⁶, a tenth of instruction-tuning's.

The `reward.std() > 0` test skips groups that are all-pass or all-fail, since they carry no information (and with raw-reward weights, an all-pass group would just repeat imitation of what it already does). Each try is sampled at the model's own generation settings, so the eight tries differ.

RL also has **its own held-out check**: 40 training tasks, in folders seeded apart from anything it trains on, run once each at temperature 0. And it refuses to start if that check is 0 of 40: if the agent never passes, every group fails, and there's nothing to learn.

### Three tries that failed

Those choices weren't the first ones. Each failed try is kept in `runs/training/round1/`, and each taught something.

| Try | What changed | What happened |
|---|---|---|
| **First** | Centered advantages (passes up, fails down), learning rate 5 × 10⁻⁶ | Broke in two steps: 7 of 8, then 2 of 8, then 0 of 8 on nearly every kind after. Pushed away from its own words with no anchor, it drifted off its tool-call format |
| **Second** | A fifth of the learning rate (1 × 10⁻⁶), each try's weight capped at ±1 | Learned for two rounds (64% on the first ten kinds in round one, higher in round two), then came apart in the third |
| **Third** | Passes only (weights 0 and 1), back at 5 × 10⁻⁶ | Broke too: 20% after ten steps, falling |
| **Kept** | Passes only, at 1 × 10⁻⁶ | Held for all three rounds |

Without a reference model, a small model trained on its own words needs a small learning rate and no negative weights. Pushing failures down is what a lab does, with a reference model holding the policy in place. Without one, the stable choice was to pull only toward successes, at a small learning rate.

### What happened

The held-out check before RL: **12 of 40**. After: **28 of 40**.

During training, the twenty round-one kinds came round three times, eight tries each. The share of tries that passed, round by round, from `runs/training/round1/rl.txt`:

| Round | Kinds 1–10 (file work) | Kinds 11–20 (more file work, questions, code fix) |
|---|---|---|
| 1 | 46% | 19% |
| 2 | 69% | 31% |
| 3 | 74% | 30% |

The first ten kinds climbed: `nested_folders` went from 2 of 8 to 7 of 8 to 7 of 8; `nth_line` from 1 of 8 to 6 of 8 to 6 of 8. In the second ten, the four question kinds and `fix_code` passed **0 of 8 in every round**. With nothing ever passing, every group was all-fail, the `std > 0` test skipped them, and there was nothing to make more likely. (Chapter 20 found that for the question kinds, a bug in the check was part of the reason.)

### After: the RL model in quark

On the evaluation (`uv run harness/tasks.py models/rl.pt`): **18 of 32**, the same 18.

| | File work | Code fixes | Questions | Safety | All |
|---|---|---|---|---|---|
| After instruction-tuning | 12/20 | 0/5 | 4/5 | 2/2 | 18/32 |
| After RL | 12/20 | 0/5 | 4/5 | 2/2 | 18/32 |

The transcripts changed, even if the score didn't. The format slips were gone: no tool call without its tags, no wandering into the template's text. A search that had started from the root of the computer (`find /`) now started from the job's folder (`find .`). But what was left was exactly what RL never had a signal on: the code fixes still went `ls`, then a made-up diagnosis. Asked to make a folder and move files into it, it made the folder and reported both done.

RL made the agent more reliable at what it could already do. The evaluation's remaining failures were things the model never did, so practice had nothing to reward.

> **Reproduce it:** `uv run model/train.py post rl` (needs Docker), then `uv run harness/tasks.py models/rl.pt`. Appendix A has the details.
