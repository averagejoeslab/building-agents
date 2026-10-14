# Part III: Building the Body

## 10. What a Harness Is

Our model can hold a conversation. Ask it to fix the failing tests, and it will tell you, at best, what it would do. It can't open a file. It can't run the tests. It can't remember yesterday. It doesn't know where it is or what day it is. Everything it lacks, the harness provides.

The harness is everything around the model. It turns the model's tokens into actions, and what happened back into tokens. Its five parts were introduced in Chapter 3; here they are as the loop they make, with control flow holding the other four:

```
┌──────────────────────── control flow ─────────────────────────┐
│                                                                │
│  input ─► context ─► model interface ─► output ─┬─► person     │
│    ▲                    (the model)              │             │
│    └────────────────── a tool's result ──────────┘             │
└────────────────────────────────────────────────────────────────┘
```

### The harness in pseudocode

Before any Python, here is the whole harness in a language-neutral form. Everything in this Part is an implementation of these five procedures; everything in Chapter 14 is a refinement of them.

```
-- INPUT: what comes in
procedure CAPTURE_INPUT():
    return the person's next message, as text

-- CONTEXT: what the model is shown
procedure ASSEMBLE_CONTEXT(conversation):
    instructions ← who the agent is, where it is, what day it is
    tools        ← [ {name, description, parameters} for each tool ]
    return { system: instructions, tools: tools, messages: conversation }

-- MODEL INTERFACE: reach the model
procedure REQUEST_RESPONSE(context):
    send context to the model, in the format it expects
    return its response: a list of blocks, each TEXT(words) or TOOL_USE(id, name, arguments)

-- OUTPUT: act on the response
procedure HANDLE_OUTPUT(response):
    results ← []
    for block in response.blocks:
        if block is TEXT:      show block.words to the person
        if block is TOOL_USE:  result ← run the tool with block.arguments
                               results.append(TOOL_RESULT(block.id, result))
    return results

-- CONTROL FLOW: the loop
procedure CONTROL_FLOW():
    conversation ← []
    loop:                                            -- outer: one request at a time
        conversation.append(USER(CAPTURE_INPUT()))
        loop:                                        -- inner: one request, carried through
            response ← REQUEST_RESPONSE(ASSEMBLE_CONTEXT(conversation))
            conversation.append(ASSISTANT(response.blocks))
            results  ← HANDLE_OUTPUT(response)
            if results is empty: break               -- nothing ran: hand back
            conversation.append(USER(results))       -- a tool ran: go again
```

Two things to notice. The conversation is a plain list of messages, each with a role (`user` or `assistant`) and content (text, or blocks). It's the agent's entire working memory, and it's rebuilt into a context on every call. And the model only ever *asks* to act, by emitting a `TOOL_USE` block; the harness decides whether and how to carry it out. That split is where every safety measure in Chapter 14 will go.

### Building around a borrowed mind

We'll build the harness one part at a time, and watch what each part adds. To see each part's effect clearly, the mind inside needs to be capable. Ours, at 600 million parameters, makes enough mistakes of its own that it would hide what the harness is doing. So, as with pre-training, we borrow: we build the body around **Claude Sonnet**, a model built at scale, reached over the internet through Anthropic's API. Once the body is built and proven, our own model moves in (Part IV), and the evaluation will show exactly how far it has to go.

This works because only one part, the model interface, knows which model is inside. Everything else deals in plain things: messages, tool-use blocks, and results. Swapping minds means changing one procedure. Chapter 16 does exactly that.

### Building outward

We build the parts in the order information flows, outward from the model: first reach it, then let someone ask it something, then let it act, then let it go again, and finally tell it what it is. Each step is a file in `harness/`, the previous file plus one part:

| Step | File | Adds |
|---|---|---|
| 1 | `1_model_interface.py` | `request_response` |
| 2 | `2_input.py` | `capture_input` |
| 3 | `3_output.py` | the `bash` tool, `handle_output` |
| 4 | `4_control_flow.py` | `control_flow` |
| 5 | `quark.py` | `assemble_context` |

The agent is called **quark**. A quark is one of the smallest particles there is, and quark is meant to be the smallest agent: the five parts and nothing more, 50 lines.

### The job

Every version gets the same job. A tiny project, `harness/shop/`, has two files:

```python
# prices.py
def total(items, discount=0):
    """Add up (price, quantity) pairs, then take off a percentage discount."""
    subtotal = sum(price * quantity for price, quantity in items)
    return round(subtotal - discount, 2)          # the bug: a flat amount, not a percentage
```

```python
# test_prices.py
class TestTotal(unittest.TestCase):
    def test_no_discount(self):
        self.assertEqual(total([(10, 2), (5, 1)]), 25)
    def test_ten_percent_off(self):
        self.assertEqual(total([(10, 2), (5, 1)], discount=10), 22.5)   # fails: gets 15
```

The request is always: *"The tests are failing. Find out why and fix it."* The job gets its own folder and git repository, so the agent can commit:

```bash
cp -r harness/shop /tmp/shop && git -C /tmp/shop init -q && git -C /tmp/shop add -A
git -C /tmp/shop commit -qm "Add prices"
```

Each step runs from that folder: `cd /tmp/shop && uv run --env-file <repo>/.env <repo>/harness/1_model_interface.py`. In the transcripts that follow, `>` is what the person typed, `<` is what quark said, and `$` is a command it ran.
