# Aider

**Source:** https://github.com/Aider-AI/aider · **Version:** commit 5dc9490bb35f9729ef2c95d00a19ccd30c26339c (2026-05-22) · **Language:** Python
**Path conventions:** `a/` = `aider/`; `c/` = `aider/coders/`; `b/` = `benchmark/`; `t/` = `tests/basic/`. All paths relative to the repo root.
**What it is:** Aider is a terminal pair-programming tool by Paul Gauthier (Aider-AI) that edits files in a local git repository and commits each change. The model is reached through LiteLLM (`litellm.completion`) over HTTPS with streaming. There is no native tool calling on the main path: the model writes edits in a text "edit format" (SEARCH/REPLACE blocks, unified diffs, whole files) that the harness parses and applies, and a bounded "reflection" loop feeds parse, lint, and test failures back as the next user message.

## Control flow
- **Outer REPL loop (`Coder.run`):** `while True` reads a line, calls `run_one`, and returns on EOF; `main` wraps it in a loop that catches `SwitchCoder` and rebuilds the coder when the user changes mode or model. `c/base_coder.py:L876–L892`; `a/main.py:L1159–L1178`
- **Reflection loop and stop rule (`run_one`):** `while message:` sends one request; the loop goes again only when `reflected_message` was set, and stops with a warning once `num_reflections >= max_reflections` (class default 3). `c/base_coder.py:L924–L944`, `L101`
- **Go-again triggers:** after a reply, `send_message` sets `reflected_message` on newly mentioned files, on an edit-format `ValueError` from `apply_updates`, on lint errors (after `confirm_ask`), and on test errors (after `confirm_ask`), each returning early so `run_one` re-sends. `c/base_coder.py:L1561–L1566`, `L1585–L1623`, `L2296–L2336`
- **Approval gates the harness consumes:** `confirm_ask` gates adding mentioned files, creating or editing files not yet in chat, running model-suggested shell commands (explicit yes required), adding command output, and attempting lint/test fixes; "don't ask again" and group "all/skip" answers are remembered per question. `a/io.py:L807–L860`; `c/base_coder.py:L2191–L2242`, `L2450–L2485`
- **Architect delegation (depth 1):** `ArchitectCoder.reply_completed` optionally asks "Edit the files?", builds a second `Coder` on `editor_model` with the editor edit format and no repo map, runs the architect's reply as that coder's message, then folds cost and commit hashes back into the parent. `c/architect_coder.py:L11–L48`; `a/models.py:L625–L645`
- **Model routing keyed to the work:** the `weak_model` writes commit messages and history summaries and the `editor_model` performs the architect's edit step; both come from model settings, not from failures. `a/models.py:L603–L623`; `a/repo.py:L342–L364`; `a/history.py:L7–L13`

## Input
- **Terminal input:** `get_input` shows files in chat and the mode in a prompt_toolkit prompt; `preproc_user_input` dispatches `/commands`, scans the text for file mentions, and offers to scrape URLs into the message. `c/base_coder.py:L898–L922`, `L964–L984`; `a/io.py:L523–L545`
- **Scripted input:** `--message` and `--message-file` call `coder.run(with_message=...)`, which sends one message and returns the reply text. `a/main.py:L1126–L1140`; `c/base_coder.py:L876–L881`
- **File-watcher input ("AI comments"):** `FileWatcher.process_changes` turns `AI!` or `AI?` comments found in changed files into a request, adding the files to chat and including tree-sitter context around each comment. `a/watch.py:L181–L283`
- **Results re-enter as text:** approved shell-command output, `/run` and `/test` output, lint and test errors, and the edit-format failure report are either appended as `user`/`assistant` message pairs or become the next `reflected_message`. `c/base_coder.py:L1609–L1623`; `a/commands.py:L1013–L1060`; `c/editblock_coder.py:L79–L124`

