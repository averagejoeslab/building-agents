# Part V: The Method

## 21. Building an Agent from Scratch

Here is the whole path, as a lab walks it and as this book did, at the scale of one computer:

| Step | A frontier lab | This book |
|---|---|---|
| **The model** | Its own architecture | Qwen3's design, built from nothing and checked against Qwen's |
| **Pre-training** | Trillions of tokens, a large model | Ours on Shakespeare; then Qwen3-0.6B-Base's trained numbers |
| **Mid-training** | Chosen data, including recorded agent sessions | Shell command pages |
| **Post-training** | Broad conversations; then the agent's own sessions | Public conversation, command, reasoning, tool and code data |
| **The harness** | Its own loop, tools and production hardening | quark: five parts, six production concerns |
| **The evaluation** | Held-out task suites in the harness, and safety evaluations | 32 tasks, never trained on |
| **Training in the harness** | Agent sessions in the harness's format, checked and decontaminated; RL in many environments, on long tasks, with graders for results, helpfulness and safety | Verified sessions from twenty kinds of training task; RL on their checks |
| **Every stage** | Held-out data for what the stage trains; the agent's evaluations from post-training on | The same |

What we couldn't match was size: of the model, the data, the environments, the tasks, the safety training, and the number of rounds. The method is the same.

### The method, in order

1. **Know what an agent is.** A loop: perceive, decide, act, again. A model to decide; a harness for everything else.
2. **Build the model.** Seven parts, from tokenizer to generation. Check it against a known one.
3. **Pre-train it** on as much text as you can, for language and knowledge. Check it on held-out text.
4. **Mid-train it** on what the job needs. Check it on held-out material from that field.
5. **Post-train it** to take turns and follow requests. Check it on held-out conversations.
6. **Build the harness:** model interface, input, output, control flow, context. Make it ready to leave running: persistence, safety, observability, resilience, performance.
7. **Build the evaluation:** tasks with known answers, checked by what was done, never trained on.
8. **Train the model in its harness:** first by example, with real sessions in the harness's own format; then by practice, on tasks it passes some of the time.
9. **Check every stage twice:** on its own held-out data, and as an agent, in its harness, on the evaluation.
10. **Let what fell short decide the next round.** Change the data, not the evaluation. Fix the checks when they're wrong. Train again.

### The whole method, as pseudocode

```
procedure BUILD_AGENT(job):
    model   ← ARCHITECTURE()                                  -- Ch 5: seven parts; check against a reference
    model   ← PRETRAIN(model, all text)                        -- Ch 7: next token, everywhere
    model   ← MIDTRAIN(model, text for the job)                -- Ch 8: next token, chosen data
    model   ← INSTRUCT(model, conversations)                   -- Ch 9: assistant tokens only
    harness ← HARNESS(input, context, model_interface, output, control_flow)   -- Ch 10–13
    harness ← HARDEN(harness, persistence, safety, observability, resilience, performance)  -- Ch 14
    eval    ← TASKS(job, known answers, checks of what was done)              -- Ch 15
    assert eval(harness(capable model)) is perfect             -- the body is proven
    loop:                                                      -- rounds
        model ← INSTRUCT(model, verified sessions in harness)  -- Ch 17
        model ← RL(model, harness, training tasks passed sometimes)   -- Ch 18
        score ← eval(harness(model))                           -- Ch 19
        if score is good enough: ship harness(model)
        gaps  ← DIAGNOSE(failures)                             -- which part, which stage
        change the data, the curriculum, or the checks for the gaps   -- Ch 20
        -- never change the evaluation to fit the model
```

Every line has a check, and every check runs on data the line never trained on.

### What to remember

A model is a mind that predicts the next token. Everything it knows comes from training, and what it does with that knowledge comes from post-training. A harness is the body that lets the mind perceive, remember and act. And the mind works best in the body it was trained in. The last step, training the model in its own harness, is where a model becomes *this* agent.

Every number in this book came from a real run. Most of them are small. That's the point. The path from nothing to an agent is the same at every scale; only the size changes. Build the model and train it in stages; build the harness and its evaluation; train the model in its harness; check every stage twice; and let what fell short decide the next round.

That's how you build an agent from scratch.
