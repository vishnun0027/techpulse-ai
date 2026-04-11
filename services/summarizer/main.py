import time
from groq import Groq
from loguru import logger
from tenacity import retry, wait_exponential, stop_after_attempt
from shared.config import settings
from shared.redis_client import read_from_stream, delete_from_stream
from shared.db import save_article

client = Groq(api_key=settings.groq_api_key)

SYSTEM = """You are a senior tech analyst writing for developers.
Rules:
- Write exactly 2-3 sentences
- Explain WHY it matters to developers or AI engineers
- Be direct, no hype, no filler words
- End with one concrete takeaway"""

@retry(wait=wait_exponential(min=3, max=30), stop=stop_after_attempt(3))
def call_groq(title: str, content: str, source: str) -> str:
    r = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content":
             f"Title: {title}\nSource: {source}\nContent: {content[:1500]}\nSummarize:"}
        ],
        max_tokens=180,
        temperature=0.3,
    )
    return r.choices[0].message.content.strip()

def summarize():
    messages = read_from_stream(count=50)
    if not messages:
        logger.info("No messages in stream")
        return

    logger.info(f"Summarizing {len(messages)} articles...")
    for msg in messages:
        d = msg["data"]
        try:
            summary = call_groq(
                title=d.get("title", ""),
                content=d.get("content", ""),
                source=d.get("source", "")
            )
            save_article({
                "title":      d.get("title"),
                "source_url": d.get("source_url"),
                "source":     d.get("source"),
                "content":    d.get("content"),
                "summary":    summary,
                "score":      float(d.get("score", 1.0)),
                "topics":     ["tech"],
            })
            delete_from_stream(msg["id"])
            logger.success(f"Done: {d.get('title','')[:55]}")
            time.sleep(2)  # respect Groq free rate limit (30 req/min)
        except Exception as e:
            logger.error(f"Summarize failed: {e}")

if __name__ == "__main__":
    summarize()