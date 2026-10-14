## 20. The Next Round

The next round changes the data, keeps the evaluation, and trains again from the same mid-trained model.

### What changed

- **Six new training kinds,** aimed at what the agent failed: work in two steps (make a folder and move files into it; find a file, then write its name; measure every file, then pick one; copy a file, then edit the copy), and a code fix with two functions and one bug.
- **More variety:** fourteen shapes of bug instead of seven.
- **A different mix:** public conversations cut from 1,500 to 900, the talk among them filtered to say nothing about shells; the agent's own sessions raised from 900 to 1,500.
- **Stricter demonstrations:** one is kept only if its last command before answering was a look: reading a file, listing a folder, counting, running the tests.

### Three bugs, found first

Before the new round produced a result, it found three mistakes. Each cost a run.

**The chat template is part of the model.** Qwen's template puts an empty thinking block into some assistant turns and not others. Trained on that mix, the first round-two model dropped or doubled its tool-call markers whenever a session had more than one step, and every multi-step task failed. The fix: lay out every training conversation the same way, with no empty block anywhere, and end the prompt exactly where the turn began.

**A check can be wrong.** The question tasks pass only if nothing in the folder changed. But in the harness, the folder gains quark's own memory folder, so in training those tasks could never pass, whatever the model did. In round one, they scored zero at every step for that reason, not the model's. The evaluation already ignored the memory folder; the training check now does too.

**A task that runs out of time is a result.** Three code fixes in the evaluation ran past their ten minutes. Round one's model gave up after listing the files. This one ran the tests, read the failure, and kept going, and ran out of time.

### Instruction-tuning, round two

Held-out loss: **1.940 to 0.287** (round one: 2.260 to 0.496). In quark, on the evaluation: **18 of 32 again, but not the same 18.**

| Model in quark | File work | Code fixes | Questions | Safety | All |
|---|---|---|---|---|---|
| Round one, after instruction-tuning | 12/20 | 0/5 | 4/5 | 2/2 | 18/32 |
| Round two, after instruction-tuning | 13/20 | 0/5 | 3/5 | 2/2 | 18/32 |

The transcripts changed more than the score. Multi-step tasks that round one never passed now pass. Every task begins with a look and ends with a check. The code fixes list the files, run the tests, read the error, and then stall or run out of time, where round one invented a cause. The new failures are commands it half-knows: the wrong option for counting, a search for the wrong kind of file, a "program" that's just the word it was meant to print.

### Reinforcement learning, round two

Its own check, before training: **37 of 40** (round one, under the broken check, 12 of 40). Then one full round over all 26 kinds, eight tries each: 25 kinds passed **8 of 8**, and one passed **0 of 8**.

No group was mixed, so no update happened. The model after 26 steps was the model before.

### The arithmetic of a useful group

Round two's RL did nothing because every group was all-pass or all-fail. How likely is that? If a model passes a kind of task with probability *p*, and tries it *G* times independently, the chance that the group is **mixed**, so that it has something to learn from, is:

```
P(mixed) = 1 − p^G − (1 − p)^G
```

For groups of eight:

| p (chance of passing) | P(all pass) | P(all fail) | P(mixed): a useful group |
|---|---|---|---|
| 0.00 | 0.00 | 1.00 | 0.00 |
| 0.05 | 0.00 | 0.66 | 0.34 |
| 0.20 | 0.00 | 0.17 | 0.83 |
| 0.50 | 0.004 | 0.004 | 0.99 |
| 0.80 | 0.17 | 0.00 | 0.83 |
| 0.95 | 0.66 | 0.00 | 0.34 |
| 1.00 | 1.00 | 0.00 | 0.00 |

RL learns fastest on tasks the model passes about half the time, and not at all at the ends. Round two's model passed 25 kinds at *p* ≈ 1 and one at *p* ≈ 0: the worst curriculum for RL, which came from making the model better at the kinds RL trains on.

A **curriculum** keeps tasks in the middle. In practice that means measuring each kind's pass rate first, dropping the kinds near 1 or making them harder, adding easier variants of the kinds near 0, and re-measuring as training goes. Labs do this at scale, with thousands of task kinds and difficulty levels, so that some always sit in the useful band.

### What round two says

Data moved the agent from guessing to working: it looks, acts, checks, and reports what it saw, the four habits the demonstrations teach. It did not move the score, because the remaining failures are a different gap: commands it doesn't quite know, and code fixes it can start but not finish. Those are mid-training's job: more shell, more code. That is where the next round would go.

RL needs tasks the model passes some of the time. At 8 of 8 there is nothing to learn; at 0 of 8, nothing to learn from. A curriculum for RL has to sit in between, and move as the model does.
