import asyncio
from typing import List, Dict, Any, Optional, Union
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from loguru import logger
from tenacity import AsyncRetrying, wait_exponential, stop_after_attempt
from shared.config import settings
from shared.redis_client import ensure_group_exists, read_from_group, acknowledge_message
from shared.db import save_article, log_telemetry, get_filter_config
from shared.models import ArticleAnalysis


# Shared models are now used for structured output schema


# ── LangChain Setup ───────────────────────────────────────────────────────────

llm = ChatGroq(
    api_key=settings.groq_api_key,
    model=settings.groq_model,
    temperature=0.3,
    max_tokens=220,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a senior tech intelligence officer.
Analyze the article and return valid JSON only:
{{
  "score": <float 0.0-5.0>,
  "summary": "<2-3 sentences why it matters to the user>",
  "topics": ["<emoji> <Category>", "<tag1>", "<tag2>"]
}}

The FIRST topic in the list MUST be a concise category (e.g., '🛠️ Python', '🦀 Rust', '☁️ Cloud', '🧠 AI Research') based on your analysis.

Target Topics (for scoring relevance): {allowed_topics}

Score criteria:
- Relevance to the Target Topics (0-2.5 pts)
- Technical depth and insight (0-1.5 pts)
- Novelty and importance (0-1 pt)"""),
    ("human", "Title: {title}\nSource: {source}\nContent: {content}")
])

parser = JsonOutputParser(pydantic_object=ArticleAnalysis)
chain = prompt | llm | parser


# ── Groq Call With Async Retry ────────────────────────────────────────────────

async def call_groq_async(title: str, content: str, source: str, allowed_topics: List[str]) -> ArticleAnalysis:
    """
    Calls the Groq LLM to analyze an article with exponential backoff retries.
    
    Args:
        title: Article title.
        content: Article content snippet.
        source: Name of the news source.
        allowed_topics: User's configured interests for relevance scoring.
        
    Returns:
        ArticleAnalysis: Pydantic model with AI results.
    """
    allowed_str = ", ".join(allowed_topics) if allowed_topics else "General high-quality tech intelligence"
    
    async for attempt in AsyncRetrying(
        wait=wait_exponential(min=10, max=60), 
        stop=stop_after_attempt(3)
    ):
        with attempt:
            result = await chain.ainvoke({
                "title":          title,
                "source":         source,
                "content":        content[:1500],
                "allowed_topics": allowed_str
            })
            return ArticleAnalysis(**result)


# ── Main Summarizer ───────────────────────────────────────────────────────────

GROUP_NAME = "summarizer-group"
CONSUMER_NAME = "worker-1"


async def process_message(msg: Dict[str, Any], semaphore: asyncio.Semaphore) -> Union[float, str, None]:
    """
    Processes a single raw message from the Redis stream.
    
    1. Checks for blocked keywords.
    2. Sends to LLM for scoring and summarizing.
    3. Applies priority boosts for specific interest matches.
    4. Saves the resulting article to Supabase.
    
    Args:
        msg: Raw Redis message dictionary.
        semaphore: Async semaphore to control concurrency.
        
    Returns:
        Union[float, str, None]: Final score (float), 'blocked' status, or None on failure.
    """
    async with semaphore:
        d = msg["data"]
        msg_id = msg["id"]
        user_id = d.get("user_id")
        
        try:
            # 1. Fetch config for user-specific filtering
            config = get_filter_config(user_id)
            
            # 2. Safety Check: Filter against blocked keywords
            blocked = [t.lower() for t in config.get("blocked", [])]
            text = (d.get("title", "") + " " + d.get("content", "")[:500]).lower()
            if any(b in text for b in blocked if b):
                logger.info(f"🚫 Blocked in Summarizer: {d.get('title')[:30]}...")
                acknowledge_message(GROUP_NAME, msg_id)
                return "blocked"

            # 3. Request AI Analysis
            result = await call_groq_async(
                title=d.get("title", ""),
                content=d.get("content", ""),
                source=d.get("source", ""),
                allowed_topics=config.get("allowed", [])
            )

            # 4. Apply Interest Priority Boost (+20% or +1.0 point)
            final_score: float = result.score
            priority = [t.lower() for t in config.get("priority", [])]
            if any(t.lower() in priority for t in result.topics):
                final_score = min(5.0, final_score + 1.0)
                logger.info(f"🚀 Priority Boost (+1.0) applied to {d.get('title')[:30]}...")

            # 5. Persist to Supabase
            success = save_article({
                "user_id":    user_id,
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
                    f"[score={final_score:.1f}] [{', '.join(result.topics)}] "
                    f"{d.get('title', '')[:50]}"
                )
            else:
                logger.error(f"Failed to save article {msg_id} to DB.")

            # Rate limit compliance: ~20 RPM = 3s pause
            await asyncio.sleep(3)
            return float(final_score)

        except Exception as e:
            logger.error(f"Summarize failed for message {msg_id}: {e}")
            await asyncio.sleep(3)
            return None


async def summarize() -> None:
    """
    Main summarization entry point. Reads batches from Redis and handles async execution.
    """
    ensure_group_exists(GROUP_NAME)
    
    # Read articles from the raw stream group
    messages = read_from_group(GROUP_NAME, CONSUMER_NAME, count=60)
    if not messages:
        logger.info("No new messages in stream")
        return

    logger.info(f"Summarizing {len(messages)} articles (Async)...")
    
    # We use a semaphore of 1 (strictly serial) to avoid Groq rate limits while processing a batch
    semaphore = asyncio.Semaphore(1)
    tasks = [process_message(m, semaphore) for m in messages]
    results = await asyncio.gather(*tasks)
    
    # Telemetry preparation
    processed_scores = [r for r in results if isinstance(r, float)]
    success_count = len(processed_scores)
    
    avg_score = round(sum(processed_scores) / success_count, 2) if success_count > 0 else 0
    noise_ratio = round(((len(messages) - success_count) / len(messages) * 100), 1) if len(messages) > 0 else 0
    
    log_telemetry("summarizer", {
        "avg_score": avg_score,
        "noise_ratio": noise_ratio
    }, success=(success_count > 0))


if __name__ == "__main__":
    asyncio.run(summarize())