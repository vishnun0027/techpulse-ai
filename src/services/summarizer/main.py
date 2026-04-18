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
    ("system", """You are a senior tech intelligence officer.
Analyze the article and return valid JSON only:
{{
  "score": <float 0.0-5.0>,
  "summary": "<2-3 sentences why it matters to the user>",
  "topics": ["<tag1>", "<tag2>"]
}}

Target Topics (for scoring relevance): {allowed_topics}

Score criteria:
- Relevance to the Target Topics (0-2.5 pts)
- Technical depth and insight (0-1.5 pts)
- Novelty and importance (0-1 pt)"""),
    ("human", "Title: {title}\nSource: {source}\nContent: {content}")
])

parser = JsonOutputParser(pydantic_object=ArticleAnalysis)
chain  = prompt | llm | parser


# ── Groq Call With Async Retry ────────────────────────────────────────────────
async def call_groq_async(title: str, content: str, source: str, allowed_topics: list) -> ArticleAnalysis:
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
GROUP_NAME    = "summarizer-group"
CONSUMER_NAME = "worker-1"

async def process_message(msg: dict, semaphore: asyncio.Semaphore) -> bool:
    """Process a single message with rate limiting. Returns success."""
    async with semaphore:
        d = msg["data"]
        msg_id = msg["id"]
        user_id = d.get("user_id")
        
        try:
            # Fetch config for filtering and boosting
            config = get_filter_config(user_id)
            
            # 1. Final Safety Check: Blocked Keywords
            blocked = [t.lower() for t in config.get("blocked", [])]
            text = (d.get("title", "") + " " + d.get("content", "")[:500]).lower()
            if any(b in text for b in blocked if b):
                logger.info(f"🚫 Blocked in Summarizer: {d.get('title')[:30]}...")
                acknowledge_message(GROUP_NAME, msg_id)
                return "blocked"

            # 2. Call LLM for analysis
            result = await call_groq_async(
                title=d.get("title", ""),
                content=d.get("content", ""),
                source=d.get("source", ""),
                allowed_topics=config.get("allowed", [])
            )

            # 3. Apply Topic Boost (Spec: +20% boost = +1.0)
            final_score = result.score
            priority = [t.lower() for t in config.get("priority", [])]
            if any(t.lower() in priority for t in result.topics):
                final_score = min(5.0, final_score + 1.0)
                logger.info(f"🚀 Priority Boost (+1.0) applied to {d.get('title')[:30]}...")

            # Save to database
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
                    f"[score={result.score}] [{result.topics}] "
                    f"{d.get('title', '')[:50]}"
                )
            else:
                logger.error(f"Failed to save article {msg_id}")

            # Rate limit: ~20 RPM = 3s between requests
            await asyncio.sleep(3)
            return float(final_score)

        except Exception as e:
            logger.error(f"Summarize failed for message {msg_id}: {e}")
            await asyncio.sleep(3)
            return None

async def summarize():
    ensure_group_exists(GROUP_NAME)
    
    # Read from group
    messages = read_from_group(GROUP_NAME, CONSUMER_NAME, count=60)
    if not messages:
        logger.info("No new messages in stream")
        return

    logger.info(f"Summarizing {len(messages)} articles (Async)...")
    
    semaphore = asyncio.Semaphore(1)
    tasks = [process_message(m, semaphore) for m in messages]
    results = await asyncio.gather(*tasks)
    
    # Record telemetry
    scores = [r for r in results if isinstance(r, float)]
    success_count = len(scores)
    
    avg_score   = round(sum(scores) / success_count, 2) if success_count > 0 else 0
    # noise_ratio = articles blocked or failed / total processed
    noise_ratio = round(((len(messages) - success_count) / len(messages) * 100), 1) if len(messages) > 0 else 0
    
    log_telemetry("summarizer", {
        "avg_score": avg_score,
        "noise_ratio": noise_ratio
    })


if __name__ == "__main__":
    asyncio.run(summarize())