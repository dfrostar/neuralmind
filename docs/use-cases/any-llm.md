# Use Case: Any LLM (ChatGPT / Gemini / Local Models)

## What you're solving for

You want NeuralMind-quality context but you're not using Claude Code, Cursor, or any MCP-compatible agent. You're in ChatGPT, Gemini, a Perplexity thread, an Ollama session, or just a custom script. You need **portable context** that fits any chat window.

## The pattern

NeuralMind's CLI output is plain text. Pipe it into any clipboard, file, or request body — the model doesn't care how it got there.

## Setup

```bash
pip install neuralmind graphifyy
cd your-project
graphify update .
neuralmind build .
```

## Patterns

### 1. Copy-paste into a web chat

**macOS:**
```bash
neuralmind wakeup . | pbcopy
# paste into ChatGPT / Gemini / Claude.ai
```

**Linux:**
```bash
neuralmind wakeup . | xclip -selection clipboard
```

**Windows (PowerShell):**
```powershell
neuralmind wakeup . | Set-Clipboard
```

Then start your chat with: "Here is the project context: `<paste>`. My question is …"

### 2. Piped into a one-shot script

```bash
CONTEXT=$(neuralmind query . "How does auth work?")
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d "$(jq -n --arg c "$CONTEXT" --arg q "explain the flow" '{
    model: "gpt-4o",
    messages: [
      {role: "system", content: $c},
      {role: "user", content: $q}
    ]
  }')"
```

### 3. Saved as a file the model reads

```bash
neuralmind wakeup . > CONTEXT.md
neuralmind query . "How does billing work?" > BILLING_CONTEXT.md
```

Attach those files to a Gemini Project, Claude Project, or Ollama system prompt. You get NeuralMind retrieval without needing the MCP server running.

### 4. Per-question context

Don't load the whole repo — load just what the question needs:

```bash
neuralmind query . "How does the payment webhook validate signatures?" | pbcopy
```

Paste, ask, done. Usually ~800–1,100 tokens instead of tens of thousands.

## What you lose vs. Claude Code

- **No PostToolUse compression** — that's Claude-Code-specific. You still get the retrieval-side savings (40–70×), just not the additional Read/Bash/Grep compression layer.
- **No MCP tool calls** — the model can't invoke `neuralmind_query` itself; you invoke it and paste.

## What you still get

- The same 4-layer progressive disclosure
- The same skeleton views (`neuralmind skeleton <file>`)
- The same semantic search (`neuralmind search . "term"`)
- Fully local, no data leaves your machine
- Works with any model — OpenAI, Google, Anthropic, Ollama, vLLM, anything

## Pro tip: system prompt pattern

Generate context once at the start of a long session:

```bash
neuralmind wakeup . > /tmp/sys.md
```

Set the contents of `/tmp/sys.md` as your system prompt. For specific questions during the session, append `neuralmind query . "..."` output to the user message.

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
