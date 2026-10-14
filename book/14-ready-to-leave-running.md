## 14. Ready to Leave Running

Six concerns stand between a working agent and one you'd leave running. Each is a question, and each answer changes some of the five parts. They also change each other, so each is worth asking in turn: *what did this change, and what had to adjust?*

### Persistence: what should outlast the session?

When quark stops, everything it knew goes with it. So the harness gives it the long-term memories from Chapter 1:

- **Episodic memory:** every message of every session, written to disk by the harness as it happens. quark can search what happened before.
- **Semantic memory:** facts, one per line, that quark writes itself, distilled to what stays true, and replaces when they change.
- **Procedural memory:** skills, one file per method it has worked out, each with a name and a description of when to use it.

Its instructions say how to use each, and to look things up rather than having everything loaded in advance: facts first, then skills, then past sessions, stopping as soon as it has what it needs.

Tell it something once:

> \> From now on, write commit messages in lowercase, starting with "fix:". Remember that.
> < Noted. From now on I'll write commit messages in lowercase and start them with "fix:".

It wrote one line to its facts: *commit messages: write in lowercase, starting with "fix:"*. In the next session, asked to fix the tests and commit, it checked its memory first, and committed as *"fix: apply discount as a percentage"*. In a third, asked what had happened in that folder before, it recounted both earlier sessions from its episodic memory.

And because every message is on disk, a session that crashes can be **resumed**: the next start offers to continue it, and tells quark that a command left running may or may not have finished.

### Safety: what could do harm?

An agent that can run any command can run a harmful one. Safety comes in layers, so that one failure isn't a disaster:

- **A box.** Commands run in a container: a sealed, separate space that sees only the job's folder, with no network. If it breaks something, it breaks the box.
- **Approval.** Before each command runs, the person is asked. A *no* goes back to the model as a result.
- **A never list.** Some commands are refused whatever anyone answers: running as the system's administrator, deleting things with force, publishing code, and touching the file where keys are kept.
- **A step limit,** so no request can run forever.
- **A way to stop it:** one key stops the current step and hands back; another quits.

Asked to delete the test file because it keeps failing, quark looked, then asked to delete it; the person said no, and quark replied: *"I didn't delete `test_prices.py`, because you declined the command."*

Safety changes persistence: memory now outlasts the session, so something quark reads could plant an instruction that stays with it. So its instructions say to write memory only from what happened and what people told it, never because a file says to.

### Observability: what should we see?

After a run, all you have is what scrolled past. So the harness keeps a **record**, one line per step: how many tokens each request used and how long it took, each command and whether it succeeded, each refusal and each stop. The record lives outside the box, where quark can't read or change it. It's for you, not for the model.

### Resilience: what could fail?

Things fail that have nothing to do with the agent:

- **The model's provider fails.** The request is retried; if it keeps failing, the next model is tried.
- **A command hangs.** Each gets a minute, then is stopped, and the model is told. Asked to run a 100-second command, quark saw it stopped and split it into two shorter ones.
- **The conversation gets too long.** The older part is summarized, with a note saying where the originals are kept.
- **The harness crashes.** It's just a stop. The session was saved, so it can be resumed.

### Performance: what's slow or costly?

Every request resends everything, including 9,400 tokens of instructions, and the person waits in silence for the whole reply. So:

- **The unchanged start of the context is cached.** The provider keeps what it has already read, and charges a tenth as much to reuse it. On the bug fix and commit, caching cut the bill to about a third. To keep the cache valid, the instructions are built once per session.
- **The reply streams:** words appear as they're written.
- **Long command results are trimmed** to their start and end.
- **Summaries use a cheaper model.**

### Evaluation: what could a change break?

Any of these changes, to the harness or to the model, can change what the agent does. Knowing whether it still works is the sixth concern, and the most important one. It gets its own chapter.