## Context
- **System prompt and chunk order:** `fmt_system_prompt` fills the edit-format prompt with fence choice, platform and shell info, reply language, and lazy/overeager reminders; `format_chat_chunks` assembles ordered chunks: system, examples, read-only files, repo map, summarized history, chat files, current messages, and a reminder placed as system or appended to the last user message if it fits. `c/base_coder.py:L1174–L1224`, `L1226–L1331`; `c/chat_chunks.py:L16–L26`
- **Repo map:** `RepoMap` extracts definitions and references with tree-sitter (cached by mtime in a `diskcache` SQLite directory), ranks files with NetworkX PageRank personalized toward chat files and mentioned identifiers, and binary-searches the tag count so the rendered tree fits `map_tokens` (default 1024, times 8 when no files are in chat). `a/repomap.py:L103–L168`, `L217–L265`, `L470–L529`, `L629–L709`; `c/base_coder.py:L709–L748`
- **History compaction:** `ChatSummary.summarize_real` keeps a tail under half the budget, summarizes the head with the weak model, and recurses to depth 3; `summarize_start` runs it in a background thread whenever `done_messages` exceeds `max_chat_history_tokens`, and `format_chat_chunks` joins the thread before use. `a/history.py:L33–L130`; `c/base_coder.py:L1002–L1046`
- **Window check:** `check_tokens` compares the estimated prompt to `max_input_tokens` and asks before sending; a `ContextWindowExceededError` sets `exhausted` and prints a report instead of retrying. `c/base_coder.py:L1396–L1417`, `L1536–L1546`
- **Prompt caching:** with `--cache-prompts`, `add_cache_control_headers` marks the system/examples, repo-map, and chat-files chunks `cache_control: ephemeral`, and `warm_cache` re-sends the cacheable prefix with `max_tokens=1` every ~5 minutes to keep it warm. `c/chat_chunks.py:L28–L56`; `c/base_coder.py:L1333–L1394`

## Model interface
- **Client:** `Model.send_completion` builds the request (temperature, an optional single forced `tools` function, `extra_params`, ollama `num_ctx`, a 600 s timeout) and calls `litellm.completion`; litellm is imported lazily with `drop_params = True`. `a/models.py:L985–L1037`, `L28`; `a/llm.py:L21–L45`
- **Streaming:** `show_send_output_stream` iterates chunks, accumulates content, reasoning, and function-call deltas, and raises `FinishReasonLength` when `finish_reason == "length"`. `c/base_coder.py:L1900–L1975`
- **Retries and prefill continuation:** `send_message` loops with exponential backoff from 0.125 s until `RETRY_TIMEOUT = 60` for litellm exceptions whose table entry says `retry=True`; on `FinishReasonLength` it appends the partial reply as an assistant prefill and re-sends when the model supports it. `c/base_coder.py:L1449–L1513`; `a/exceptions.py:L13–L57`; `a/models.py:L26`
- **Summarizer and commit-message fallback:** `ChatSummary` and `get_commit_message` try `[weak_model, main_model]` in order through `simple_send_with_retries`, which has its own backoff loop. `a/history.py:L98–L130`; `a/models.py:L1039–L1084`; `a/repo.py:L342–L364`

## Output
- **Edit formats as the tool set:** each `Coder` subclass pairs a prompt with a parser and applier: `EditBlockCoder.get_edits` parses SEARCH/REPLACE blocks and fenced shell blocks, `UnifiedDiffCoder` parses hunks, `WholeFileCoder` whole files, `PatchCoder` the apply-patch format. `c/editblock_coder.py:L15–L41`, `L439–L470`; `c/udiff_coder.py:L49–L94`; `c/__init__.py:L1–L34`
- **Fuzzy application and failure report:** `replace_most_similar_chunk` tries exact, whitespace-insensitive, and `...` elision matches; failed blocks produce a `ValueError` with the block, "did you mean" lines, and instructions to resend only the failed blocks. `c/editblock_coder.py:L157–L189`, `L79–L124`
- **Apply pipeline:** `apply_updates` runs parse, dry run, `prepare_to_edit` (per-file permission and dirty commit), and apply; edited files are auto-committed with a generated commit message and, if enabled, linted and tested. `c/base_coder.py:L2269–L2336`, `L2375–L2395`, `L1681–L1696`; `a/repo.py:L131–L140`
- **Shell execution:** model-suggested commands run after approval through `run_cmd` (pexpect interactive spawn on a POSIX TTY, otherwise `subprocess.Popen`) in the repo root with no sandbox; output is added to the chat only after a second confirmation. `c/base_coder.py:L2434–L2485`; `a/run_cmd.py:L11–L24`, `L42–L62`, `L89–L121`
- **Rendering:** streamed markdown is drawn live through `MarkdownStream`, reasoning tags are reformatted, and `/diff` shows the auto-commit diff. `c/base_coder.py:L1977–L1992`; `a/io.py:L1014–L1042`

