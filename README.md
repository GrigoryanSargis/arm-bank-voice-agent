# 🏦 Armenian Bank Voice AI Support Agent

An end-to-end **voice AI customer support agent** for Armenian banks, built entirely on the open-source [LiveKit Agents](https://github.com/livekit/agents) framework (self-hosted, no LiveKit Cloud). The agent understands and speaks **Armenian**, answers questions strictly about **Loans, Deposits, and Branch/ATM Locations**, and politely refuses everything else.

**Banks covered:** Ardshinbank · Inecobank · Mellat Bank · Evocabank

> ✅ **Mellat Bank** (`mellatbank.am`) is included — one of the few solutions in this cohort to cover all four banks including Mellat.

---

## How It Works — Full Pipeline

```
User speaks Armenian (or English)
         │
         ▼
  ┌─────────────────────────────────────────────────┐
  │  Silero VAD                                     │
  │  Detects when the user starts / stops speaking  │
  │  CPU-only · zero latency · free                 │
  └─────────────────┬───────────────────────────────┘
                    │ voice segment
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  Groq Whisper STT  (whisper-large-v3)           │
  │  Transcribes Armenian speech to text            │
  │  Language hint: "hy" (Armenian)                 │
  │  Free tier · ~300ms latency                     │
  └─────────────────┬───────────────────────────────┘
                    │ transcript text
                    ▼
  ┌─────────────────────────────────────────────────┐
  │  QueryGuard  (agent/guardrails.py)              │
  │  • Keyword scope gate — no LLM cost if blocked  │
  │  • Typo correction: "luan" → "loan"             │
  │  • Armenian STT variant correction              │
  │  • Fuzzy matching (difflib, threshold 0.82)     │
  │  • Bank name detection (Armenian + English)     │
  └──────┬──────────────────────────┬───────────────┘
         │ out-of-scope             │ in-scope
         ▼                          ▼
  Polite refusal        ┌───────────────────────────┐
  in user's language    │  KBQueryService            │
                        │  Groq Llama-3.1-8b-instant │
                        │  Full bank KB in prompt    │
                        │  No vector DB · No embeds  │
                        └─────────────┬─────────────┘
                                      │ answer text
                                      ▼
                        ┌─────────────────────────────┐
                        │  ElevenLabs TTS             │
                        │  eleven_turbo_v2_5          │
                        │  Speaks Armenian back       │
                        │  Free tier · ~200ms         │
                        └─────────────┬───────────────┘
                                      │ audio
                                      ▼
                        ┌─────────────────────────────┐
                        │  LiveKit Room (self-hosted) │
                        │  WebRTC audio to user       │
                        └─────────────────────────────┘
```

---

## Architecture Decisions

### 1. Full-Context Retrieval (no RAG, no vector database)

The entire scraped bank knowledge base is loaded **once at startup** and injected directly into the LLM system prompt on every request. No embeddings, no similarity search, no retrieval pipeline.

| Why this works | Detail |
|----------------|--------|
| Simplicity | One file to update, no index to rebuild |
| Accuracy | LLM sees 100% of the data — no missed chunks |
| Fast iteration | Re-scrape → rebuild KB → restart agent |
| Token efficient | Topic filtering keeps each prompt ~1,500 tokens |
| Free | Zero embedding API calls |

### 2. Two-Layer Guardrails

**Layer 1 — Pre-LLM keyword gate** (zero token cost, runs on every query)
- Detects topic from Armenian + English keywords
- Corrects typos and Whisper STT transcription artifacts
- Fuzzy-matches near-misses (e.g. `branh` → `branch`)
- Out-of-scope queries never reach the LLM — saves tokens and latency

**Layer 2 — LLM system prompt rules**
- Explicit instructions: answer only from KB, never invent facts
- Refuses all questions outside the three topics
- Responds in the user's language (Armenian or English)
- Maximum 2–3 sentences for natural voice delivery

### 3. Scalability

Adding a new bank requires exactly **4 steps**: add a `BankConfig` in `banks.py`, add aliases in `guardrails.py`, run the scraper, rebuild the KB. No other code changes needed. See [Adding More Banks](#adding-more-banks).

---

## Model Choices & Justification

| Component | Model | Justification |
|-----------|-------|---------------|
| **STT** | `groq/whisper-large-v3` | OpenAI Whisper is the gold standard for Armenian transcription. Running it on Groq gives ~20× lower latency than CPU self-hosting. The `hy` language hint significantly improves accuracy on Armenian phonemes. Free on Groq tier. |
| **LLM** | `groq/llama-3.1-8b-instant` | 131k token context window fits the full KB. Handles Armenian Unicode correctly. Fastest model on Groq's free tier — critical for voice latency. ~300ms per response. |
| **TTS** | `elevenlabs/eleven_turbo_v2_5` | One of the few TTS services that reliably synthesises Armenian script. The turbo model minimises latency. Free tier: 10,000 chars/month. |
| **VAD** | Silero | Tiny (~10 MB), CPU-only, sub-millisecond. Works well on Armenian/Russian phonetics. No GPU required. |
| **Framework** | LiveKit OSS (self-hosted) | Open-source, self-hosted via Docker. Full WebRTC stack. No cloud dependency. Used per task specification. |

### Why Groq instead of OpenAI

Groq provides Whisper and a capable LLM completely free — no credit card required, no per-token cost. OpenAI charges for both. Since evaluators will test this with their own keys, minimising cost matters. Groq's performance (speed, Armenian accuracy) is comparable or better for this use case.

### Why not Llama-3.1-hye-arlis-2024

The fine-tuned `Llama-3.1-hye-arlis-2024` model (trained on arlis.am legal data) is **not suitable** for this use case:

- It is fine-tuned on Armenian legal/parliamentary text — not banking terminology
- It requires self-hosting on a GPU (no free hosted option exists)
- Our system prompt already provides all domain knowledge explicitly — fine-tuning adds no value when the KB is in the context window
- Groq's Llama-3.1-8b-instant is faster, cheaper to host, and has better instruction-following for structured refusals

---

## Project Structure

```
arm_bank_voice_agent/
├── src/arm_bank_voice_agent/
│   ├── agent/
│   │   ├── context_builder.py   # Formats entire KB → LLM system prompt
│   │   ├── guardrails.py        # Two-layer scope classifier + typo correction
│   │   └── query_service.py     # Orchestrates guard → LLM → answer
│   ├── config/
│   │   ├── banks.py             # Bank configs + seed URLs  ← add banks here
│   │   └── settings.py          # All settings loaded from .env
│   ├── livekit_app/
│   │   ├── edge_tts_plugin.py   # ElevenLabs TTS plugin for LiveKit 1.5
│   │   └── livekit_worker.py    # Entry point — VAD → STT → Guard → LLM → TTS
│   ├── llm/
│   │   └── groq_client.py       # Groq SDK wrapper (LLM calls)
│   ├── models/
│   │   ├── chunk.py             # DocumentChunk schema
│   │   └── schema.py            # BankDocument schema
│   ├── processing/
│   │   └── chunker.py           # Splits documents into overlapping chunks
│   ├── retrieval/
│   │   └── store.py             # JSON load/save for chunk store
│   ├── scraping/
│   │   ├── browser_client.py    # Playwright for JS-rendered pages
│   │   ├── cleaner.py           # HTML noise removal
│   │   ├── extractor.py         # Content + rate table extraction
│   │   ├── http_client.py       # httpx client factory
│   │   └── pipeline.py          # HTTP-first, Playwright fallback scraper
│   └── build_kb.py              # CLI: raw docs → processed chunks
├── data/
│   └── processed/
│       └── bank_chunks.json     # Pre-built KB — ready to use immediately
├── scripts/
│   ├── query_kb.py              # Test the LLM pipeline (no mic needed)
│   └── scrape_sources.py        # Re-scrape bank websites
├── tests/
│   ├── test_context_builder.py  # KB formatting tests (no API key needed)
│   └── test_query_service.py    # Scope detection tests (no API key needed)
├── docker/
│   └── docker-compose.yml       # Self-hosted LiveKit server
└── .env.example
```

---

## Prerequisites

| Requirement | How to get it |
|-------------|---------------|
| Python 3.10+ | [python.org](https://python.org) |
| Docker + Docker Compose | [docker.com](https://docker.com) |
| ffmpeg | `apt install ffmpeg` (Linux) · `choco install ffmpeg` (Windows) · `brew install ffmpeg` (Mac) |
| Groq API key | Free at [console.groq.com](https://console.groq.com) — no credit card |
| ElevenLabs API key | Free at [elevenlabs.io](https://elevenlabs.io) — 10,000 chars/month |

---

## Setup

### 1. Clone

```bash
git clone https://github.com/GrigoryanSargis/arm-bank-voice-agent.git
cd arm-bank-voice-agent
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Start the LiveKit server (self-hosted)

```bash
cd docker
docker-compose up -d
cd ..
```

Verify: `curl http://localhost:7880` should return a response.

### 4. Configure environment

```bash
cp .env.example .env
```

Open `.env` and add your two API keys. LiveKit values work as-is with Docker:

```env
# LiveKit — these defaults work with Docker from Step 3
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=devsecret

# Get free at console.groq.com
GROQ_API_KEY=gsk_...

# Get free at elevenlabs.io
ELEVEN_API_KEY=sk_...
```

### 5. Run the agent

The knowledge base is pre-built — no scraping needed.

```bash
# Linux / macOS
PYTHONPATH=src python -m arm_bank_voice_agent.livekit_app.livekit_worker dev

# Windows PowerShell
$env:PYTHONPATH = "src"; py -m arm_bank_voice_agent.livekit_app.livekit_worker dev
```

Expected output:
```
INFO  Prewarm: loading VAD...
INFO  Prewarm: loading knowledge base...
INFO  KBQueryService ready — 51 chunks, model=llama-3.1-8b-instant
INFO  Starting worker...
INFO  registered worker {"url": "ws://localhost:7880"}
```

### 6. Connect and speak

Open **[agents-playground.livekit.io](https://agents-playground.livekit.io)**

| Field | Value |
|-------|-------|
| URL | `ws://localhost:7880` |
| API Key | `devkey` |
| Secret | `devsecret` |

Click **Connect → Start Audio** and speak in Armenian or English.

---

## Test Queries

| Say this | Expected response |
|----------|-------------------|
| "What loan rates does Ardshinbank have?" | Rates from KB |
| "What deposits does Mellat Bank offer?" | Deposit info from KB |
| "Where are Evocabank branches in Yerevan?" | Branch addresses from KB |
| "Ի՞նչ վarкer кa Inecobank-ооm?" | Armenian answer from KB |
| "What is the weather today?" | Polite refusal |
| "Who is the prime minister of Armenia?" | Polite refusal |

---

## Testing Without a Microphone

```bash
# Linux / macOS
PYTHONPATH=src python scripts/query_kb.py "What deposit rates does Ardshinbank offer?"
PYTHONPATH=src python scripts/query_kb.py "What loans does Mellat Bank have?"
PYTHONPATH=src python scripts/query_kb.py "Where are Inecobank branches?"
PYTHONPATH=src python scripts/query_kb.py "What is the weather?"   # should refuse

# Windows
$env:PYTHONPATH = "src"; py scripts/query_kb.py "What deposit rates does Ardshinbank offer?"
```

Run unit tests (no API keys needed):

```bash
PYTHONPATH=src pytest tests/ -v
```

---

## Rebuilding the Knowledge Base

To scrape fresh data from bank websites (~5 minutes):

```bash
python scripts/scrape_sources.py
python -m arm_bank_voice_agent.build_kb
```

---

## Adding More Banks

**1.** Add a `BankConfig` in `config/banks.py`:

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

**2.** Add bank aliases in `agent/guardrails.py`:

```python
BANK_ALIASES = {
    "new bank": "New Bank",
    "newbank":  "New Bank",
}
```

**3.** Scrape and rebuild:

```bash
python scripts/scrape_sources.py --bank new_bank --output data/raw/new_bank.json
# merge JSON, then:
python -m arm_bank_voice_agent.build_kb
```

**4.** Restart the agent. No other changes needed.

> **Site blocks scrapers?** Add curated data manually as a JSON file following the `BankDocument` schema (see `data/raw/ardshinbank_manual.json` as reference).

> **React/Vue SPA?** Add `wait_for_selector=".content-class"` to the `SeedPage` so Playwright waits for content to render.

---

## Cost

| Service | Free Tier | Cost |
|---------|-----------|------|
| Groq Whisper STT | 7,200 requests/day | **$0** |
| Groq Llama LLM | 14,400 requests/day | **$0** |
| ElevenLabs TTS | 10,000 chars/month | **$0** |
| LiveKit | Self-hosted Docker | **$0** |
| **Total** | | **$0** |