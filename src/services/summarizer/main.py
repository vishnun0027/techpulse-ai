import asyncio
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from loguru import logger
from tenacity import AsyncRetrying, wait_exponential, stop_after_attempt
from shared.config import settings
from shared.redis_client import ensure_group_exists, read_from_group, acknowledge_message
from shared.db import save_article, log_telemetry, get_filter_config


# ── Structured Output Schema ──────────────────────────────────────────────────
class ArticleAnalysis(BaseModel):
    score:   float     = Field(..., ge=0.0, le=5.0,
                               description="Relevance score 0.0 to 5.0")
    summary: str       = Field(...,
                               description="2-3 sentence summary for developers")
    topics:  list[str] = Field(...,
                               description="Topic tags like AI, LLM, Python")


# ── LangChain Setup ───────────────────────────────────────────────────────────
llm = ChatGroq(
    api_key=settings.groq_api_key,
    model=settings.groq_model,
    temperature=0.3,
    max_tokens=220,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a senior AI/ML engineer curating a tech digest.
Analyze the article and return valid JSON only:
{{
  "score": <float 0.0-5.0>,
  "summary": "<2-3 sentences why it matters to developers>",
  "topics": ["<tag1>", "<tag2>"]
}}

Score criteria:
- Relevance to AI/ML/LLM/dev tools (0-2 pts)
- Technical depth for developers (0-1.5 pts)
- Novelty and importance (0-1 pt)
- Source credibility (0-0.5 pts)"""),
    ("human", "Title: {title}\nSource: {source}\nContent: {content}")
])

parser = JsonOutputParser(pydantic_object=ArticleAnalysis)
chain  = prompt | llm | parser


# ── Groq Call With Async Retry ────────────────────────────────────────────────
async def call_groq_async(title: str, content: str, source: str) -> ArticleAnalysis:
    async for attempt in AsyncRetrying(
        wait=wait_exponential(min=10, max=60), 
        stop=stop_after_attempt(3)
    ):
        with attempt:
            result = await chain.ainvoke({
                "title":   title,
                "source":  source,
                "content": content[:1500]
            })
            return ArticleAnalysis(**result)


# ── Main Summarizer ───────────────────────────────────────────────────────────
GROUP_NAME    = "summarizer-group"
CONSUMER_NAME = "worker-1"

async def process_message(msg: dict, semaphore: asyncio.Semaphore) -> bool:
    """Process a single message with rate limiting. Returns success."""
    async with semaphore:
        d = msg["data"]
        msg_id = msg["id"]
        try:
            result = await call_groq_async(
                title=d.get("title", ""),
                content=d.get("content", ""),
                source=d.get("source", "")
            )

            # Apply Topic Boost
            final_score = result.score
            try:
                config = get_filter_config()
                priority = [t.lower() for t in config.get("priority", [])]
                if any(t.lower() in priority for t in result.topics):
                    final_score = min(5.0, final_score + 1.5)
                    logger.info(f"🚀 Priority Boost applied to {d.get('title')[:30]}... (+1.5)")
            except Exception as e:
                logger.warning(f"Failed to apply priority boost: {e}")

            # Save to database
            success = save_article({
                "title":      d.get("title"),
                "source_url": d.get("source_url"),
                "source":     d.get("source"),
                "content":    d.get("content"),
                "summary":    result.summary,
                "score":      final_score,
                "topics":     result.topics,
            })

            if success:
                acknowledge_message(GROUP_NAME, msg_id)
                logger.success(
                    f"[score={result.score}] [{result.topics}] "
                    f"{d.get('title', '')[:50]}"
                )
            else:
                logger.error(f"Failed to save article {msg_id}")

            # Rate limit: ~20 RPM = 3s between requests (must be before return)
            await asyncio.sleep(3)
            return bool(success)

        except Exception as e:
            logger.error(f"Summarize failed for message {msg_id}: {e}")
            await asyncio.sleep(3)  # still wait on failure to avoid error storms
            return False

async def summarize():
    ensure_group_exists(GROUP_NAME)
    
    # Increase count to 60 to drain the backlog faster
    messages = read_from_group(GROUP_NAME, CONSUMER_NAME, count=60)
    if not messages:
        logger.info("No new messages in stream")
        return

    logger.info(f"Summarizing {len(messages)} articles (Async)...")
    
    # Use a semaphore to process one at a time but with async efficiency
    # and controlled timing.
    semaphore = asyncio.Semaphore(1)
    tasks = [process_message(m, semaphore) for m in messages]
    results = await asyncio.gather(*tasks)
    
    # Record telemetry
    success_count = sum(1 for r in results if r)
    log_telemetry("summarizer", {
        "read": len(messages),
        "summarized": success_count,
        "failed": len(messages) - success_count
    })


if __name__ == "__main__":
    asyncio.run(summarize())