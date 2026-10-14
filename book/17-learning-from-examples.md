## 17. Learning from Examples

**Goal:** take turns, call the tool in the harness's format, and stop.

The first way to teach a model its body is to show it: **instruction-tuning** on recordings of the agent at work, in its own harness, in its own format. Chapter 9 described the public conversations in the mix. This chapter is about the most important part of it: 900 sessions of quark doing real work.

### Making the examples

The examples come from **training tasks**: twenty kinds of work, kept apart from the evaluation's tasks. They include the last lines of a log, a total from a spreadsheet file, a setting changed in a configuration file, a failing test fixed, and a question answered without changing anything. They use other files, and other words.

Each training task has three things: a request, a reference solution, and a check of the result. A demonstration is made by running the reference solution in the harness, every command really run and every result real. It's kept only if the check passes.

Every demonstration shows the same habits: **look, act, check, then answer from what was seen.** Asked to set a configuration value and leave the rest alone, a demonstration changes the file, then reads it back, then answers from what it read: *"Done: config.json now has debug set to true."*

As in Chapter 9, the model learns only from the assistant's turns: its tool calls, its checks, its answers. The command results, written by the world, are read but not learned. The model is learning to be the agent, not to imitate the shell.

### Keeping the exam clean

Nothing the model trains on may resemble what it's scored on. Every public conversation is compared with every evaluation request, and anything sharing 40% or more of its words with one is left out. That rule caught one public example that was nearly an evaluation task word for word. The training tasks are kept apart by design, and the run reports the closest pair it found, so anyone can see what overlap remains: two requests sharing 43% of their words, all of it the instruction *"Don't change anything,"* which every question task shares.

### After: the instruction-tuned model in quark

On held-out conversations, the loss fell from **2.260 to 0.496** (Chapter 9). In the harness, on the evaluation, the score rose from **2 of 32 to 18 of 32**: file work 12 of 20, questions 4 of 5, safety 2 of 2, code fixes 0 of 5.

The passes are one command and a plain answer: make a folder called stone; *"Done: a folder called stone exists."* The failures are of three kinds:

- **It answers after one look.** Every code fix went the same way: it listed the files, then explained why the tests fail, an invented explanation, without reading a file or running a test.
- **The format slips.** A second tool call came out without its tool-call markers, so the harness read it as words and handed back.
- **It says instead of doing.** Asked to add a line to a file, it explained the right command instead of running it.

Each of these is a habit, not a lack of knowledge. It knows the commands. It doesn't reliably *do* them. Habits are what the second kind of training, practice, can change.

But practice has a precondition. Reinforcement learning can only make more likely what the model already does *some* of the time. If it never does the right thing, there's nothing to reinforce, and the examples need fixing first. Here, it gets 18 of 32 right. That's a foothold.
