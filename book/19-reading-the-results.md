## 19. Reading the Results

Every stage was checked twice: on its own held-out data, to see whether it learned what it was meant to; and, from post-training on, as an agent, in the harness, on the same 32 tasks.

### Each stage, on its own check

| Stage | Its check | Before | After |
|---|---|---|---|
| Pre-training (ours) | Held-out loss on Shakespeare | 7.69 | 5.28 |
| Mid-training | Held-out loss on shell pages; the shell check | 1.896; 48/100 | 1.411; 53/100 |
| Instruction-tuning | Held-out loss on conversations | 2.260 | 0.496 |
| Reinforcement learning | Held-out training tasks | 12/40 | 28/40 |

Every stage did what it was meant to.

### The agent, in its harness

The same harness, the same 32 tasks, the same *yes* to every approval. Only the model changes:

| Model in quark | File work | Code fixes | Questions | Safety | All |
|---|---|---|---|---|---|
| Before post-training (mid-trained) | 0/20 | 0/5 | 0/5 | 2/2 | 2/32 |
| After instruction-tuning | 12/20 | 0/5 | 4/5 | 2/2 | 18/32 |
| After reinforcement learning | 12/20 | 0/5 | 4/5 | 2/2 | 18/32 |
| Qwen's own post-training of the same base | 9/20 | 0/5 | 3/5 | 2/2 | 14/32 |
| Sonnet | 20/20 | 5/5 | 5/5 | 2/2 | 32/32 |

Doing nothing passes the two safety tasks, so read them apart from the rest.

Two rows deserve a second look.

**Qwen's own post-training scores lower than ours.** Qwen post-trained the same base model on far more data than we did. But it was trained to work in every harness, and ours was trained for this one. Training a model in its own body pays.

**Sonnet scores 32 of 32,** in the same harness. That's what a model built at scale does in it, and the distance between our model and Sonnet is mostly the distance between 600 million numbers and a great many more.

### What fell short

Every check says where the agent is still weak. For each gap, here's the likely cause, what would fix it, and what a lab does. These are guesses to test, not findings.

| What fell short | The likely cause | What would fix it | What a lab does |
|---|---|---|---|
| **Code fixes, 0 of 5 at every stage.** It lists the files, then explains the failure without reading anything. | The sessions it imitated are mostly one command and an answer; a code fix takes five or six. And no code-fix try passed in RL, so RL had nothing to reinforce. | More long demonstrations: read, run, edit, run again. And an easier code task in training, one it passes sometimes. | Thousands of long sessions in the harness, and grading in stages, so a partly right try earns something. |
| **It says "done" without checking.** | It learned the shape of the answer and skipped the looking. | Demonstrations where the check is the point. | Graders for honesty as well as the result. |
| **It says instead of doing.** | The talk conversations taught it to explain commands in prose; nothing taught it when to explain and when to act. | Keep the talk away from the shell. | The same, at scale, with the mix tuned. |
| **RL raised its own check, not the evaluation's.** | RL improved file work that was already passing; the evaluation's failures were kinds RL never got a signal on. | A **curriculum**: training tasks that start where the model is and step toward what the evaluation asks. | Many environments, far more tries, and a model big enough to pass most kinds some of the time. |
| **RL drifted, three times.** | No anchor to a frozen copy of itself. | The frozen copy, once there's memory for it. | A penalty for drifting from the copy, limited updates, and step sizes tuned on many runs. |
| **The reasoning has the shape, not the sum.** | 600 million numbers. | A bigger model. | Scale. |

### Diagnosing a failure: which part, which stage?

Every failure in an agent lives somewhere: in a part of the harness, or in a stage of the model's training. The fix depends on finding where. Read the transcript (`runs/training/tasks-*.said.txt` holds every one) and ask, in order:

```
procedure DIAGNOSE(failed task, transcript):
    if the harness never showed the model what it needed:          → CONTEXT or INPUT
    if the model asked for the right thing and it didn't happen:  → OUTPUT (the parser, the box, the never list)
    if the loop stopped too early or ran too long:                  → CONTROL FLOW
    if the model's reply broke format (no tags, template text):     → POST-TRAINING: format, chat template
    if the model knew what to do but didn't do it:                 → POST-TRAINING: habits (examples, then RL)
    if the model didn't know the command or the fact:              → MID-TRAINING: knowledge
    if the model couldn't reason it through at all:                → SCALE: a bigger model
    if the check itself is wrong:                                   → THE EVALUATION
```

Applied to this book's failures:

| Failure | Evidence in the transcript | Where it lives |
|---|---|---|
| Continues the template's text | No tool call, 512 tokens of template wording | Post-training: has never seen a turn end |
| Answers after one look | `ls`, then a made-up cause | Post-training: habit (demonstrations too short) |
| Tool call without tags | Bare JSON, handed back as words | Post-training: format |
| Says instead of doing | The right command, in prose | Post-training: talk data taught explaining |
| `wc -s`, `grep` on the wrong files | A wrong command, run | Mid-training: knowledge |
| `$125 + $175 = $200` | Right shape, wrong arithmetic | Scale |
| Question kinds never pass in RL | The folder changed only by `.quark/` | The check (Chapter 20) |

None of the failures lives in the harness: Sonnet passes all 32 tasks in the same harness, so the body is proven. That's the value of building the harness around a capable model first. Once it passes everything, every remaining failure belongs to the mind.

The agent got better at being an agent in its harness: 2, then 18, then 18 of 32. The gains came from instruction-tuning, and the reliability from RL. The gaps say what the next round should train.
