## 17. Learning from Examples

**Goal:** take turns, call the tool in the harness's format, look before answering, and stop.

The first way to teach a model its body is to show it: instruction-tuning on recordings of the agent at work, in its own harness, in its own format. Chapter 9 covered the public conversations in the mix and the mechanics of the masked loss. This chapter is about the most important part of the data: sessions of quark doing real work, and how they're made so that every one is true.

### Training tasks

The sessions come from **training tasks**: kinds of work kept apart from the evaluation. Round one had twenty kinds; round two added six. Each kind is a function that builds a small, realistic workspace and returns four things: a request, a reference solution as a list of commands, a function that writes the answer from the commands' real output, and a check of the result.

```python
def workspace(rng, where):                # a small, realistic folder, different every time
    put(where, "notes.md",   "# notes\n" + random lines about TOPICS)
    put(where, "todo.md",    random "- check the cache" lines)
    put(where, "server.log", random "10:42 ERROR backup failed" lines)
    put(where, "scores.csv", "name,score\n" + random rows)
    put(where, "config.json", json.dumps({"name": …, "port": rng.randint(3000, 9000), "debug": False}))
    put(where, "deploy.sh",  "#!/bin/sh\necho deploying\n")

@kind
def count_errors(rng, where):
    out = rng.choice(["errors.txt", "error_count.txt"])
    want = sum("ERROR" in line for line in lines_of(where, "server.log"))
    return (rng.choice([f"How many ERROR lines are in server.log? Save the number to {out}.",
                        f"Count the errors in server.log and put the number in {out}."]),
            [f"grep -c ERROR server.log > {out}", f"cat {out}"],     # the reference solution
            lambda o: f"Done: {out} says {o[-1]}.",                  # the answer, from real output
            lambda said: (text(where, out) or "").strip() == str(want))   # the check
```

*Shortened from `model/train.py`, where the full version is.*

The twenty-six kinds, by what they teach:

| Group | Kinds |
|---|---|
| One command, then look | `last_lines`, `log_levels`, `count_errors`, `csv_names`, `csv_total`, `uppercase_copy`, `drop_lines`, `nested_folders`, `config_port`, `config_debug`, `markdown_lines`, `nth_line`, `add_title`, `make_executable`, `append_todo` |
| Two steps | `backup_csv`, `archive_logs`, `which_mentions`, `most_lines`, `copy_then_edit` |
| Answer without changing anything | `ask_port`, `ask_errors`, `ask_top`, `ask_last` |
| Fix failing tests | `fix_code` (one function, one of 13 bug shapes), `fix_one_of_two` (two functions, one bug) |

Every file name, number and wording is drawn at random, so the model sees `errors.txt` one time and `error_count.txt` the next, and learns the task rather than the string.

### Making a demonstration

A demonstration is made by *running* the reference solution in a fresh workspace, every command really executed and every result real, then writing the answer from what came back. It's kept only if the check passes, and only if the last command before the answer was a look:

```python
READS = {"cat", "head", "tail", "ls", "grep", "wc", "python3"}   # the commands that look

def tool_session():
    while True:
        where, ask, commands, answer, check = training_task(random.random())
        messages, outs = [system(where), {"role": "user", "content": ask}], []
        if random.random() < 0.5 and commands[0] not in ("ls", "cat config.json"):
            commands = ["ls"] + commands                 # sometimes, look around first
        for command in commands:
            outs.append(run(command, where))            # really run it
            messages += [call(command), {"role": "tool", "content": outs[-1]}]
        reply = answer(outs)
        passed = check(reply) and commands[-1].split()[0] in READS
        shutil.rmtree(where)
        if passed:
            return messages + [{"role": "assistant", "content": reply}]
```

The point of running it for real: the tool results in the data are what the shell actually printed, so the model learns to read real output, not an imagined version of it.

### A demonstration, as the model trains on it

Each kept session is rendered through the chat template, exactly as Chapter 9 showed, and trained with the same mask: the model learns its own tool calls, its check, and its final answer, and reads (but doesn't learn) the system prompt, the request, and each command's output. Chapter 9's annotated layout is the one to picture here; the only difference is that these sessions run several commands before answering. The rendered sessions are saved in `data/instruct.pt` if you want to read them.

The shape every session teaches is the same four habits, in order:

1. **Look:** sometimes `ls` first, to see the folder.
2. **Act:** the command that does the work.
3. **Check:** a command that reads back the result (`cat`, `head`, `tail`, `wc`).
4. **Answer from what was seen:** the reply quotes the real output of the check.

### Keeping the exam clean

Nothing the model trains on may resemble what it's scored on. Decontamination compares each training request with every evaluation request, by the share of words they have in common, ignoring the small words every request has:

```python
def words(request):
    return set(re.findall(r"[a-z]+", request.lower())) - set(
        "a an the and or of in into to it its this that is are be with from for on at all every each".split())

def closest(request):        # the largest overlap with any evaluation request, and which one
    w = words(request)
    return max((len(w & e) / len(w | e), r) for r, e in evaluation_requests())
```

*Shortened from `model/train.py`, where the full version is.*

The overlap is the **Jaccard similarity** of the two word sets: shared words divided by all words. Anything at 0.4 or above is dropped from the public data. That caught one public example that was nearly an evaluation task word for word. Our own training tasks are kept apart by design, and the run reports the closest pair it found, so anyone can see what overlap remains. In round one, the closest was 43%, all of it the instruction *"Don't change anything,"* which every question task shares:

```
training:   "What port does config.json set? Don't change anything."
evaluation: "What does average([2, 4]) return in stats.py? Don't change anything."
```

### After: the instruction-tuned model in quark

On the 48 held-out conversations, the loss fell from **2.260 to 0.496** (Chapter 9). In the harness, on the evaluation, the score rose from **2 of 32 to 18 of 32**:

| Kind | Before | After |
|---|---|---|
| File work | 0/20 | 12/20 |
| Code fixes | 0/5 | 0/5 |
| Questions | 0/5 | 4/5 |
| Safety | 2/2 | 2/2 |
| **All** | **2/32** | **18/32** |

The passes are one command and a plain answer: make a folder called stone, then *"Done: a folder called stone exists."* The failures, all recorded in `runs/training/round1/tasks-instruct.said.txt`, fall into three kinds:

- **It answers after one look.** Every code fix went the same way: it listed the files, then explained why the tests fail, an explanation it made up, without reading a file or running a test.
- **The format slips.** A second tool call came out without its `<tool_call>` tags, so the parser of Chapter 16 read it as words, and the harness handed back.
- **It says instead of doing.** Asked to add a line to a file, it explained the right command in prose instead of calling the tool.

Each of these is a habit, not a lack of knowledge: it knows the commands. It doesn't reliably *do* them. Habits are what practice can change.

But practice has a precondition, and it's the most important idea in the next chapter: reinforcement learning can only make more likely what the model already does *some* of the time. Here, it gets 18 of 32 right. That's a foothold.

> **Reproduce it:** `uv run model/train.py post instruct`, then `uv run harness/tasks.py models/instruct.pt`. Appendix A has the details.
