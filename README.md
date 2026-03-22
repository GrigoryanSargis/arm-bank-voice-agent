# Armenian Bank Voice AI Support Agent

A production-ready **voice AI customer support agent** for Armenian banks, built on the open-source [LiveKit Agents](https://github.com/livekit/agents) framework. The agent understands and speaks **Armenian**, answers questions about **Loans, Deposits, and Branch/ATM Locations** for four banks, and refuses all out-of-scope queries.

**Banks covered:** Ardshinbank · Inecobank · Mellat Bank · Evocabank

---

## Architecture

```
User microphone
      │
      ▼
 Silero VAD ──────────────────── detects speech boundaries (CPU, free)
      │
      ▼
 Groq Whisper STT ─────────────── whisper-large-v3, language hint "hy"
 (free tier)                       best available free Armenian STT
      │ (transcript)
      ▼
 QueryGuard ───────────────────── keyword + fuzzy scope classifier
      │                            blocks off-topic before any LLM call
      │ (in-scope)
      ▼
 KBQueryService ───────────────── Groq Llama-3.1-8b-instant
 (free tier)                       full bank KB injected in system prompt
                                   no vector DB · no embeddings
      │ (answer text)
      ▼
 ElevenLabs TTS ───────────────── eleven_turbo_v2_5, Armenian voice
 (free tier)                       speaks the answer back to the user
      │ (audio frames)
      ▼
 LiveKit Room ─────────────────── WebRTC back to user browser/app
 (cloud or self-hosted)
```

### Full-Context Retrieval — Design Decision

This project deliberately does **not** use a vector database or embeddings. Instead, the entire scraped bank knowledge base is loaded once at startup and injected directly into the LLM system prompt on every request.

**Why this approach:**

| Reason | Explanation |
|--------|-------------|
| Simplicity | No embedding model, no index, no retrieval pipeline to debug |
| Accuracy | LLM sees all data at once — no missed chunks from retrieval failures |
| Easy iteration | Change KB by re-scraping; no reindexing step needed |
| Token efficiency | Topic filtering (credit / deposit / branch) keeps each prompt under 6k tokens |
| Cost | Zero embedding API calls; stays within Groq free tier |

---

## Model Choices & Justification

| Component | Model | Why |
|-----------|-------|-----|
| **STT** | `groq/whisper-large-v3` | Best free Armenian transcription; Groq inference ~20× faster than CPU self-hosting; native `hy` language hint improves accuracy significantly |
| **LLM** | `groq/llama-3.1-8b-instant` | 131k token context; handles Armenian Unicode correctly; fastest Groq free tier model; low latency suits real-time voice |
| **TTS** | `elevenlabs/eleven_turbo_v2_5` | Supports Armenian script natively; low-latency turbo model; free tier 10k chars/month |
| **VAD** | Silero | ~10 MB CPU-only model; sub-millisecond inference; excellent sensitivity on Armenian/Russian phonetics |
| **Framework** | LiveKit OSS | Self-hosted open-source WebRTC; no cloud vendor lock-in |

### Why Groq over OpenAI

Both Whisper and a capable LLM are available completely free on Groq's tier — no credit card required, no per-token cost. OpenAI requires payment. For a project targeting Armenian banks where zero cost is a hard requirement, Groq is the correct choice.

### Why not a fine-tuned Armenian model (e.g. Llama-3.1-hye-arlis-2024)

A general-purpose model like Llama-3.1-8b-instant outperforms domain-specific fine-tuned models for this use case because:
- Our system prompt provides the domain knowledge (bank data) explicitly — fine-tuning buys nothing extra
- A fine-tuned model requires self-hosting with a GPU, which is neither free nor low-latency
- Groq's infrastructure provides response times that self-hosted inference cannot match

---

## Guardrails

The `QueryGuard` class (`agent/guardrails.py`) provides two layers of protection:

**Layer 1 — Pre-LLM keyword gate (zero token cost)**
- Detects topic (credit / deposit / branch) from keywords in Armenian and English
- Corrects common typos: `luan` → `loan`, `depost` → `deposit`, `branh` → `branch`
- Corrects Armenian STT transcription variants: `varkeri` → `վarкер`
- Fuzzy-matches misspelled words using `difflib` (threshold 0.82)
- Detects which bank is mentioned by name or alias in any language

**Layer 2 — LLM system prompt enforcement**
- Explicit scope rules forbid the model from answering off-topic questions
- LLM instructed to base every answer solely on KB data — never invent rates or addresses
- Responses capped at 2–3 sentences for voice-friendliness

---

## Project Structure

```
arm_bank_voice_agent/
├── src/arm_bank_voice_agent/
│   ├── agent/
│   │   ├── context_builder.py   # Formats entire KB → LLM system prompt
│   │   ├── guardrails.py        # Scope classifier + typo correction
│   │   └── query_service.py     # Orchestrates guard → LLM → answer
│   ├── config/
│   │   ├── banks.py             # Bank configs + seed URLs (add banks here)
│   │   └── settings.py          # All env var settings
│   ├── livekit_app/
│   │   ├── edge_tts_plugin.py   # ElevenLabs TTS wrapper for LiveKit
│   │   └── livekit_worker.py    # Main entry point — full voice pipeline
│   ├── llm/
│   │   └── groq_client.py       # Thin Groq SDK wrapper
│   ├── models/
│   │   ├── chunk.py             # DocumentChunk pydantic model
│   │   └── schema.py            # BankDocument pydantic model
│   ├── processing/
│   │   └── chunker.py           # Splits documents into overlapping text chunks
│   ├── retrieval/
│   │   └── store.py             # JSON serialisation for chunk store
│   ├── scraping/
│   │   ├── browser_client.py    # Playwright for JS-rendered pages
│   │   ├── cleaner.py           # HTML noise removal
│   │   ├── extractor.py         # Structured content + rate table extraction
│   │   ├── http_client.py       # httpx client factory
│   │   └── pipeline.py          # Scraping orchestrator with http→browser fallback
│   └── build_kb.py              # CLI: raw docs → processed chunks
├── data/
│   ├── raw/                     # Scraped JSON (gitignored)
│   └── processed/
│       └── bank_chunks.json     # Ready-to-use KB (committed for convenience)
├── scripts/
│   ├── query_kb.py              # CLI test tool — no microphone needed
│   └── scrape_sources.py        # Re-scrape bank websites
├── tests/
│   ├── test_context_builder.py
│   └── test_query_service.py
├── docker/
│   └── docker-compose.yml       # Self-hosted LiveKit server (optional)
├── .env.example
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.10+ | `python --version` to check |
| ffmpeg | `apt install ffmpeg` (Linux) · `choco install ffmpeg` (Windows) |
| Groq API key | Free at [console.groq.com](https://console.groq.com) — no credit card |
| ElevenLabs API key | Free at [elevenlabs.io](https://elevenlabs.io) — 10k chars/month free |
| LiveKit project | Free cloud at [livekit.io](https://livekit.io) — or self-host via Docker |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/arm-bank-voice-agent.git
cd arm-bank-voice-agent
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your three API keys — everything else has working defaults:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

GROQ_API_KEY=gsk_...

ELEVEN_API_KEY=sk_...
```

### 4. Knowledge base is pre-built

`data/processed/bank_chunks.json` is included in the repo — skip straight to Step 5.

To rebuild from fresh scraping (re-fetches live bank websites, ~5 minutes):

```bash
python scripts/scrape_sources.py
python -m arm_bank_voice_agent.build_kb
```

### 5. Run the voice agent

```bash
# Linux / macOS
PYTHONPATH=src python -m arm_bank_voice_agent.livekit_app.livekit_worker dev

# Windows PowerShell
$env:PYTHONPATH = "src"; py -m arm_bank_voice_agent.livekit_app.livekit_worker dev
```

You should see:

```
INFO  Prewarm: loading VAD...
INFO  Prewarm: loading knowledge base...
INFO  KBQueryService ready — 38 chunks, model=llama-3.1-8b-instant
INFO  Starting worker...
INFO  registered worker  {"url": "wss://your-project.livekit.cloud"}
```

### 6. Connect and speak

Open **[agents-playground.livekit.io](https://agents-playground.livekit.io)**

Enter your LiveKit credentials → **Connect** → **Start Audio** and speak.

Example queries to try:

| Query | Expected |
|-------|----------|
| Ի՞նչ տοκosadrooyт oonenи Ardshinbank varкerы? | Loan rates from KB |
| What deposit rates does Evocabank offer? | Deposit info from KB |
| Mellat Bank-i masnahajoghnerы oortegher ен? | Branch addresses |
| What is the weather today? | Polite refusal |

---

## Testing Without Voice

Test the full pipeline from the command line — no microphone or LiveKit needed:

```bash
# Linux / macOS
PYTHONPATH=src python scripts/query_kb.py "What deposit rates does Ardshinbank offer?"
PYTHONPATH=src python scripts/query_kb.py "What consumer loans does Inecobank have?"
PYTHONPATH=src python scripts/query_kb.py "Where are Mellat Bank branches?"
PYTHONPATH=src python scripts/query_kb.py "What is the weather?"   # → refusal

# Windows PowerShell
$env:PYTHONPATH = "src"; py scripts/query_kb.py "What deposit rates does Ardshinbank offer?"
```

Run unit tests (no API keys required):

```bash
PYTHONPATH=src pytest tests/ -v
```

---

## Adding More Banks

The system scales to any number of banks with minimal changes.

**1. Add a `BankConfig` entry in `config/banks.py`:**

```python
"new_bank": BankConfig(
    name="New Bank",
    allowed_domains=("newbank.am", "www.newbank.am"),
    seed_pages=(
        SeedPage(topic="credit",  url="https://newbank.am/en/loans",    language="en"),
        SeedPage(topic="deposit", url="https://newbank.am/en/deposits", language="en"),
        SeedPage(topic="branch",  url="https://newbank.am/en/branches", language="en"),
    ),
),
```

**2. Add aliases in `agent/guardrails.py`:**

```python
BANK_ALIASES = {
    ...
    "new bank": "New Bank",
    "newbank":  "New Bank",
}
```

**3. Scrape and rebuild:**

```bash
python scripts/scrape_sources.py --bank new_bank --output data/raw/new_bank.json
# merge into bank_documents.json, then:
python -m arm_bank_voice_agent.build_kb
```

**4. Restart the agent.** No other code changes needed.

> **If the bank's website blocks scraping:** Create a manual JSON file under `data/raw/` following the `BankDocument` schema with curated content, then merge it before rebuilding. See `data/raw/ardshinbank_manual.json` for an example.

> **If the page is a React/Vue SPA:** Add `wait_for_selector=".your-content-class"` to the `SeedPage` config so Playwright waits for the content to render before extracting.

---

## Cost

| Service | Free Tier | Cost |
|---------|-----------|------|
| Groq Whisper STT | 7,200 requests/day | **$0** |
| Groq Llama LLM | 14,400 RPD · 500k TPM | **$0** |
| ElevenLabs TTS | 10,000 chars/month | **$0** |
| LiveKit | Free hosted tier | **$0** |
| **Total** | | **$0** |
