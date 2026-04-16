import hashlib
import json
from upstash_redis import Redis
from shared.config import settings

redis = Redis(
    url=settings.upstash_redis_rest_url,
    token=settings.upstash_redis_rest_token
)

STREAM_RAW = "stream:raw"
DEDUP_TTL  = settings.dedup_ttl_days * 86400

def check_seen(url: str) -> bool:
    """True if the URL has already been processed recently."""
    fp  = hashlib.md5(url.encode()).hexdigest()
    return bool(redis.exists(f"seen:{fp}"))

def mark_seen(url: str):
    """Mark URL as processed with a TTL."""
    fp  = hashlib.md5(url.encode()).hexdigest()
    redis.setex(f"seen:{fp}", DEDUP_TTL, 1)

def check_title_seen(title: str) -> bool:
    """True if a similar title has already been processed."""
    # Simplified: normalize title and hash it
    slug = "".join(e for e in title.lower() if e.isalnum())[:100]
    return bool(redis.exists(f"title:{slug}"))

def mark_title_seen(title: str):
    """Mark a title as processed."""
    slug = "".join(e for e in title.lower() if e.isalnum())[:100]
    redis.setex(f"title:{slug}", DEDUP_TTL, 1)


def push_to_stream(data: dict) -> str:
    # Build raw Redis XADD command
    # Format: XADD stream:raw MAXLEN ~ 500 * field1 val1 field2 val2 ...
    cmd = ["XADD", STREAM_RAW, "MAXLEN", "~", "500", "*"]
    for k, v in data.items():
        cmd.append(str(k))
        cmd.append(str(v))
    return redis.execute(command=cmd)

def ensure_group_exists(group_name: str):
    """Ensure the consumer group exists for the stream."""
    try:
        # XGROUP CREATE stream:raw group_name $ MKSTREAM
        redis.execute(command=["XGROUP", "CREATE", STREAM_RAW, group_name, "$", "MKSTREAM"])
    except Exception as e:
        # If group already exists, Redis returns an error - we ignore it
        if "BUSYGROUP" not in str(e):
            raise e

def read_from_group(group_name: str, consumer_name: str, count: int = 10) -> list:
    """Read new messages from the group (or pending messages if any)."""
    # XREADGROUP GROUP group_name consumer_name COUNT count STREAMS stream:raw >
    # The '>' means 'buy and read new messages only'
    result = redis.execute(command=[
        "XREADGROUP", "GROUP", group_name, consumer_name,
        "COUNT", str(count), "STREAMS", STREAM_RAW, ">"
    ])
    
    if not result:
        return []
    
    # XREADGROUP returns [ [stream_name, [ [msg_id, [fields]] ] ] ]
    raw_messages = result[0][1]
    messages = []
    for entry in raw_messages:
        msg_id = entry[0]
        fields_list = entry[1]
        fields = {fields_list[i]: fields_list[i+1] for i in range(0, len(fields_list), 2)}
        messages.append({"id": msg_id, "data": fields})
    return messages

def acknowledge_message(group_name: str, msg_id: str):
    """Acknowledge message processing completion."""
    # XACK stream:raw group_name msg_id
    redis.execute(command=["XACK", STREAM_RAW, group_name, msg_id])

def delete_from_stream(msg_id: str):
    """Legacy: Delete from stream. Use acknowledge_message instead in groups."""
    redis.execute(command=["XDEL", STREAM_RAW, msg_id])