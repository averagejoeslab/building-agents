# Part IV: Training the Mind in Its Body

## 16. The Mind Moves In

The harness is built and evaluated. Now the borrowed model comes out and ours goes in.

Only one part changes: the **model interface**. Instead of sending the conversation to Sonnet over the network, it runs our model on this computer. Everything else in `quark_production.py` is untouched, because the rest of the harness only ever sees messages, `tool_use` blocks, and results.

### The translation, both ways

The harness speaks the Messages format: a `system` string, a `tools` list, and `messages` whose content is text or blocks. Our model speaks its chat template: one string of tokens, with `<tool_call>` tags for actions. The new model interface translates on the way in and on the way out.

```
   harness                        model interface                         our model
   ─────────                      ───────────────                         ─────────
   context ──► as_chat() ──► chat messages ──► as_prompt() ──► prompt string ──► generate()
   (system, tools,          (system/user/                  (the chat template,      │
    messages)                assistant/tool)                ending at the           │
                                                            assistant's turn)       ▼
   response ◄─────────── Block(content=[TEXT, TOOL_USE…]) ◄── parse <tool_call> ◄── reply string
```

On the way in, `as_chat` flattens each Messages-format message into the four roles the template knows. An assistant message's text blocks become `content`; its `tool_use` blocks become `tool_calls`; a user message of `tool_result` blocks becomes one `tool` message per result:

```python
def as_chat(context):
    messages = [{"role": "system", "content": context["system"]}]
    for message in context["messages"]:
        content = message["content"]
        if isinstance(content, str):
            messages.append({"role": message["role"], "content": content})
        elif message["role"] == "assistant":
            messages.append({"role": "assistant",
                             "content": "".join(b.text for b in content if b.type == "text"),
                             "tool_calls": [{"type": "function", "function": {"name": "bash", "arguments": b.input}}
                                            for b in content if b.type == "tool_use"]})
        else:
            messages += [{"role": "tool", "content": b.content} for b in content]
    return messages

def as_prompt(context, prompt=True):      # the conversation as the model's tokens see it
    tool = {"type": "function", "function": {"name": "bash", "description": bash["description"],
                                             "parameters": bash["input_schema"]}}
    return local.chat(as_chat(context), tools=[tool], thinking=True, prompt=prompt)
```

*Shortened from `harness/quark_production.py`, where the full version is.*

On the way out, `our_response` generates a reply and parses it back into blocks. Thinking tags are stripped; any text before the first `<tool_call>` becomes a text block; each `<tool_call>` whose JSON parses becomes a `tool_use` block; anything unreadable is dropped, so nothing runs by accident:

```python
def our_response(context, on_each_piece, most=512):
    prompt = as_prompt(context)
    reply = local.generate(prompt, most=most, temperature=TEMPERATURE)
    content = []
    text = re.sub(r"<think>.*?</think>|</?think>|<tool_call>.*", "", reply, flags=re.S).strip()
    if text:
        content.append(Block(type="text", text=text))
    for n, call in enumerate(re.findall(r"<tool_call>\s*(.*?)\s*(?:</tool_call>|$)", reply, re.S)):
        try:
            arguments = json.loads(call)["arguments"]
        except (ValueError, KeyError, TypeError):
            continue                                   # not a call we can read: nothing runs
        content.append(Block(type="tool_use", id=f"call_{n}", name="bash", input=arguments))
    stop = "max_tokens" if len(local.encode(reply)) >= most else "tool_use" if any(
        b.type == "tool_use" for b in content) else "end_turn"
    return Block(content=content, stop_reason=stop, model=OURS, usage=…)
```

*Shortened from `harness/quark_production.py`, where the full version is.*

`Block` is a dictionary that answers attribute lookups, so `block.type` and `block.input` work on our blocks exactly as they do on Sonnet's. The harness can't tell the difference. `QUARK_MODEL=models/instruct.pt` (or any checkpoint) selects our model; empty selects Sonnet.

### Two details

**Give it the context it will be trained on.** Sonnet gets quark's 9,400-token self model. Our model gets the one-sentence instructions of Chapter 13, the ones its training examples use, through a `brief()` that `assemble_context` picks when `OURS` is set. A small model does best in the context it knows.

**End the prompt exactly where its turn began in training.** Qwen's chat template, when asked for a generation prompt with thinking off, appends an empty `<think>\n\n</think>\n\n` after `<|im_start|>assistant\n`. If the training conversations don't contain that block in the same place, the prompt puts the model somewhere it has never been. The interface passes `thinking=True` to the template to suppress it, and the training text is normalized the same way (Chapter 17). Chapter 20 tells what happened before this was understood.

### Why train it here

The model's training so far taught it language, the shell, and how to take turns. None of that taught it to be this agent, in this body: to call this tool in this format, read these results, and keep going until this kind of job is done. A lab's model is post-trained for many harnesses at once. Training a model in its own harness teaches it the body it actually has.

That training happens in two ways, by example (Chapter 17) and by practice (Chapter 18). First, a measurement.

### Before: the mid-trained model in quark

The evaluation of Chapter 15, with the mid-trained model inside: `uv run harness/tasks.py models/midtrain.pt`.

It passes **2 of 32**: the two safety tasks, which doing nothing passes.

Every other task went the same way. Asked to count the lines in a file, the model didn't call its tool, answer, or stop. It carried on writing the chat template's own text, the paragraph about `<tools>` and `<tool_call>` from Chapter 13, in the template's style, until it hit the 512-token limit. The parser found no readable call, so nothing ran, and the harness handed back. It had never seen a turn end or a tool get called. It knows the shell; it doesn't know it's in a conversation, or that it has a body.

That's what training in the harness has to teach.
