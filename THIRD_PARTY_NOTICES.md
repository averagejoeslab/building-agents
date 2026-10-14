# Third-party notices

This repository's own work is licensed as its [README](./README.md#license) says. The material below comes from others, keeps its own license, and is not covered by this repository's licenses.

## Training data in `data/`

The committed data is built from these public sources, so that a reproduction trains on exactly what the record was made with.

| File | Built from | License | Changes |
|---|---|---|---|
| `data/shakespeare.txt` | [Tiny Shakespeare](https://github.com/karpathy/char-rnn/tree/master/data/tinyshakespeare), from Shakespeare's plays | public domain | none |
| `data/midtrain.pt` | [tldr-pages](https://github.com/tldr-pages/tldr), © the tldr-pages authors | [CC BY 4.0](./LICENSE-CC-BY-4.0) | the `common` and `linux` pages, less those too near an evaluation request; tokenized with the Qwen3 tokenizer, and some kept as text for a check |
| `data/instruct.pt`, `data/round1/instruct.pt` | [smol-smoltalk](https://huggingface.co/datasets/HuggingFaceTB/smol-smoltalk), Hugging Face | [Apache 2.0](./licenses/Apache-2.0.txt) | a sample of conversations, in Qwen's chat format |
| | [NL2Bash](https://github.com/TellinaTool/nl2bash) (`data/bash`), © 2020 NL2Bash dataset | [MIT](./licenses/MIT-NL2Bash.txt) | a sample of request–command pairs, turned into tool calls in Qwen's chat format |
| | [GSM8K](https://github.com/openai/grade-school-math), © 2021 OpenAI | [MIT](./licenses/MIT-GSM8K.txt) | a sample of problems, with the worked steps as thinking, in Qwen's chat format |
| | [Hermes function-calling v1](https://huggingface.co/datasets/NousResearch/hermes-function-calling-v1), Nous Research | [Apache 2.0](./licenses/Apache-2.0.txt) | a sample of conversations, in Qwen's chat and tool format |
| | [Magicoder OSS-Instruct 75K](https://huggingface.co/datasets/ise-uiuc/Magicoder-OSS-Instruct-75K), © 2023 iSE-UIUC | [MIT](./licenses/MIT-Magicoder.txt) | a sample of problems and solutions, in Qwen's chat format |

The rest of the conversations in the `instruct.pt` files, the ones that work as quark, are this repository's own. Every sample leaves out anything too near an evaluation request.

The book quotes a GSM8K word problem in Chapter 9, with the people's names changed.

## Models

[Qwen3-0.6B and Qwen3-0.6B-Base](https://huggingface.co/Qwen/Qwen3-0.6B-Base) are released by the Qwen team under the [Apache 2.0](./licenses/Apache-2.0.txt) license. Their weights and tokenizer are downloaded when the code runs; they are not in this repository, and neither are the checkpoints trained from them (`models/`).

## Fonts in `book/ebook/fonts/`

| Font | Copyright | License |
|---|---|---|
| Source Serif 4 | © 2014–2023 Adobe, with Reserved Font Name 'Source' | [SIL Open Font License 1.1](./book/ebook/fonts/OFL-SourceSerif4.txt) |
| Inter | © 2016 The Inter Project Authors | [SIL Open Font License 1.1](./book/ebook/fonts/OFL-Inter.txt) |

They are embedded in `book/Building-Agents.pdf`.