## Production concerns
- **Persistence:** chat history is appended to `.aider.chat.history.md` and reloaded with `--restore-chat-history` (context); git commits are the durable artifact and `/undo` reverts aider's own commits (output); repo-map tags live in `.aider.tags.cache.v4` (context). `a/io.py:L1117–L1137`; `c/base_coder.py:L519–L523`; `a/commands.py:L553–L575`; `a/repomap.py:L35–L43`
- **Safety & security:** no sandbox; safety is the `confirm_ask` gates (control flow), gitignore and aiderignore checks before editing, and `--dry-run` (output). `c/base_coder.py:L2191–L2242`, `L2450–L2460`; `a/repo.py:L523–L566`
- **Observability:** per-message token and cost report from `completion.usage` including cache read/write tokens; `--llm-history-file` logs full prompts and responses; opt-in analytics send `message_send` and `exit` events with redacted model names to PostHog or Mixpanel. `c/base_coder.py:L1994–L2126`; `a/io.py:L754–L766`; `a/analytics.py:L213–L253`
- **Resilience:** backoff retries on transient provider errors (model interface), prefill continuation on output-length cutoff (model interface), the `exhausted` report on context overflow (context), and Ctrl-C handling that records the interruption in the transcript. `c/base_coder.py:L1456–L1513`, `L1575–L1583`, `L1628–L1680`
- **Performance:** streaming, prompt-cache headers plus keepalive pings, background summarization thread, repo-map memoization keyed by chat files and mentions, and lazy litellm import. `c/base_coder.py:L1340–L1394`; `a/repomap.py:L576–L627`; `a/llm.py:L21–L45`
- **Evaluation:** `benchmark/benchmark.py` runs Exercism and SWE-bench tasks in Docker per model and edit format; unit tests cover the coder loop, edit-block parsing, and the repo map. `b/benchmark.py:L679–L700`; `t/test_editblock.py:L1–L30`; `t/test_repomap.py:L1–L30`; `t/test_coder.py:L1–L30`

## Hard to place
- **Edit formats:** one class per format carries both the prompt (what the model is shown) and the parser/applier (what is done with the reply); by function the prompt text is context and `get_edits`/`apply_edits` are output, so the rules split a single component. `c/editblock_coder.py:L15–L41`; `c/editblock_prompts.py:L8–L28`
- **File mentions in the reply:** a model mention of a file name has the effect of a tool call (add file to context) without any tool; the rules resolve it as a context effect behind a control-flow approval gate, but the capture is text scanning, not a tool-call format. `c/base_coder.py:L1714–L1782`, `L1561–L1566`
- **Cache warming:** a background thread issues real model requests (`max_tokens=1`) whose response is discarded; it is a model-interface call made purely as a performance measure for context, with no input, output, or control-flow role. `c/base_coder.py:L1340–L1394`

## Summary
| Primitive | Design decision |
|---|---|
| Input | Terminal REPL, scripted message, or AI! file comments; results re-enter as plain text message pairs |
| Context | Ordered chunks: system, examples, PageRank repo map, files, weak-model summarized history; optional cache headers |
| Model interface | LiteLLM completion with streaming, exponential backoff to 60 s, assistant-prefill continuation on length cutoff |
| Output | Text edit formats parsed and fuzzily applied to files, auto-commit, lint/test, approved unsandboxed shell commands |
| Control flow | Reflection loop up to 3 re-sends on edit/lint/test failure; confirm gates; architect-to-editor two-coder handoff |
