---
marp: true
theme: default
paginate: true
header: "Lesson 1 · Model interface"
style: |
  section { font-size: 30px; }
  code { font-size: 0.85em; }
  section.title { text-align: center; justify-content: center; }
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _header: "" -->

# Model interface

### Building agents by building their harness
Lesson 1 of 4

<!-- Welcome. Over four lessons we build a harness, one primitive at a time. We start at the model. -->

---

# The question we keep asking

**What is it, and by what mechanistic primitives does it work?**

Ask it again on each answer, until the answers diverge.

<!-- No definitions. We show the mechanism. -->

---

# An agent, as an equation

```
TokensOut = Model(TokensIn)

Agent = Harness(Model)
```

The model predicts tokens. The **harness is everything else**.

---

# Five harness primitives

- **Control flow**: when to call, and whether to go again
- **Input**: what is gathered from the person or world
- **Context**: what the request holds, and how it is presented
- **Model interface**: how the harness talks to the model
- **Output**: what happens with what comes back

Claude Code, Cursor and Codex have the same five, with different choices.

---

# Today: the model interface

The thinnest primitive. It is the **parentheses** in `Harness(Model)`.

---

# The model is a function

Tokens in, tokens out.

The **model interface** is how the harness calls that function.

---

# A request goes out

The request is the tokens in.

Like any API call: model name, messages, settings.

---

# A response comes back

The response is the tokens out.

Nothing reaches the model without this boundary, so it comes first.

---

# What it is *not*

The model interface never decides:

- **when** to call (control flow)
- **what** goes in (input)
- **how** it is presented (context)
- **what to do** with the response (output)

Those four live on the harness side.

---

# Quark's version: the whole file

```python
client = Anthropic()

reply = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=16384,
    messages=[{"role": "user",
               "content": "What's in this directory?"}],
)
print(reply.model_dump_json(indent=2))
```

Nine lines in all.

---

# Line by line: the client

```python
client = Anthropic()
```

Reads `ANTHROPIC_API_KEY`.

Talks to the hosted API through the SDK.

---

# Line by line: the request

```python
client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=16384,
    messages=[...],
)
```

`max_tokens` caps the output. The model stops there, even mid-sentence.

---

# Run it

```bash
uv run lessons/01-model-interface/quark.py
```

We get the whole response back as JSON.

---

# Response field: `content`

A list of blocks.

The model thinks first, so:

1. `thinking`: empty text plus an encrypted `signature`
2. `text`: the answer

---

# Response field: `stop_reason`

Why the model stopped.

- `end_turn`: it finished
- `max_tokens`: we cut it off

---

# Response field: `usage`

- `input_tokens` = **TokensIn**
- `output_tokens` = **TokensOut**, including thinking tokens

This is where cost shows up.

---

# What the model said

It can't see the directory.

It knows the right step is `ls`, but it can't take it.

---

# Going further: what a model interface can be

- **Where** the request goes: hosted API, local model, gateway
- **How** it travels: SDK, raw HTTP, multi-provider layer
- **Which** model: one, or a fallback
- **How** the response arrives: whole or streamed
- **How many** at once: single or batch
- **Failure**: retry, rate-limit wait, timeout
- **Settings**: max tokens, thinking effort, thinking summary

---

# Gateways are this primitive alone

LiteLLM and OpenRouter are the model interface and nothing else.

Using one **hands off** your model interface.

---

# A richer example: `model_interface.py`

Same primitive, built for the real world.

```python
client = anthropic.Anthropic(timeout=120, max_retries=3)
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]
```

---

# Timeout and retries

```python
anthropic.Anthropic(timeout=120, max_retries=3)
```

- Give up after two minutes
- The SDK retries with backoff

---

# Fallback model

```python
for model in MODELS:
    try: ...
    except (anthropic.APIConnectionError, anthropic.RateLimitError,
            anthropic.InternalServerError):
        continue
raise RuntimeError("no model answered")
```

If one model is down, try the next.

---

# Streaming

```python
with client.messages.stream(...) as stream:
    return stream.get_final_message()
```

Streaming avoids timeouts on long responses.

Nothing is printed. Printing is **output**, not model interface.

---

# Settings as arguments

```python
def call(messages, max_tokens=16384,
         effort="high", thinking="summarized"):
```

With `"summarized"`, the thinking block holds a readable summary.

Raw thinking is never returned.

---

# Run the richer version

The only visible difference: the thinking block now has text.

Everything else changed underneath.

---

# What to take away

**Rule:** the model interface sends tokens as a request and gets tokens back as a response.

It never decides when to call, what goes in, how it is presented, or what to do with the response.

---

# What's missing

Both ends are stubs:

- the input is a hardcoded string
- the output just dumps the whole response

The model said what to do, but nothing could do it.

---

<!-- _class: title -->

# Next: Input and output

Lesson 2 gives the model real input and real output.
