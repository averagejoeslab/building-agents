## 12. Closing the Loop

**Control flow** decides what happens next. Its rule:

- If the model asked to run something, run it, send the result back, and let the model go again.
- If it didn't, it's done with this request. Hand back to the person for their next message.

That makes two loops. The **inner loop** runs while the model is working: act, see the result, decide, act again. The **outer loop** runs between the agent and the person: a request, the work, an answer, the next request. In `4_control_flow.py`:

```python
def control_flow():
    conversation = []
    while True:                                                   # outer: the person's turn
        conversation.append({"role": "user", "content": capture_input()})
        while True:                                               # inner: the agent's turn
            response = request_response({"tools": [bash], "messages": conversation})
            conversation.append({"role": "assistant", "content": response.content})
            tool_results = handle_output(response)
            if not tool_results:
                break                                             # done: hand back to the person
            conversation.append({"role": "user", "content": tool_results})   # a tool ran: go again
```

Three things about the conversation list:

- **It's the whole memory.** Every request, every reply, every tool call and its result, in order. It's sent in full on every call, so the model sees everything that has happened.
- **Tool results are `user` messages.** In the Messages format, there are only two roles. The model's tool calls live in `assistant` messages; what came back lives in `user` messages, as `tool_result` blocks. The role says who is speaking: the world, not the agent.
- **The model's own replies go back to it.** `response.content` is appended as-is, tool calls included. Next call, the model reads its own earlier reasoning and commands as part of the context.

```
conversation:
  user      "The tests are failing. Find out why and fix it."
  assistant [TEXT "Let me start by..."] [TOOL_USE bash "pwd; ls -la; ..."]
  user      [TOOL_RESULT "/tmp/shop\nprices.py\ntest_prices.py..."]
  assistant [TOOL_USE bash "cat prices.py test_prices.py; python -m pytest ..."]
  user      [TOOL_RESULT "...AssertionError: 15 != 22.5..."]
  assistant [TEXT "The docstring says..."] [TOOL_USE bash "sed -i ... && python -m unittest"]
  user      [TOOL_RESULT "...OK"]
  assistant [TEXT "The tests pass now. The bug was in prices.py, not in the tests."]
  ── no tool ran: hand back ──
  user      "Commit the fix."
  …
```

### The transcript

Now give it the job:

```
> The tests are failing. Find out why and fix it.
< Let me start by looking at the project and running the tests.
$ pwd; ls -la; git status 2>/dev/null | head
$ cat prices.py test_prices.py; python -m pytest -q 2>&1 | tail -30
$ python -m unittest -v 2>&1 | tail -20
< The docstring says the discount is a percentage, but the code subtracts it as a flat
  amount. So 25 − 10 = 15 instead of 25 × 0.9 = 22.5. I'll fix the code to match the
  documented behavior.
$ sed -i 's|return round(subtotal - discount, 2)|return round(subtotal * (1 - discount / 100), 2)|' prices.py && cat prices.py && python -m unittest 2>&1 | tail -5
< The tests pass now. The bug was in `prices.py`, not in the tests.

> Commit the fix.
$ git add prices.py && git commit -q -m "Fix total() to apply discount as a percentage ..." && git log --oneline -3
< I committed the fix as `d6beb65`, "Fix total() to apply discount as a percentage". Only `prices.py` is in the commit.
```

What the loop did. First call: the model emitted a text block and a tool call; the harness showed the text, ran the command, and sent the listing back. Second call: seeing the files, the model asked to read them and run the tests, in one command. (It tried `pytest`, which wasn't installed, then `unittest`, which was. The error went back as a result, like any other.) Third call: with the test output in context, it reasoned out the bug and fixed it, in one command that also re-ran the tests. Fourth call: the tests passed, so it wrote an answer with no tool call, and the inner loop broke. Then *"Commit the fix"* needed no explanation, because the whole conversation went back with it.

This is an agent: it perceived, decided, acted, and went again until the job was done, then handed back.

### What it doesn't know

Start it fresh, and ask the simplest question:

```
> Who are you, and where are you working?
< I'll check the environment first so I can answer accurately.
$ echo "user: $(whoami)"; echo "host: $(hostname)"; echo "cwd: $(pwd)"; uname -a; ls -la | head -20
< I'm an AI assistant. I can run shell commands, and I use that to read files, run code
  and make changes in the environment I'm given.
```

It had to go looking for where it was. It doesn't know its own name, what its body is, where it's working, or what day it is. Each of those costs a step to find out, or a guess. The last part fixes that.
