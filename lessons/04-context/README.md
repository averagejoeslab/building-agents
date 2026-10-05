# Lesson 4: Context

> 🎥 **Video:** coming soon

**You build:** how inputs are presented to the model: who it is, what's happened, what it remembers.
**You end with:** [`agent.py`](./agent.py), 40 lines. This is quark.

---

## Explain

The model knows nothing about this moment except what's in the tokens you send it. It doesn't know where it's running, what day it is, what it did a minute ago, or what you told it last week. Every call starts from nothing. Context is the primitive that decides what's in those tokens.

The mechanism is one sentence: **before every call, assemble what the model should see, and fit it in the space it has.** Two parts:

- **Assemble.** Choose what goes in, and how it's presented.
- **Fit.** The model can only read so many tokens at once: its context window. When what you'd send is bigger than that, something has to give.

Almost everything people build into harnesses is a context component, because almost everything is a way of deciding what the model sees. A few you'll hear about:

- **Instructions:** who the model is, what it's for, how to behave. Usually a system prompt.
- **Working memory:** what's happened in this session. The message list.
- **Episodic memory:** a record of what happened in past sessions.
- **Semantic memory:** facts and lessons that outlast a session: who you are, what you prefer, what went wrong last time.
- **Procedural memory:** how to do things. Recipes, playbooks, skills loaded when they're relevant.
- **Retrieval:** search a store and put what you found in front of the model.
- **Compaction:** when working memory won't fit, replace some of it with a summary.
- **Self-knowledge:** tell the model what it is and how it works.

You don't need all of them. You need the ones your agent needs, built in whatever way fits.

## Show

quark's context has four components. You've already built one of them.

### Working memory

You've been building it since Lesson 1. `working_memory` is every message in this session: what you said, what the model said, what it asked for, what came back. It's sent in full on every call, which is how the model "remembers" what it did two passes ago. That's why it has the name.

### Instructions, world, and self: the system prompt

```python
def system(): return [{"type": "text", "text": f"# Self Model\n\n**Identity:** You are quark ... ", "cache_control": {"type": "ephemeral"}}]
```

The full prompt is one long line in [`agent.py`](./agent.py). Read it there. It's sent as `system=system()` on every call, and it's organized as models of what the agent needs to know:

- **Self Model.** Who it is, that its context window is its mind, that bash is its body, and that it works in a loop.
- **World Model.** Where it is (`os.getcwd()`) and when (`datetime.date.today()`).
- **Other Selves Model.** That you exist, and how to reach you.
- **Body Operations.** How to use its one tool well: small actions, escalate only when needed, look before acting.

Two choices to notice:

**The date, not the time.** `cache_control` tells the API to cache this prompt, so later calls don't pay full price to re-read it. A cache only hits if the prompt is identical. A timestamp would change every second and the cache would never hit. So quark puts the date in context, and tells the model to run `date` if it needs the time. The choice made in context is shaped by the model interface.

**`system()` is a function, not a constant.** It's rebuilt on every call, so the directory and date are always current.

### Self-knowledge: its own source

```python
def mechanics(): return "\n".join('def system(): return "<system prompt redacted so you can see your self mechanics in harness>"' if l.startswith("def system():") else l for l in open(__file__).read().split("\n"))
```

quark reads its own file and puts it at the end of the system prompt, under `# Mechanics`. The model sees the harness it's running in: how the loop works, what happens to a cut-off command, when it gets summarized. The `system()` line is swapped for a placeholder, because the model is already reading it.

### Semantic memory: a file it writes itself

The **Long-term memory** section of the prompt points quark at `.quark/memory/memory.md`, and tells it how to use it: create it if missing, the exact format for an entry, a command for writing one, and ways to read it back with `grep` and `tail`. And what's worth writing: who you are, what you prefer, corrections to how it works.

There's no memory code. quark writes and reads the file with the tool it already has. The harness supplies the instructions; the model does the rest through input and output. That's semantic memory: facts that outlast a session, there for the model to look up.

### Fitting: compaction

Working memory grows every pass. Eventually the API refuses it. quark waits for that to happen:

