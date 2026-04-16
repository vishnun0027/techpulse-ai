import argparse
import sys
from loguru import logger
from shared.redis_client import redis, STREAM_RAW
from shared.db import supabase


def clear_redis():
    """Clear all Redis-based storage (stream and deduplication keys)."""
    logger.info("🧹 Clearing Redis...")
    
    # 1. Clear the stream
    redis.delete(STREAM_RAW)
    logger.debug(f"Deleted stream: {STREAM_RAW}")
    
    # 2. Destroy the consumer group
    try:
        redis.execute(command=["XGROUP", "DESTROY", STREAM_RAW, "summarizer-group"])
        logger.debug("Destroyed consumer group: summarizer-group")
    except Exception:
        pass  # Group might not exist if it was never created
    
    # 3. Clear deduplication keys (seen and title)
    keys = redis.keys("seen:*") + redis.keys("title:*")
    if keys:
        for key in keys:
            redis.delete(key)
        logger.debug(f"Deleted {len(keys)} deduplication keys.")
    
    logger.success("Redis cleared logic applied.")


def clear_db():
    """Clear all rows from the Supabase articles table."""
    logger.info("🗄️ Clearing Database...")
    try:
        # Standard Supabase hack to delete all rows: filter for all IDs
        # (Assuming ID is not negative)
        res = supabase.table("articles").delete().neq("title", "___NON_EXISTENT_TITLE___").execute()
        logger.success(f"Database cleared. Deleted records: {len(res.data or [])}")
    except Exception as e:
        logger.error(f"Database clear failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="TechPulse AI Maintenance Control")
    parser.add_argument("action", choices=["reset"], help="Action to perform")
    parser.add_argument("--confirm", action="store_true", help="Confirm destructive action")
    
    args = parser.parse_args()
    
    if args.action == "reset":
        if not args.confirm:
            logger.error("🛑 DANGER: This action will delete all data. Run with --confirm to proceed.")
            sys.exit(1)
            
        logger.warning("⚠️ PROCEEDING WITH FULL STORAGE RESET...")
        clear_redis()
        clear_db()
        logger.success("✨ Master Reset Complete. System is now in a clean state.")


if __name__ == "__main__":
    main()
