import asyncio
import time
from shared.redis_client import push_to_stream, ensure_group_exists
from services.summarizer.main import summarize
from services.delivery.main import deliver
from loguru import logger


async def test_e2e():
    logger.info("Starting E2E Test...")
    ensure_group_exists("summarizer-group")

    # 1. Inject a dummy article directly into the stream

    test_title = f"Test AI Breakthrough {int(time.time())}"
    dummy_article = {
        "title": test_title,
        "source_url": f"https://example.com/test-{int(time.time())}",
        "source": "E2E-Test-Source",
        "content": "This is a test article about a new AI breakthrough in quantum computing. It is very technical and relevant to developers.",
    }

    logger.info(f"Step 1: Pushing dummy article: {test_title}")
    push_to_stream(dummy_article)

    # 2. Run the async summarizer
    logger.info("Step 2: Running Summarizer...")
    await summarize()

    # 3. Run the delivery
    logger.info("Step 3: Running Delivery...")
    deliver()

    logger.info("E2E Test Complete.")


if __name__ == "__main__":
    asyncio.run(test_e2e())
