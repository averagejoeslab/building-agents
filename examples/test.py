import subprocess
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()


def bash(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return "error: command timed out after 30s"
    return (result.stdout + result.stderr).strip() or f"(exit {result.returncode})"


tools = [
    {
        "name": "bash",
        "description": "Run a shell command",
        "input_schema": {
            "type": "object",
            "properties": {"cmd": {"type": "string"}},
            "required": ["cmd"],
        },
    }
]


messages = [{"role": "user", "content": "Show me the contents of pyproject.toml and tell me what tool calls you made and how did they look"}]

while True:
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system="You are a helpful coding assistant. Use the bash tool CAREFULLY to do work ONLY as needed",
        messages=messages,
        tools=tools,
    )
    messages.append({"role": "assistant", "content": response.content})

    tool_calls = [b for b in response.content if b.type == "tool_use"]
    if not tool_calls:
        break

    results = [
        {"type": "tool_result", "tool_use_id": c.id, "content": bash(**c.input)}
        for c in tool_calls
    ]
    messages.append({"role": "user", "content": results})

for block in response.content:
    if block.type == "text":
        print(block.text)
