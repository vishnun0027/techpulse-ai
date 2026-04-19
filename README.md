# TechPulse AI

### Intelligent technology news aggregation curated by AI.

TechPulse AI is an automated news aggregation system designed to monitor high-signal technology sources, filter for relevance using intelligent heuristics, and deliver concise summaries directly to your preferred communication channels.

The system is designed for high efficiency and scalability, utilizing a multi-tenant architecture that allows for personalized news feeds and topic filtering for multiple users simultaneously.

---

## Features

- **Multi-Tenant Architecture**: Optimized for individual user personalization with isolated RSS source management and topic filtering.
- **AI-Powered Summarization**: Leverages large language models to generate technical summaries and relevance scores tailored to user profiles.
- **Intelligent Filtering**: Implements a multi-tier keyword system to prioritize critical updates and filter out irrelevant content.
- **automated Freshness Control**: Enforces strict publication date limits to ensure only the most recent and relevant news is processed.
- **Unified Command Line Interface**: Professional CLI tools for both system management and personal account configuration.
- **Multi-Channel Delivery**: Native support for delivering digests to Slack and Discord.

---

## Getting Started

### 1. Prerequisites
- Python 3.12 or higher.
- Access to Supabase, Groq, and Redis (Upstash) instances.

### 2. Installation
Clone the repository and install the required dependencies:
```bash
uv sync
```

### 3. Database Initialization
Initialize your database schema by applying the consolidated migration file found in:
`migrations/setup_supabase.sql`

### 4. Configuration
Create a `.env` file based on the following template to configure your external service connections:
```env
SUPABASE_URL=your_project_url
SUPABASE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_public_key
GROQ_API_KEY=your_groq_api_key
UPSTASH_REDIS_REST_URL=your_redis_url
UPSTASH_REDIS_REST_TOKEN=your_redis_token
COLLECTION_INTERVAL_DAYS=14
```

---

## Usage

### User CLI (`techpulse`)
Manage your personal news sources and topic filters:
```bash
# Log in to your personal account
uv run techpulse login

# List and manage your RSS sources
uv run techpulse sources list

# View your personal pipeline status
uv run techpulse status
```

### Operator CLI (`techpulse-ops`)
For system-wide execution and service management:
```bash
# Execute the full processing pipeline
uv run techpulse-ops run all

# Monitor system-wide health and telemetry
uv run techpulse-ops monitor
```

---

## Technical Documentation
For detailed information on the system architecture, data flow, and developer guidelines, please refer to:
**[developer.md](developer.md)**

---

## License
Distributed under the MIT License.