```python
    except BadRequestError as e:
        if "prompt is too long" not in str(e): raise
        drop += 1
```

and then, at the top of the next pass, summarizes:

```python
        if drop > 0:
            turns = [i for i, m in enumerate(working_memory) if m["role"] == "user" and isinstance(m["content"], str)]
            if drop > len(turns): break
            msgs = working_memory[turns[drop]:] if drop < len(turns) else ([working_memory[turns[-1]]] if turns else working_memory)
            s = next((b.text for b in client.messages.create(model=MODEL, max_tokens=2048, system=system(), messages=msgs + [{"role": "user", "content": "Your working memory is full. Summarize into a gist that preserves what matters for continuing."}]).content if b.text.strip()), "")
            working_memory = [{"role": "user", "content": f"[your prior working memory, summarized] {s}"}]; drop = 0; continue
```

`turns` finds where each of your messages starts. Working memory that's too big to send is also too big to summarize, so quark drops the oldest `drop` turns and asks the model to summarize what's left. Then working memory is replaced by the summary, and the loop goes on. If the summary request is too long too, `drop` goes up by one and it tries again with less. If there's nothing left to drop, quark stops.

The choice here is *reactive*: quark compacts when the API says the prompt is too long, not before. It never spends a call on a summary it didn't need. The cost is that the oldest turns are dropped without being summarized at all.

> quark's own version also retries the summary call if the network fails, and lets you interrupt with ESC. Those are hardening, so they're left out here. Everything else is quark, line for line.

## Do

1. **Type it.** Add `mechanics()`, `system()`, `system=system()` on both calls, and the compaction code to your `agent.py`. Type the system prompt in your own words if you like; it's yours. Run it and ask:

   ```bash
   uv run agent.py
   > what are you, and how do you work?
   > remember that I prefer short answers
   ```

   Quit with `/q`, start it again, and ask what it knows about you. Then look in `.quark/memory/memory.md`.

2. **Make one change of your own.** Pick one, or invent your own:
   - Rename it. Give it your own identity and memory path.
   - Add episodic memory: append every message to a `.jsonl` file, and tell the model where it is.
   - Compact proactively: check `saying.usage.input_tokens` after each call and summarize before you hit the limit.
   - Add procedural memory: a folder of markdown recipes, listed in the system prompt, read when relevant.

3. **Check yourself.** If you're stuck, compare against [`agent.py`](./agent.py) in this folder.

## Take apart a harness you've never read

You've built all five primitives. Now go the other way.

Pick a harness you haven't read. [nanoagent](https://github.com/averagejoeslab/nanoagent) is a good first one: it's another small agent, written in TypeScript. Or pick a big one. Read it and sort what you find under the five primitives:

```
control flow          what kind of loop? who decides when to stop?
├── input             where do inputs come from: people, the world, both?
├── context           what does the model see? which memories? how does it fit?
├── model interface   which model, how is it called, what's kept from the reply?
└── output            where do outputs go? which tools, and how are they run?
```

Some things won't fit at first. Ask what each one does. Is it deciding what the model sees? Then it's context, however it's named. Is it acting on what the model said? Output. Keep asking until it fits. If you find something that genuinely fits none of the five, I'd like to hear about it.

## Recap

**The rule:** before every call, context assembles what the model should see and fits it in the space it has. Memory, retrieval, instructions, and compaction are all ways of doing that.

**Questions to check yourself:**
- Where does each thing the model knows come from in your harness?
- What happens in your harness when working memory is too big?
- Why does quark put the date in its prompt but not the time?

**What else would have worked:**
- **Proactive compaction.** Summarize at a threshold, before the API refuses. Costs calls you might not have needed.
- **Truncation.** Drop the oldest messages without summarizing. Cheap, and the model forgets.
- **Retrieval.** Embed past messages or documents and fetch the relevant ones each call.
- **Memory the harness manages.** Code that decides what to save and load, instead of leaving it to the model.
- **Skills.** Instructions loaded only when a task needs them, instead of all at once.

## You've built a harness

Control flow, input, context, model interface, output. Five primitives, 40 lines, and an agent that works, remembers, and knows what it is. quark is one set of choices. Now you know what the choices are.
