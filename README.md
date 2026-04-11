# TechPulse AI

### *Your intelligent tech pulse, curated by AI.*

TechPulse AI is an automated news aggregator designed for developers and AI enthusiasts. It monitors top-tier tech sources, filters through the noise, and delivers concise, high-value summaries directly to your favorite communication platforms.

---

## Key Features

- **Smart Ingestion**: Aggregates news from Hacker News, Dev.to, and other premium RSS feeds.
- **AI-Powered Summaries**: Uses **Groq (Llama 3)** to generate developer-focused summaries—skipping the hype and getting straight to why it matters.
- **Real-time Stream Processing**: Powered by Redis streams for efficient, reliable data handling.
- **Multi-Channel Delivery**: Instant digests delivered to **Slack** and **Discord** via webhooks.
- **Scoring System**: Intelligently ranks articles so you only see the most relevant tech breakthroughs.

## Technology Stack

- **Language**: Python 3.12+
- **Inference**: Groq (Llama-3.3-70b-versatile)
- **Database**: Supabase (PostgreSQL)
- **Cache**: Upstash Redis
- **Infrastructure**: Designed for serverless or containerized deployment

## Quick Start (High-Level)

### 1. Prerequisites
- Python 3.12+
- API keys for: Groq, Supabase, and Upstash Redis.
- (Optional) Slack or Discord Webhooks.

### 2. Environment Setup
Copy the `.env.example` (if provided) or create a `.env` file with your credentials:
```env
GROQ_API_KEY=your_key
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
UPSTASH_REDIS_REST_URL=your_url
UPSTASH_REDIS_REST_TOKEN=your_token
```

### 3. Run the Services
TechPulse AI is built as a set of independent services:
- **Collect**: `python -m services.collector.main`
- **Summarize**: `python -m services.summarizer.main`
- **Deliver**: `python -m services.delivery.main`

---

## License
MIT License. Feel free to use and contribute!
