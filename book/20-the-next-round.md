## 20. The Next Round

The gaps in the last chapter are a to-do list. So we did what a lab does with one: **change the data, not the evaluation,** and train again, starting from the same mid-trained model.

### What changed

- **Six new training kinds,** aimed at what the agent failed: work in two steps (make a folder and move files into it; find a file, then write its name; measure every file, then pick one; copy a file, then edit the copy), and a code fix with two functions and one bug.
- **More variety:** fourteen shapes of bug instead of seven.
- **A different mix:** public conversations cut from 1,500 to 900, the talk among them filtered to say nothing about shells; the agent's own sessions raised from 900 to 1,500.
- **Stricter demonstrations:** one is kept only if its last command before answering was a look: reading a file, listing a folder, counting, running the tests.

### Three bugs, found first

Before the new round produced a result, it found three mistakes. Each cost a run. Each is the kind of thing a lab's pipeline is built to catch.

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

Not one group was mixed. So not one update happened. The model after 26 steps was the model before, to the last digit.

### What round two says

Data moved the agent from guessing to working: it looks, acts, checks, and reports what it saw, the four habits the demonstrations teach. It did not move the score, because the remaining failures are a different gap: commands it doesn't quite know, and code fixes it can start but not finish. That's not post-training's job. It's mid-training's: more shell, more code. That's where a lab would spend the next round.

And RL taught its sharpest lesson by doing nothing. Practice needs tasks the model passes *some* of the time. At 8 of 8 it has nothing to learn; at 0 of 8, nothing to learn from. A curriculum for RL has to sit in between, and move as the model does.
