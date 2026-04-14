# Reltio AI-Ready Documentation

> The complete Reltio product knowledge base — 3,200+ topics — optimized for AI consumption and available as structured Markdown. No authentication required.

![Last synced](https://img.shields.io/badge/Last%20synced-2026------04------14-blue)
![Topics](https://img.shields.io/badge/Topics-3%2C200%2B-green)
![Format](https://img.shields.io/badge/Format-Markdown-lightgrey)
![Access](https://img.shields.io/badge/Access-Public%2C%20no%20auth-brightgreen)

---

## Overview

Reltio AI-Ready Documentation gives you Reltio's entire product knowledge base in a format that AI tools can consume directly. The files in this repository are sourced from Reltio's authoring system — not scraped from HTML — and are updated weekly.

You can drop these files into any RAG pipeline, AI agent, coding assistant, or LLM with a single URL. No scraping. No authentication. No custom ETL.

> **Note:** These files are too large to preview in the GitHub web interface. See [Why you can't read these files on GitHub](#why-you-cant-read-these-files-on-github) for details and [How to use these files](#how-to-use-these-files) to get started.

---

## Files in this repository

### `docs.md` — Documentation corpus (~11 MB)

The complete Reltio documentation corpus compiled into a single Markdown file. It covers 3,200+ topics across all Reltio product areas:

- **Reltio MDM** — entity modeling, matching, merging, survivorship, data quality, APIs, and connectors
- **Reltio I360** — customer intelligence, analytics, and identity resolution
- **Administration** — security, access control, audit trails, and environment management
- **Integration** — REST APIs, webhooks, Kafka, and third-party connectors
- **Troubleshooting** — diagnostics, common errors, and performance tuning

**Source:** The content comes directly from Reltio's content management system (DITA XML), not from crawling docs.reltio.com. Tables, code blocks, step sequences, and cross-reference URLs are accurately converted. This means you get complete, consistent content — not a best-effort scrape.

**Use this file** when you want to give an AI tool access to the full Reltio knowledge base.

---

### `index.md` — Contextual retrieval index (~3 MB)

A structured index of every published Reltio topic. For each topic, the index provides:

| Field | Description |
|---|---|
| Hierarchy path | Full product area → category → topic path |
| Keywords | Topic-specific search terms |
| Summary | Short description of the topic's content |
| URL | Direct link to the topic on docs.reltio.com |
| Cross-references | Related topics and their paths |

**Use this file** alongside `docs.md` in RAG pipelines to significantly improve retrieval accuracy. The index gives AI models structural context about where each topic sits in the knowledge base — not just flat text — which reduces irrelevant results and improves grounding.

---

## Why you can't read these files on GitHub

GitHub's web interface has file size limits for preview and rendering:

| File | Size | GitHub behavior |
|---|---|---|
| `docs.md` | ~11 MB | "Sorry, this file is too large to display." |
| `index.md` | ~3 MB | Shown as plain text; Markdown not rendered |

Both files exceed GitHub's 512 KB Markdown rendering limit, and `docs.md` exceeds the 5 MB display limit entirely.

**This is expected behavior.** These files aren't designed to be read in a browser — they're designed to be consumed programmatically by AI tools, RAG pipelines, and developer tooling.

To use the files, download them using the raw URL (see [How to use these files](#how-to-use-these-files)).

---

## How to use these files

### Download with curl

```bash
# Download the documentation corpus
curl -L -o docs.md \
  https://raw.githubusercontent.com/reltio-ai/reltio-ai-ready-docs/main/docs.md

# Download the contextual retrieval index
curl -L -o index.md \
  https://raw.githubusercontent.com/reltio-ai/reltio-ai-ready-docs/main/index.md
```

### Clone the repository

```bash
git clone https://github.com/reltio-ai/reltio-ai-ready-docs.git
```

---

### Use in a RAG pipeline

Point your vector store or retrieval pipeline at `docs.md`. Use `index.md` to chunk by topic hierarchy for more accurate retrieval.

**LangChain**
```python
from langchain.document_loaders import TextLoader

loader = TextLoader("docs.md")
documents = loader.load()
```

**LlamaIndex**
```python
from llama_index.core import SimpleDirectoryReader

documents = SimpleDirectoryReader(input_files=["docs.md"]).load_data()
```

**AWS Bedrock Knowledge Bases**

Upload `docs.md` as a data source in your S3 bucket, then sync it to your Knowledge Base.

**Azure AI Search**

Index `docs.md` as a Blob Storage document using the built-in Markdown chunking skill.

---

### Use with AI coding assistants

Add `docs.md` to your project context so your coding assistant has full knowledge of Reltio's APIs, configuration model, and best practices.

**Claude Code**
```bash
# Reference the file directly in your conversation
@docs.md
```

**GitHub Copilot / Cursor / Windsurf**

Add `docs.md` to your workspace or project rules context.

---

### Use with large-context LLMs

For models with large context windows (Claude, Gemini 1.5+), you can pass `docs.md` directly as part of your prompt:

```python
import anthropic

with open("docs.md", "r") as f:
    docs = f.read()

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=4096,
    messages=[
        {
            "role": "user",
            "content": f"<reltio_docs>\n{docs}\n</reltio_docs>\n\nHow do I configure entity matching in Reltio?"
        }
    ]
)
print(response.content[0].text)
```

---

### Use in Zendesk, Salesforce Service Cloud, or support bots

Load `docs.md` into your support platform's knowledge base or AI bot. The structured Markdown format is compatible with all major support platforms that accept external knowledge sources.

---

## Common use cases

| Use case | Files to use | Notes |
|---|---|---|
| RAG pipeline / AI assistant | `docs.md` + `index.md` | Use `index.md` for better retrieval accuracy |
| AI coding assistant context | `docs.md` | Works with Claude Code, Copilot, Cursor, Codex |
| Support bot knowledge base | `docs.md` | Compatible with Zendesk, Salesforce, Intercom |
| Onboarding and training | `docs.md` | Query conversationally with any LLM |
| LLM direct context | `docs.md` | Best with large context window models |
| Custom GPT / AI agent | `docs.md` + `index.md` | Upload both files for best results |

---

## Sync schedule

This repository is updated **every Wednesday and Friday** from Reltio's content management system.

| Time (UTC) | US Pacific | US Eastern | India (IST) | Europe (CET) |
|---|---|---|---|---|
| 17:30 | 10:30 AM | 1:30 PM | 11:00 PM | 6:30 PM |

_* Previous day_

The files reflect the latest published documentation as of the sync date shown in the badge at the top of this page. If you're maintaining a local copy, run `git pull` or re-download the files on Wednesdays and Fridays to stay current.

---

## What's not included

These files contain published product documentation only. The following content is not included:

- API schemas (Swagger / OpenAPI specifications)
- SDK source code or code samples
- Support knowledge base articles
- Release notes in full detail
- Content in languages other than English

---

## License

© Reltio, Inc. All rights reserved.

The content in this repository is Reltio's published product documentation, made available for use with Reltio products and services. You may use these files to build AI tools, integrations, and workflows that consume Reltio documentation. You may not republish or redistribute the content as your own.
