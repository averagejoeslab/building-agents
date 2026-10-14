## 18. Learning from Its Own Tries

**Goal:** do the work reliably.

The second way to teach a model its body is practice: **reinforcement learning**, or RL. Instead of copying examples, the model tries the work itself, and each try is graded. Tries that earned a good grade are made more likely.

For an agent, a try is a task done in its harness. That's why the harness had to exist first: it's where the practice happens.

### How it works

1. **Pick a training task.**
2. **Let the agent try it eight times,** in quark, each in a fresh folder.
3. **Grade each try by what it left behind:** the task's check runs on the folder. What the agent *said* doesn't count.
4. **Make the passing tries more likely,** by training on them.

There's a catch built into step 4. If all eight tries pass, or all eight fail, they don't differ, and there's nothing to learn about what made the difference. RL learns from the difference between a try that worked and one that didn't.

### One idea, two uses

Instruction-tuning and RL turn out to be the same operation with different weights. Instruction-tuning makes every example more likely, each weighted equally. RL makes the model's own tries more likely, weighted by how they did: a pass counts, a fail doesn't. Both are *make this text more likely, this much*.

### Three tries that failed

A lab's RL also makes failed tries *less* likely, weighing each try against the others in its group. And it keeps the model from drifting too far by penalizing it for straying from a frozen copy of itself.

We tried the first half without the second, because a frozen copy would need a second model in memory, and this computer doesn't have the room. Each failure is kept in the repository:

- **Pushed both ways,** making wins more likely and losses less likely, the model broke in two steps.
- **With a fifth of the step size, and each try's push limited,** it learned for two rounds, then came apart in the third.
- **Keeping only the wins,** at the step size instruction-tuning used, it broke too.

Pushed away from its own words with nothing to anchor it, a model this small drifts off its format. Once every try fails, there's no signal left to come back on. What worked was the simplest version: **keep the wins, leave the losses alone, and take small steps**, a tenth the size of instruction-tuning's. Learning from its own words, the model needs a light touch.

### Checking it

RL gets its own held-out check: 40 training tasks, in folders it never trains in. Before RL, the agent passes **12 of 40**. After, **28 of 40**.

During training, the twenty kinds of task came round three times. The share of tries that passed, round by round:

| Round | First ten kinds | Second ten kinds |
|---|---|---|
| 1 | 46% | 19% |
| 2 | 69% | 31% |
| 3 | 74% | 30% |

The first ten kinds are file work, and they climbed: one kind went from 2 of 8 tries passing to 7 of 8. The second ten include the question kinds and the code fix, which never passed a single try, in any round. There was nothing to make more likely. (The next round would find that for the question kinds, part of the reason was a mistake in their check, not the model.)

### After: the RL model in quark

On the evaluation: **18 of 32. The same 18.**

The transcripts changed. The format slips were gone: no more tool calls without their markers, no more wandering into the template's text. A search that had started from the whole computer now started from the job's folder. But what was left was exactly what RL never had a signal on. The code fixes still went: list the files, then an invented diagnosis. Asked to make a folder and move files into it, it made the folder and reported both done.

RL made the agent more reliable at what it could already do. The evaluation's failures were the things it couldn't do at all, and practice can't reward what never happens.
