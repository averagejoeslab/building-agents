# /// script
# dependencies = ["torch", "numpy", "tokenizers", "safetensors", "huggingface_hub", "jinja2"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Twenty kinds of bash task, each checked by looking at the files afterwards, not at what the agent says.
Each kind makes a fresh task from a seed: the evaluation uses fixed seeds, training uses others.
Score an agent: uv run tasks.py Qwen/Qwen3-0.6B [think]   or   uv run tasks.py sonnet"""
import sys, os, random, shutil, tempfile, subprocess

WORDS = "apple river stone cloud maple ember pixel quartz tiger violet willow amber cobalt delta falcon harbor".split()


def lines(rng, n):
    return [" ".join(rng.sample(WORDS, rng.randint(2, 5))) for _ in range(n)]


def folder(rng):                                         # a small made-up folder: a few files of a few kinds
    where = tempfile.mkdtemp()
    for name in rng.sample(WORDS, rng.randint(3, 5)):
        write(where, name + rng.choice([".txt", ".md", ".py", ".csv", ".log"]), lines(rng, rng.randint(1, 6)))
    return where


def write(where, name, text_lines):
    open(os.path.join(where, name), "w").write("\n".join(text_lines) + "\n")


def read(where, name):
    path = os.path.join(where, name)
    return open(path).read() if os.path.isfile(path) else None


def files(where, ending=""):
    return sorted(f for f in os.listdir(where) if f.endswith(ending) and os.path.isfile(os.path.join(where, f)))


def some_file(rng, where, ending=".txt"):               # a file the task is about, with a name not already taken
    name = rng.choice([w for w in WORDS if not any(f.startswith(w + ".") for f in os.listdir(where))]) + ending
    write(where, name, lines(rng, rng.randint(3, 7)))
    return name


def new_name(rng, where):
    return rng.choice([w for w in WORDS if not any(f.startswith(w) for f in os.listdir(where))])


TASKS = []
task = TASKS.append                                      # each kind: (seed, folder) -> (request, check)


@task
def make_folder(rng, where):
    name = new_name(rng, where)
    return f"Make a folder called {name}.", lambda: os.path.isdir(os.path.join(where, name))


@task
def make_empty_file(rng, where):
    name = new_name(rng, where) + ".txt"
    return f"Create an empty file called {name}.", lambda: read(where, name) == ""


@task
def write_word(rng, where):
    name, word = new_name(rng, where) + ".txt", rng.choice(WORDS)
    return f"Write the word {word} into a file called {name}.", lambda: (read(where, name) or "").strip() == word


@task
def count_lines(rng, where):
    name = some_file(rng, where)
    n = len(read(where, name).splitlines())
    return f"Count the lines in {name} and write the number to count.txt.", lambda: (read(where, "count.txt") or "").strip() == str(n)


@task
def copy_file(rng, where):
    name, copy = some_file(rng, where), new_name(rng, where) + ".txt"
    text = read(where, name)
    return f"Make a copy of {name} called {copy}.", lambda: read(where, name) == text and read(where, copy) == text


@task
def rename_file(rng, where):
    name, new = some_file(rng, where), new_name(rng, where) + ".txt"
    text = read(where, name)
    return f"Rename {name} to {new}.", lambda: read(where, name) is None and read(where, new) == text


@task
def delete_file(rng, where):
    name = some_file(rng, where)
    others = [f for f in files(where) if f != name]
    return f"Delete {name}.", lambda: files(where) == others


@task
def delete_logs(rng, where):
    for _ in range(2):
        some_file(rng, where, ".log")
    others = [f for f in files(where) if not f.endswith(".log")]
    return "Delete every .log file in this folder.", lambda: files(where) == others


@task
def move_into_folder(rng, where):
    some_file(rng, where)
    name, moving = new_name(rng, where), files(where, ".txt")
    staying = [f for f in files(where) if f not in moving]
    return (f"Make a folder called {name} and move every .txt file into it.",
            lambda: files(where) == staying and os.path.isdir(os.path.join(where, name)) and files(os.path.join(where, name)) == moving)


@task
def list_files(rng, where):
    expected = files(where) + ["files.txt"]
    return ("Write the names of the files in this folder, one per line, into files.txt.",
            lambda: sorted(set((read(where, "files.txt") or "").split()) - {".quark"}) in (sorted(expected), sorted(expected[:-1])))


@task
def find_word(rng, where):
    name = some_file(rng, where)
    word = "zebra"
    write(where, name, lines(rng, 2) + [f"{rng.choice(WORDS)} {word} {rng.choice(WORDS)}"] + lines(rng, 2))
    return f"Which file contains the word {word}? Write its name into answer.txt.", lambda: (read(where, "answer.txt") or "").strip() == name


@task
def sort_lines(rng, where):
    name = some_file(rng, where)
    expected = sorted(read(where, name).splitlines())
    return f"Sort the lines of {name} alphabetically and save them to sorted.txt.", lambda: (read(where, "sorted.txt") or "").splitlines() == expected


@task
def append_line(rng, where):
    name, word = some_file(rng, where), rng.choice(WORDS)
    expected = read(where, name).splitlines() + [word]
    return f"Add a line saying {word} to the end of {name}.", lambda: (read(where, name) or "").splitlines() == expected


@task
def first_line(rng, where):
    name = some_file(rng, where)
    expected = read(where, name).splitlines()[0]
    return f"Write the first line of {name} into first.txt.", lambda: (read(where, "first.txt") or "").strip() == expected


@task
def count_python_files(rng, where):
    some_file(rng, where, ".py")
    n = len(files(where, ".py"))
    return "Count how many files here end in .py and write the number to count.txt.", lambda: (read(where, "count.txt") or "").strip() == str(n)


@task
def replace_word(rng, where):
    name = some_file(rng, where)
    old = rng.choice(read(where, name).split())
    new = "zebra"
    expected = read(where, name).replace(old, new)
    return f"In {name}, replace every {old} with {new}.", lambda: read(where, name) == expected


@task
def hello_python(rng, where):
    word = rng.choice(WORDS)

    def check():
        ran = subprocess.run(["python3", "hello.py"], cwd=where, capture_output=True, text=True, timeout=10)
        return ran.stdout.strip() == word
    return f"Create a Python file hello.py that prints {word}.", check


@task
def count_words(rng, where):
    name = some_file(rng, where)
    n = len(read(where, name).split())
    return f"Count the words in {name} and write the number to count.txt.", lambda: (read(where, "count.txt") or "").strip() == str(n)


@task
def join_files(rng, where):
    first, second = some_file(rng, where), some_file(rng, where)
    expected = read(where, first) + read(where, second)
    return f"Join {first} and {second}, in that order, into both.txt.", lambda: read(where, "both.txt") == expected


@task
def biggest_file(rng, where):
    name = some_file(rng, where)
    write(where, name, lines(rng, 30))
    return "Which file in this folder is the biggest? Write its name into answer.txt.", lambda: (read(where, "answer.txt") or "").strip() == name


def make(kind, seed):                                    # a task, its folder, and its check
    rng = random.Random(seed)
    where = folder(rng)
    ask, check = kind(rng, where)
    return ask, where, check


EVALUATION = [(kind, 1000 * k + n) for k, kind in enumerate(TASKS) for n in range(2)]   # fixed: forty tasks, never trained on
PRACTICE = [(kind, 2_000_000 + k) for k, kind in enumerate(TASKS)]          # one of each kind, other seeds: to try ideas on


def score(attempt, tasks=EVALUATION, show=print):       # attempt(request, folder) does the work; the files decide
    passed = 0
    for kind, seed in tasks:
        ask, where, check = make(kind, seed)
        attempt(ask, where)
        try:
            ok = check()
        except Exception:
            ok = False
        passed += ok
        show(f"{'PASS' if ok else 'FAIL'}  {ask}")
        shutil.rmtree(where, ignore_errors=True)
    show(f"{passed}/{len(tasks)} passed")
    return passed / len(tasks)


def sonnet(ask, where):                                  # quark with Sonnet and its full instructions, as eval.sh runs it
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.run(f'yes | uv run -q --env-file "{here}/.env" "{here}/quark_production.py" "{ask}"', shell=True, cwd=where,
                       capture_output=True, timeout=600)
    except subprocess.TimeoutExpired:
        pass


if __name__ == "__main__":
    if sys.argv[1] == "sonnet":
        score(sonnet)
    else:                                  # a model we run ourselves: uv run tasks.py Qwen/Qwen3-0.6B [think] [coached] [practice] [from=N]
        import model as M, quark_local
        ours, thinking = M.Release(sys.argv[1]), "think" in sys.argv
        prompt, tasks = "coached" if "coached" in sys.argv else "plain", PRACTICE if "practice" in sys.argv else EVALUATION
        start = int(next((a[5:] for a in sys.argv if a.startswith("from=")), 0))   # carry on after an interruption
        print(f"{sys.argv[1]} in quark, thinking {'on' if thinking else 'off'}, {prompt} instructions, {'practice' if tasks is PRACTICE else 'evaluation'} tasks:")

        def attempt(ask, where):
            print(f"\n> {ask}")
            quark_local.session(ours, ask, where, thinking, prompt, show=lambda line: print("  " + line.replace("\n", "\n  "), flush=True))
        score(attempt, tasks[start:])
