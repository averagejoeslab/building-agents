# /// script
# dependencies = ["torch", "numpy", "tokenizers", "safetensors", "huggingface_hub", "transformers", "jinja2"]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Qwen3-0.6B as Qwen released it, untrained by us, in quark: quark.py's instructions and bash tool, a different model interface.
The interface speaks Qwen's own format: its chat template renders the conversation and the tool, and the model calls a tool
by writing <tool_call>{"name": ..., "arguments": ...}</tool_call>. Run from the repo: uv run --script runs/qwen_in_quark.py [think]"""
import sys, re, json, torch, torch.nn.functional as F
sys.path.insert(0, ".")
import model as M, quark_local as Q, tasks as T
from transformers import AutoTokenizer

NAME = "Qwen/Qwen3-0.6B"
qwen = M.load_real(NAME)
template = AutoTokenizer.from_pretrained(NAME)            # its chat template and its tokenizer: the exact format Qwen was trained on
encode = lambda text: template.encode(text, add_special_tokens=False)    # not Base's: Base reads <think> and <tool_response> as plain text
decode = template.decode
bash = {"type": "function", "function": {"name": "bash", "description": "Run a shell command",       # quark.py's tool
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
INSTRUCTIONS = "You are quark, an agent. You act through bash, in /work. Today is 2026-10-08."          # quark.py's instructions
STOP = {encode("<|im_end|>")[0], encode("<|endoftext|>")[0]}      # both, as its generation_config.json lists
THINK = "think" in sys.argv                              # Qwen3 can think first, in <think>…</think>, before it answers
TEMPERATURE, TOP_P, MOST = (0.6, 0.95, 1500) if THINK else (0.7, 0.8, 400)   # Qwen's advice for each mode
problems = []                                            # replies the interface could not turn into a tool call


def assemble_context(conversation):
    return template.apply_chat_template([{"role": "system", "content": INSTRUCTIONS}] + conversation, tools=[bash],
                                        add_generation_prompt=True, enable_thinking=THINK, tokenize=False)


@torch.no_grad()
def request_response(context, most=MOST):
    ids, caches, out = torch.tensor([encode(context)]), [{} for _ in qwen.layers], []
    scores = qwen(ids, caches)[0, -1]
    for _ in range(most):
        top = torch.topk(scores / TEMPERATURE, 20)
        probs = F.softmax(top.values, dim=-1)
        keep = probs.cumsum(0) - probs < TOP_P
        next_id = top.indices[keep][torch.multinomial(probs[keep] / probs[keep].sum(), 1)]
        if next_id.item() in STOP:
            break
        out.append(next_id.item())
        scores = qwen(next_id.view(1, 1), caches, start=ids.shape[1] + len(out) - 1)[0, -1]
    return decode(out)


def handle_output(response, where):                      # the reply as text, plus each <tool_call> it made, run
    calls, results = [], []
    for raw in re.findall(r"<tool_call>(.*?)</tool_call>", response, re.S):
        try:
            call = json.loads(raw)
            command = call["arguments"]["command"]
        except (ValueError, KeyError, TypeError):
            problems.append(raw)
            results.append({"role": "tool", "content": "error: the tool call was not valid JSON with a command"})
            continue
        calls.append({"type": "function", "function": {"name": "bash", "arguments": {"command": command}}})
        results.append({"role": "tool", "content": Q.run(command, where)})
    if "<tool_call>" in response and not calls and not results:
        problems.append(response)
    thought = "".join(re.findall(r"<think>(.*?)</think>", response, re.S)).strip()
    text = re.sub(r"<tool_call>.*?</tool_call>|<think>.*?</think>", "", response, flags=re.S).strip()
    return {"role": "assistant", "content": text, "tool_calls": calls, "thought": thought}, results


transcripts = []


def session(ask, where, turns=8):                        # quark's control flow: go again while tools ran
    conversation = [{"role": "user", "content": ask}]
    for _ in range(turns):
        reply, results = handle_output(request_response(assemble_context(conversation)), where)
        conversation += [reply] + results
        if not results:
            break
    transcripts.append(conversation)


torch.manual_seed(0)
print(f"{NAME}, untrained by us, in quark, thinking {'on' if THINK else 'off'}:")
T.score(session)
print(f"tool calls the interface could not read: {len(problems)}", *problems[:3], sep="\n  ")
for conversation in transcripts[:6:2] + transcripts[-4::2]:
    print("\n" + "─" * 70)
    for m in conversation:
        shown = m["content"] + "".join(f"\n$ {c['function']['arguments']['command']}" for c in m.get("tool_calls", []))
        if m.get("thought"):
            print(f"[thinking] {m['thought'][:600]}")
        print(f"[{m['role']}] {shown.strip()[:400]}")
