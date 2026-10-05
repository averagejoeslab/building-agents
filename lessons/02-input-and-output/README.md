# Lesson 2: Input and output

> 🎥 **Video:** coming soon

**You build:** how inputs are gathered, and how outputs are handled: shown to a person or run as a tool.
**You end with:** [`agent.py`](./agent.py), 23 lines.

---

## Explain

Input and output are two primitives, built independently. They're taught together because they're the two ends of one exchange: output is how the model reaches the world, input is how the world reaches the model.

**Input** gathers what goes in. It has two sources:

- **A person.** Someone types a message, asks a question, gives a task.
- **The world.** The result of something the harness did: a command's output, a file's contents, an error.

**Output** handles what comes out. It has two destinations:

- **A person.** The model's words are shown to someone.
- **The world.** The model asks for a tool, and the harness runs it.

A tool is how a model acts. The model can only produce tokens, so it can't run a command. What it can do is produce tokens that *ask* for one: a tool name and arguments, in a shape the harness agreed on. The harness reads the request, runs it, and the result comes back as input. The model asks, the harness acts.

You don't strictly need tools to have an agent. A model that can only talk still perceives and responds. But without tools, the only thing it can change is what a person reads. Most of what we want from an agent needs it to act.

Every input and output primitive comes down to these mechanisms:

- **Input:** receive something, and put it in a form the model interface can send.
- **Output:** look at what came back, route each part to its destination, and capture what happened.

Everything else is a choice. Where input comes from: a terminal, a chat app, a webhook, a file, a schedule. Where output goes. Which tools exist, and how many: one general tool, or many specific ones. What a tool's result looks like when it fails, or is cut off.

## Show

quark's input is one line:

```python
working_memory = [{"role": "user", "content": next(u for u in iter(lambda: " ".join(sys.argv[1:]).strip() or input("> "), None) if u.strip())}]
```

It reads the task from the command line if you gave one, otherwise it prompts you with `> `, and keeps prompting until you type something that isn't blank. A blank message would be a wasted call.

quark's tools are one tool:

```python
client, MODEL, body = Anthropic(), "claude-sonnet-4-5", [{"name": "bash", "description": "Run shell command — the whole system is in reach", "input_schema": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}]
```

A tool definition is a name, a description the model reads to decide when to use it, and a JSON schema for its arguments. quark calls the list `body`, because it's how quark acts on the world. And it gives quark exactly one tool: `bash`. Anything you can do from a command line, quark can do: read files, write files, run programs, install more tools. That's the choice. One general tool instead of twenty specific ones. The cost is that nothing narrows what the model can do. That's why the setup warns you to run this somewhere you can afford to lose.

The model interface sends the tools along: `tools=body`.

quark's output starts by keeping the reply and finding what the model asked for:

```python
working_memory.append({"role": "assistant", "content": saying.content})
calls = [b for b in saying.content if b.type == "tool_use"]
```

The words were already shown to the person while they streamed. That's output to a person, done in Lesson 1. What's left is output to the world. Each tool request is a `tool_use` block with an `id` and an `input`.

Then it runs each one:

```python
results = []
for c in calls:
    if "cmd" not in (c.input or {}) or (saying.stop_reason == "max_tokens" and c is calls[-1]):
        results.append({"type": "tool_result", "tool_use_id": c.id, "content": "[your doing was cut off before it was fully formed — it never reached the world]"}); continue
    print(f"$ {c.input['cmd']}")
    doing = subprocess.run(c.input["cmd"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = doing.stdout.decode(errors="replace")
    if out: print(out, end="")
    results.append({"type": "tool_result", "tool_use_id": c.id, "content": out or f"(exit {doing.returncode})"})
working_memory.append({"role": "user", "content": results})
```

The pieces worth noticing:

- **The cutoff guard.** If the model hit `max_tokens` while writing a command, that command is incomplete. Running half a command is worse than running none. So quark doesn't run it, and tells the model why. This is why Lesson 1 kept `stop_reason`.
- **`print(f"$ {c.input['cmd']}")`.** The person sees what's about to run. Output goes to both destinations at once.
- **`stderr=subprocess.STDOUT`.** Errors and normal output arrive as one stream, in the order they happened. The model sees what you would have seen.
- **`out or f"(exit {doing.returncode})"`.** A command that prints nothing still tells the model something: whether it worked.
- **The `tool_result`.** Each result names the `tool_use_id` it answers. All the results go back in one `user` message. That's the shape the model expects, and it's the harness gathering input from the world.

> quark's own version reads command output in chunks instead of all at once, so pressing ESC can stop a command partway through. That's hardening, so it's left out here. What's above is the primitive.

## Do

1. **Type it.** Add the input line, the tool, `tools=body`, and the output code to your `agent.py`. Run it with a task:

   ```bash
   uv run agent.py "what's in this directory?"
   ```

   You should see the model ask for a command, the command run, and its output print.

2. **Make one change of your own.** Pick one, or invent your own:
   - Add a second tool, like `read_file` with a `path` argument, and route each call by `c.name`. Does the model pick the right one?
   - Print `working_memory` at the end. Find the `tool_use` and the `tool_result` that answers it.
   - Take input from somewhere other than the terminal: a file, an environment variable, standard input.
   - Ask for confirmation before each command runs.

3. **Check yourself.** If you're stuck, compare against [`agent.py`](./agent.py) in this folder.

## Recap

**The rule:** input puts the world into tokens; output puts tokens into the world. A tool is the model asking and the harness acting.

**Questions to check yourself:**
- Name the two sources of input and the two destinations of output in your code.
- Why does a tool result have to name the request it answers?
- What would go wrong if you ran a command the model didn't finish writing?

**What else would have worked:**
- **Many specific tools** (`read_file`, `write_file`, `search`) instead of one general one. Easier to check and limit, more to build, and the model can only do what you anticipated.
- **A different input.** A chat app, an issue tracker, a webhook, a voice transcript. The rest of the harness doesn't change.
- **A different output.** Write to a file, post a message, open a pull request.
- **Tools that run somewhere else.** A container, a remote machine, a provider-hosted tool.

**What's missing:** the result went into `working_memory` and nobody sent it. The model asked for `ls`, `ls` ran, and the model never saw what it found. Something has to send the result back and decide to go again. That's control flow.

**→ [Lesson 3: Control flow](../03-control-flow/)**
