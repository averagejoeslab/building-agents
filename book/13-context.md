## 13. Context: What It Knows

**Context** is everything the model is shown each time it's asked to write. It's the agent's **working memory**: whatever is in it, the agent has in mind; whatever isn't, it doesn't. And because the model remembers nothing between calls, the harness assembles it fresh, every time.

### Parts of a context

In the Messages format, a context has three parts, and the model was trained to treat each differently:

| Part | Field | What it holds | How the model treats it |
|---|---|---|---|
| **System prompt** | `system` | Who the agent is, how it should work | The most authoritative text: instructions to follow |
| **Tools** | `tools` | What it can do, and how to ask | Capabilities; it emits matching `tool_use` blocks |
| **Conversation** | `messages` | What people said, what it said and did, what came back | The situation, in order |

Underneath, all three are tokens laid out by the chat template (Chapter 9). The roles are markers the model learned in training, and the training is what gives the system prompt its weight.

### The smallest useful context

`quark.py` adds one function and routes every call through it:

```python
def assemble_context(conversation):
    instructions = f"You are quark, an agent. You act through bash, in {os.getcwd()}. Today is {datetime.date.today()}."
    return {"system": instructions, "tools": [bash], "messages": conversation}

            response = request_response(assemble_context(conversation))
```

One sentence: its name, its body, where it is, and what day it is. Ask again:

```
> Who are you, and where are you working?
< I'm quark, an agent that works by running shell commands through bash. My working
  directory is /tmp/shop. Today's date is 2026-10-07.
```

No commands needed. It knew.

That's the balance context has to strike. **Too little,** and the agent wastes steps finding things out, or guesses. **Too much,** and every request costs more, and what matters is buried in what doesn't. The goal is the minimum it needs to act well, on whatever it's asked.

That's all five parts. `quark.py` is 50 lines, and with a model in it, it's an agent.

### The context, as the model sees it

For our own model (Part IV), the context is rendered through the chat template into one string. For the one-sentence instructions, the bash tool, and a first request, the string looks like this (the tool's parameters shortened):

```
<|im_start|>system
You are quark, an agent. You act through bash, in /tmp/shop. Today is 2026-10-07.

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{"type": "function", "function": {"name": "bash", "description": "Run a shell command", "parameters": {...}}}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call><|im_end|>
<|im_start|>user
The tests are failing. Find out why and fix it.<|im_end|>
<|im_start|>assistant
```

The paragraph about `<tools>` and `<tool_call>` is the template's own, added whenever tools are passed. This is the text our model will be trained on and prompted with, so the two must match exactly.

### A self model

As an agent grows more capable, its instructions grow into a picture of itself: a **self model**. The production harness of the next chapter gives quark instructions of about 9,400 tokens, following the map from Chapter 3. In outline:

```
# Self Model
  Identity   you are quark, a self in a world with other selves
  Mind       your context window: working memory, summarized when full
  Body       bash, in a container that sees only this folder; commands need approval
  Loop       observe → think → act → repeat

# Memory
  Semantic   .quark/memory/memory.md   facts, one per line; how to read and write them
  Procedural .quark/skills/*.md        one file per method that worked; an index, built live
  Episodic   .quark/episodes/*.jsonl   every message of every session; how to search them
  Across     recall ladder: semantic, then procedural, then episodic

# World Model      where you are, what day it is
# Other Selves     people and other agents; how they reach you and you them
# Body Operations  prefer one command per reply; escalate from pipes to scripts
# Mechanics        this harness's own code, with the system prompt redacted
```

Two design rules run through it. **Each memory has a format contract**: a fixed layout (`- <subject>: <fact>`) that makes it searchable with ordinary text tools, and the instructions show the exact commands to read and write it. And **it includes its own code**: the `mechanics()` function returns the harness's source with the system prompt itself cut out, so the agent can read how it works without the prompt containing itself.

Written from the agent's point of view, the self model tells the model what it is, so it never has to guess. It also costs: 9,400 tokens on every call. Chapter 14's performance section pays that bill.

### Too long to send

A conversation grows with every step, and the context window has a limit. When a request is too long to send, the harness has to make room. There are three strategies:

| Strategy | What it does | Keeps | Loses |
|---|---|---|---|
| **Sliding window** | Drops the oldest messages | The recent | The start, maybe the task itself |
| **Compaction** | Summarizes the oldest part | The gist | The details |
| **Retrieval** | Includes only what this moment needs | Focus | The rest, until it's fetched |

quark uses compaction, in Chapter 14: when the API reports the request is too long, a cheaper model summarizes the older turns, and the summary takes their place, with a note saying where the originals are kept on disk.

### Try it

quark works. In the last chapter's run it found the bug, fixed it, ran the tests, and committed. But look at how. It ran `sed -i` on the code and `git commit` without asking. Close the terminal and the conversation is gone. A command that never finishes would hang it forever, and nothing records what it did. You wouldn't leave it running on its own.
