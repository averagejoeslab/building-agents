# Add long-term memory

> **Harness component: persistence.** What survives when the process exits. quark's long-term memory is a plain markdown file that the model reads and writes with its own body — and the harness implements it without a single new line of Python.

Working memory (Module 6) is volatile: quit the agent and it's gone. Long-term memory is what lets an agent recognize you next week, remember the paths it learned in your project, and keep the corrections you gave it.

Most harnesses build this in code: serialize the conversation, embed summaries into a vector store, retrieve the nearest ones and inject them into the prompt. quark does something much simpler, and it's the purest example of the rule *the model handles what it can; code handles what it must*. The model already has a body that can write files and search them. So the harness doesn't build memory. It **teaches** it.

## The checkpoint

[`examples/07_long_term_memory.py`](../../examples/07_long_term_memory.py) has exactly the same code as Module 6. The only change is the system prompt. Diff the two files and the prompt string is the whole diff.

## What the prompt adds

A new entry in the Self Model:

```markdown
**Long-term memory:** `.quark/memory/memory.md` — your memory extended into the world for persistence across sessions.

Initialize if missing:
mkdir -p .quark/memory && [ ! -f .quark/memory/memory.md ] && echo "# Quark Memory" > .quark/memory/memory.md

Format (preserve exactly):
## YYYY-MM-DD HH:MM:SS
- one observation per bullet, phrased with the words future-you will grep for

Write (required — timestamp expands in the printf; bullets stay literal in the quoted heredoc):
printf '\n## %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> .quark/memory/memory.md && cat >> .quark/memory/memory.md << 'EOF'
- Learned X
EOF

Worth writing (your discretion): what other selves teach you — who they are, what they prefer, corrections to how you operate. A lesson not written is lost when the session ends.

Memory is a timestamped stream; the format contract above is what makes it queryable. Reads are questions answered by composing any text tools over it — common moves:
- slice by time — `tail -50 .quark/memory/memory.md`, `grep "## 2026-05" .quark/memory/memory.md`
- filter by content — `grep -i "topic" .quark/memory/memory.md`
- expand around matches — `grep -B 2 -A 10 "topic" .quark/memory/memory.md`
- index every entry — `grep "^## " .quark/memory/memory.md`

These are moves, not a menu — derive the read that answers what you actually need to know.
```

And three smaller edits elsewhere in the prompt:

- **Acts** gains `on self: long-term memory writes (recipe above)`.
- **Observes** gains `of self: long-term memory reads`.
- The **grounding gradient** gains a step: `mind (already in context) → memory → world → asking other selves`.

Writing to memory is acting on yourself; reading it is observing yourself. The three-target picture from Module 5 — self, world, other selves — is now complete.

## Why each piece is there

Every line of that section was earned in a live session. That's the part worth studying, because it's what *engineering a prompt* looks like in practice:

- **A format contract.** `## YYYY-MM-DD HH:MM:SS` headers with one bullet per observation. Memory is a timestamped stream, and the contract is what makes it queryable: `grep "## 2026-05"` only works if every header looks the same.
- **A write recipe split in two.** An earlier version used one heredoc for the whole entry. That forces a choice: an *unquoted* heredoc expands `$(date)` for the timestamp but also mangles any `$` or backtick in the content; a *quoted* one keeps content safe but can't expand the date. In practice the model reliably chose safety and then improvised the header (`## 2026-06-10 (session start)`), breaking the contract. The fix was mechanical, not a louder instruction: `printf` writes the header (expanded), then a quoted heredoc writes the bullets (literal). The safe path became the correct path.
- **Write for retrieval.** "Phrased with the words future-you will grep for." No read strategy can find an entry like *discussed the thing from earlier*. Whether a memory is findable is decided when it's written.
- **What's worth writing.** Mechanics alone weren't enough: quark knew *how* to remember but not *when*. Asked for its user's name, it ran `finger` against the system while its own memory said who it had met — and when that was pointed out, it worked out the right policy and then never wrote it down. Hence the grounding gradient puts memory before the world, and the prompt says plainly that a lesson not written is lost. It's guidance, not a mandate: what to persist stays the model's call.
- **Reads as questions, not a menu.** The four "moves" were originally derived by quark itself in a session about its own memory. They're framed as examples — "moves, not a menu" — because a closed list made the model pick from the list instead of composing the read it actually needed (counting entries, say, or joining two greps).

## Memory as system prompt learning

There's a deeper idea here. Model weights are frozen; there are only two ways to get new behavior into a model — change its weights (training, which belongs to the labs) or change what's in its context (which belongs to whoever owns the harness). quark's memory file is the second kind of learning, owned entirely by the harness: the agent writes down what it learned, and the next session reads it back.

quark's own prompt went through exactly this loop. Several lines you've read in Modules 5 and 7 were first derived by quark in a session, written into its memory, and then promoted into the system prompt by hand. Andrej Karpathy calls this **system prompt learning**; [the model background doc](../../docs/the-model.md) covers where it sits relative to training. The model is frozen; the harness is what gets smarter.

## Run it

```bash
cd examples
uv run 07_long_term_memory.py
> my name is Chase and I prefer short answers
> /q
uv run 07_long_term_memory.py
> what's my name?
```

In the first session, watch for the `printf … >> .quark/memory/memory.md` act. In the second, quark should answer from a `grep` of its memory rather than guessing or searching the system. Look at `.quark/memory/memory.md` yourself afterwards — it's just a file, and you can read and edit it too. (The repo's `.gitignore` excludes `.quark/`, so memory stays local.)

## What's missing

- **You can't stop it mid-act.** If a command hangs or the model heads somewhere you didn't want, your only option is Ctrl+C, which kills the agent and everything in its working memory.

Module 8 gives the human a way to interrupt without losing the agent.

---

**Next:** [Module 8: Add interrupts](../08-add-interrupts/)
