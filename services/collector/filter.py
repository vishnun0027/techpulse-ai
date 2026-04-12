# services/collector/filter.py

ALLOWED_TOPICS = [
    # AI & LLM
    "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
    "mistral", "llama", "agent", "rag", "embedding", "chatbot",
    "transformer", "diffusion", "multimodal", "fine-tun",

    # ML & Data
    "machine learning", "deep learning", "neural", "pytorch",
    "tensorflow", "dataset", "model", "training", "inference",
    "benchmark", "computer vision", "nlp", "reinforcement",

    # Dev & Tools
    "python", "rust", "golang", "typescript", "open source",
    "api", "framework", "library", "cli", "tool", "github",
    "docker", "kubernetes", "fastapi", "database",

    # Tech News
    "startup", "research", "paper", "released", "launched",
    "security", "vulnerability", "breach", "programming",
]

BLOCKED_TOPICS = [
    "hiring", "job posting", "salary", "cryptocurrency",
    "bitcoin", "nft", "forex", "trading signals",
    "weight loss", "casino", "betting",
]


def is_relevant(title: str, content: str = "") -> bool:
    text = (title + " " + content[:300]).lower()

    # Block irrelevant content first
    if any(b in text for b in BLOCKED_TOPICS):
        return False

    # Must match at least one allowed topic
    return any(t in text for t in ALLOWED_TOPICS)