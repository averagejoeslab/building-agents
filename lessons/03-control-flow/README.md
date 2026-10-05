# Lesson 3: Control flow

> 🎥 **Video:** coming soon

**You build:** how information flows: the loop that sends a result back and goes again.
**You end with:** [`agent.py`](./agent.py), 28 lines. This is the first version that's an agent.

---

## Explain

Control flow is one of the five primitives, and the other four sit inside it. It decides how information moves between them: what runs, in what order, and whether to go again.

You already have input, a model interface, and output. Control flow is what you do with them. The same four pieces give you different things depending on how they're arranged:

- **Run once.** Input, call, output, stop. A single call. That's what you had at the end of Lesson 2.
- **A chat loop.** Call, show the reply, hand back to the person, repeat. A chatbot.
- **An agent loop.** Call, and while the model asks for tools, run them, send the results back, and call again. Hand back when it stops asking.
- **A workflow.** You decide the steps in code: call the model to plan, then to write, then to check. The model fills in each step; your code decides the order.

There's no correct one. An agent loop isn't better than a workflow; it's a different choice about who decides what happens next. In an agent loop, the model decides. In a workflow, your code does.

Whatever you pick, control flow comes down to two mechanisms:

- **Sequence:** run the other primitives in some order, passing what one produced to the next.
- **Termination:** decide when to stop, or when to hand back to a person.

Termination is the one people forget. A loop with no clear way to end is a bill with no clear way to end.

## Show

quark is an agent loop that's also a chat loop. Here's the whole of it:

```python
chat, working_memory = len(sys.argv) < 2, [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]

while True:
    with client.messages.stream(model=MODEL, max_tokens=4096, tools=body, messages=working_memory) as stream:
        ...
    print()
    working_memory.append({"role": "assistant", "content": saying.content})
    calls = [b for b in saying.content if b.type == "tool_use"]
    if not calls:
        if not chat or (u := next(filter(str.strip, iter(lambda: input("\n> "), None)))) == "/q": break
        working_memory.append({"role": "user", "content": u})
        continue
    results = []
    for c in calls:
        ...
    working_memory.append({"role": "user", "content": results})
```

The `...` are the model interface and output from Lessons 1 and 2, unchanged, just indented into the loop. Here's what's new.

**`while True:`**. Go again. Each pass is one call to the model.

**The last line.** It's the same line as in Lesson 2. What changed is that there's a next pass now, so the results get sent. That's the whole difference between running once and an agent: the result goes back.

**`if not calls:`**. Termination. The model decides when it's done working by not asking for a tool. quark doesn't count steps or check for a magic word. When the model replies with only words, its turn is over.

**`chat = len(sys.argv) < 2`**. One loop, two modes. Give quark a task on the command line and it's one-shot: it works until the model stops asking for tools, then exits. Give it nothing and it's chat: when the model's turn ends, it hands back to you with `> `, adds what you type, and goes again. `/q` quits. Same loop either way; the only difference is what happens when the model's turn ends.

**`continue`**. After you type, go straight to the next call. There's no tool result to send, just your message.

Notice what the loop doesn't have: a step limit. quark trusts the model to finish. That's a choice, and it has a cost: if the model never stops asking for tools, quark never stops. A step limit is a guardrail, and guardrails are hardening. You can add one below.

## Do

1. **Type it.** Wrap your `agent.py` in the loop: add `chat`, the `while True:`, the `if not calls:` branch, and indent the rest. Run it both ways:

   ```bash
   uv run agent.py "find the largest file in this directory and tell me what it is"
   uv run agent.py
   ```

   In the first, watch the model run more than one command before it answers. In the second, have a conversation, and quit with `/q`.

2. **Make one change of your own.** Pick one, or invent your own:
   - Add a step limit. What should the harness tell the model, or the person, when it's hit?
   - Count the passes and print the total when the loop ends.
   - Turn it into a workflow: one call to make a plan, then one call per step of the plan, with no tools.
   - Make it a pure chat loop by removing `tools=body`. What can it no longer do?

3. **Check yourself.** If you're stuck, compare against [`agent.py`](./agent.py) in this folder.

## Recap

**The rule:** control flow sequences the other four and decides when to stop. Change it and the same four pieces become a single call, a chatbot, an agent, or a workflow.

**Questions to check yourself:**
- In your loop, who decides when to stop: the model, your code, or the person?
- What's the one line that turns "run once" into an agent?
- What happens if the model never stops asking for tools?

**What else would have worked:**
- **A step limit or a budget.** Stops a runaway loop, and sometimes stops a task that was about to finish.
- **A workflow.** Predictable and easy to test, but only handles the tasks you designed it for.
- **A planner and an executor.** One loop decides what to do, another does it.
- **More than one agent.** One loop hands a task to another and waits for the result.
- **An event loop.** Wake on a message, a schedule, or a file change instead of a person typing.

**What's missing:** this is an agent, but it doesn't know anything. Not where it is, not what day it is, not who it is, not what you told it yesterday. And `working_memory` grows on every pass; in a long session it will outgrow what the model can read. Something has to decide what the model sees. That's context.

**→ [Lesson 4: Context](../04-context/)**
