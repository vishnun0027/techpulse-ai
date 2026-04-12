import time
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from loguru import logger
from tenacity import retry, wait_exponential, stop_after_attempt
from shared.config import settings
from shared.redis_client import read_from_stream, delete_from_stream
from shared.db import save_article


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


# ── Groq Call With Retry ──────────────────────────────────────────────────────
@retry(wait=wait_exponential(min=3, max=30), stop=stop_after_attempt(3))
def call_groq(title: str, content: str, source: str) -> ArticleAnalysis:
    result = chain.invoke({
        "title":   title,
        "source":  source,
        "content": content[:1500]
    })
    return ArticleAnalysis(**result)


# ── Main Summarizer ───────────────────────────────────────────────────────────
def summarize():
    messages = read_from_stream(count=50)
    if not messages:
        logger.info("No messages in stream")
        return

    logger.info(f"Summarizing {len(messages)} articles...")

    for msg in messages:
        d = msg["data"]
        try:
            result = call_groq(
                title=d.get("title", ""),
                content=d.get("content", ""),
                source=d.get("source", "")
            )
            save_article({
                "title":      d.get("title"),
                "source_url": d.get("source_url"),
                "source":     d.get("source"),
                "content":    d.get("content"),
                "summary":    result.summary,
                "score":      result.score,
                "topics":     result.topics,
            })
            delete_from_stream(msg["id"])
            logger.success(
                f"[score={result.score}] [{result.topics}] "
                f"{d.get('title', '')[:50]}"
            )
            time.sleep(2)

        except Exception as e:
            logger.error(f"Summarize failed: {e}")


if __name__ == "__main__":
    summarize()