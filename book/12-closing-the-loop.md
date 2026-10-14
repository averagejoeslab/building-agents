## 12. Closing the Loop

**Control flow** decides what happens next. Its rule is simple:

- If the model asked to run something, run it, send the result back, and let the model go again.
- If it didn't, it's done with this request. Hand back to the person for their next message.

That makes two loops. The **inner loop** runs while the model is working: act, see the result, decide, act again. The **outer loop** runs between the agent and the person: a request, the work, an answer, the next request.

Now give it the job:

> \> The tests are failing. Find out why and fix it.
> < Let me start by looking at the project and running the tests.
> $ pwd; ls -la; git status 2>/dev/null | head
> $ cat prices.py test_prices.py; python -m pytest -q 2>&1 | tail -30
> $ python -m unittest -v 2>&1 | tail -20
> < The docstring says the discount is a percentage, but the code subtracts it as a flat amount. So 25 − 10 = 15 instead of 25 × 0.9 = 22.5. I'll fix the code to match the documented behavior.
> $ sed -i 's|return round(subtotal - discount, 2)|return round(subtotal * (1 - discount / 100), 2)|' prices.py && cat prices.py && python -m unittest 2>&1 | tail -5
> < The tests pass now. The bug was in `prices.py`, not in the tests.
>
> \> Commit the fix.
> $ git add prices.py && git commit -q -m "Fix total() to apply discount as a percentage …"
> < I committed the fix as `d6beb65`, "Fix total() to apply discount as a percentage". Only `prices.py` is in the commit.

It looked at the project. It read the code and the tests. It ran the tests and read the failure. It found the cause: the discount was being taken off as ten dollars, not ten percent. It fixed the line, ran the tests again to be sure, and reported. Then, asked to commit, it did, without needing the job explained again, because the whole conversation goes back to the model every time.

**This is an agent.** It perceives, decides, acts, and goes again, as many times as the job takes, then hands back.

### What it doesn't know

Start it fresh, and ask the simplest question:

> \> Who are you, and where are you working?
> < I'll check the environment first so I can answer accurately.
> $ echo "user: $(whoami)"; echo "host: $(hostname)"; echo "cwd: $(pwd)"; uname -a; ls -la | head -20
> < I'm an AI assistant. I can run shell commands, and I use that to read files, run code and make changes in the environment I'm given.

It had to go looking for where it was. It doesn't know its own name, what its body is, where it's working, or what day it is. Every one of those is a step spent finding out, or worse, a guess. The last part fixes that.
