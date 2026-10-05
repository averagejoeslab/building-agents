import anthropic

client = anthropic.Anthropic(timeout=120, max_retries=3)
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]

def call(messages, max_tokens=4096, effort="high", thinking="summarized"):
    for model in MODELS:
        try:
            with client.messages.stream(model=model, max_tokens=max_tokens, output_config={"effort": effort}, thinking={"type": "adaptive", "display": thinking}, messages=messages) as stream:
                return stream.get_final_message()
        except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError):
            continue
    raise RuntimeError("no model answered")

reply = call([{"role": "user", "content": "What's in this directory?"}])
print(reply.model_dump_json(indent=2))
