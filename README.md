# TechPulse AI 🤖

### *Your intelligent tech pulse, curated by AI.*

TechPulse AI is a high-performance, automated news aggregator designed for developers and AI enthusiasts. It monitors top-tier tech sources, filters the noise using intelligent heuristics, and delivers concise, high-value summaries directly to Slack and Discord.

The system is architected for **zero-cost operation**, leveraging free-tier services (Groq, Upstash, Supabase) and optimized for minimal resource consumption.

---

## 🔥 Key Features

- **🚀 Async Performance**: Refactored with `asyncio` to reduce GitHub Actions execution time by ~70%, saving valuable free-tier minutes.
- **🧠 Zero-Cost Pro Summaries**: Powered by **Groq (Llama-3.1-8b-instant)**. Optimized for high throughput and reliable processing without hitting free-tier rate limits.
- **🛡️ Reliable Stream Pipeline**: Uses **Redis Consumer Groups** (`XREADGROUP`/`XACK`) to ensure at-least-once processing. No message is lost if a database or network failure occurs.
- **🔍 Smart Deduplication**: Two-layer deduplication (URL hashing + Normalized Title hashing) ensures you never receive the same story twice, even from different sources.
- **⚡ Proactive Maintenance**: Includes a master "System Reset" tool to easily clear streams and database history for a fresh start.
- **📡 Multi-Channel Delivery**: Formatted Block Kit payloads for Slack and Markdown-optimized chunks for Discord.

---

## 🏗️ Technical Architecture

```mermaid
graph TD
    Collector[Collector / RSS Scraper] -->|URL/Title Dedup| Filter[Keywords Filter]
    Filter -->|XADD| Stream[(Redis Stream)]
    Stream -->|XREADGROUP| Summarizer[Async Summarizer]
    Summarizer -->|Groq API| LLM[Llama 3.1 8B]
    LLM -->|JSON Schema| Summarizer
    Summarizer -->|Upsert| DB[(Supabase PostgreSQL)]
    Summarizer -->|XACK| Stream
    Delivery[Delivery Service] -->|Get Top Articles| DB
    Delivery -->|Webhook| Slack[Slack]
    Delivery -->|Webhook| Discord[Discord]
```

---

## 🛠️ Technology Stack

- **Framework**: Python 3.12+ (Asyncio, Pydantic, Loguru)
- **Dependency Management**: [uv](https://github.com/astral-sh/uv)
- **Inference**: Groq (Llama-3.1-8b-instant)
- **Database**: Supabase (PostgreSQL)
- **Stream/De-duplication**: Upstash Redis
- **Deployment**: GitHub Actions (Scheduled CRON runs)

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.12+ and `uv` installed.
- API keys for: Groq, Supabase, and Upstash Redis.
- Slack or Discord Webhooks (Optional).

### 2. Setup
Clone the repo and install dependencies:
```bash
uv sync
```

### 3. Environment Config
Create a `.env` file from the following template:
```env
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.1-8b-instant
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
UPSTASH_REDIS_REST_URL=your_url
UPSTASH_REDIS_REST_TOKEN=your_token
SLACK_WEBHOOK_URL=your_url
DISCORD_WEBHOOK_URL=your_url
TOP_N_ARTICLES=10
DEDUP_TTL_DAYS=7
```

### 4. Running Locally
You can run the full pipeline with a single command:
```bash
uv run python -m services.collector.main && \
uv run python -m services.summarizer.main && \
uv run python -m services.delivery.main
```

---

## 🧹 Maintenance & Testing

### Master Storage Reset
To wipe all Redis streams, deduplication data, and database history:
```bash
uv run python -m shared.maintenance reset --confirm
```

### End-to-End Test
To verify the entire pipeline (injection -> summary -> delivery) without waiting for fresh news:
```bash
PYTHONPATH=. uv run python scratch/test_e2e.py
```

---

## 📜 License
MIT License. Feel free to use and contribute!
