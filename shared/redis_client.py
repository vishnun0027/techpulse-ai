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

def is_duplicate(url: str) -> bool:
    fp  = hashlib.md5(url.encode()).hexdigest()
    key = f"seen:{fp}"
    if redis.exists(key):
        return True
    redis.setex(key, DEDUP_TTL, 1)
    return False

def push_to_stream(data: dict) -> str:
    # Build raw Redis XADD command
    # Format: XADD stream:raw MAXLEN ~ 500 * field1 val1 field2 val2 ...
    cmd = ["XADD", STREAM_RAW, "MAXLEN", "~", "500", "*"]
    for k, v in data.items():
        cmd.append(str(k))
        cmd.append(str(v))
    return redis.execute(command=cmd)

def read_from_stream(count: int = 50) -> list:
    # XRANGE stream:raw - + COUNT 50
    result = redis.execute(command=["XRANGE", STREAM_RAW, "-", "+", "COUNT", str(count)])
    if not result:
        return []
    messages = []
    for entry in result:
        msg_id = entry[0]
        # fields come as flat [k, v, k, v, ...]
        raw    = entry[1]
        fields = {raw[i]: raw[i+1] for i in range(0, len(raw), 2)}
        messages.append({"id": msg_id, "data": fields})
    return messages

def delete_from_stream(msg_id: str):
    redis.execute(command=["XDEL", STREAM_RAW, msg_id])