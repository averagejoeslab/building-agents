from anthropic import Anthropic

# ── model interface ─────────────────────────────────────────────────────────
client = Anthropic()
MODEL = "claude-sonnet-5-5"
def call(**request): return client.messages.create(model=MODEL, **request)

output = call(max_tokens=16384, messages=[{"role": "user", "content": "What's in this directory?"}])
print(output.model_dump_json(indent=2))
