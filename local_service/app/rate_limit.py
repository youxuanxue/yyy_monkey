import time
from dataclasses import dataclass

from .db import get_conn


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_epoch: int


def check_and_increment_per_minute(key: str, limit_per_minute: int) -> RateLimitResult:
    """
    简单的按分钟计数器：
    - window_start_epoch: 当前分钟的起始 epoch 秒
    - count: 当前分钟内计数
    """
    now = int(time.time())
    window_start = now - (now % 60)
    reset_epoch = window_start + 60

    conn = get_conn()
    try:
        row = conn.execute("SELECT window_start_epoch, count FROM rate_limits WHERE key = ?", (key,)).fetchone()
        if row is None:
            count = 1
            conn.execute(
                "INSERT INTO rate_limits(key, window_start_epoch, count) VALUES(?,?,?)",
                (key, window_start, count),
            )
            conn.commit()
            return RateLimitResult(True, max(0, limit_per_minute - count), reset_epoch)

        if int(row["window_start_epoch"]) != window_start:
            count = 1
            conn.execute(
                "UPDATE rate_limits SET window_start_epoch=?, count=? WHERE key=?",
                (window_start, count, key),
            )
            conn.commit()
            return RateLimitResult(True, max(0, limit_per_minute - count), reset_epoch)

        count = int(row["count"])
        if count >= limit_per_minute:
            return RateLimitResult(False, 0, reset_epoch)

        count += 1
        conn.execute("UPDATE rate_limits SET count=? WHERE key=?", (count, key))
        conn.commit()
        return RateLimitResult(True, max(0, limit_per_minute - count), reset_epoch)
    finally:
        conn.close()


