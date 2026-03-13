"""Lightweight realtime ingestion sketch (simulation).

This script demonstrates a minimal producer/consumer pattern that simulates
real-time telemetry events and a consumer that receives events from an
asyncio.Queue and writes them into a rolling JSONL file. This is a sketch
intended as a starting point for a real Kafka/Redis consumer.

Usage:
    python scripts/realtime_simulator.py --mode producer  # run producer
    python scripts/realtime_simulator.py --mode consumer  # run consumer

The producer periodically puts JSON events onto an in-memory queue (only
when run as a combined demo). The consumer shows how you would parse events
and append to a JSONL file or forward to the ingestion pipeline.

Note: This is intentionally dependency-light and runs without Kafka/Redis.
"""

import argparse
import asyncio
import json
import random
import string
import time
from pathlib import Path

# Prefer the canonical data directory from app.config when available.
try:
    from app.config import DATA_DIR as CONFIG_DATA_DIR
except Exception:
    CONFIG_DATA_DIR = None

if CONFIG_DATA_DIR is not None:
    OUTPUT_DIR = Path(CONFIG_DATA_DIR)
else:
    OUTPUT_DIR = Path("data_generator/output")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STREAM_FILE = OUTPUT_DIR / "realtime_stream.jsonl"


def random_event():
    user_id = f"user_{random.randint(1,5)}"
    prompt = "".join(random.choices(string.ascii_lowercase + " ", k=random.randint(20, 200)))
    model = random.choice(["claude-v1", "claude-instant", "gpt-4"])
    total_tokens = max(1, int(len(prompt) / 4 + random.gauss(0, 5)))
    return {
        "user_id": user_id,
        "prompt": prompt,
        "prompt_length": len(prompt),
        "model": model,
        "total_tokens": total_tokens,
        "ts": int(time.time() * 1000),
    }


async def producer(queue: asyncio.Queue, rate: float = 0.2):
    """Produce events at roughly `rate` events/second."""
    while True:
        ev = random_event()
        await queue.put(ev)
        await asyncio.sleep(1.0 / max(rate, 0.01))


async def consumer(queue: asyncio.Queue, flush_every: int = 10):
    """Consume events and append to a JSONL file in `data_generator/output`."""
    buffer = []
    while True:
        ev = await queue.get()
        buffer.append(ev)
        if len(buffer) >= flush_every:
            with STREAM_FILE.open("a", encoding="utf-8") as f:
                for e in buffer:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            print(f"Wrote {len(buffer)} events to {STREAM_FILE}")
            buffer.clear()
        queue.task_done()


async def demo(run_time: int = 10):
    q = asyncio.Queue()
    prod = asyncio.create_task(producer(q, rate=5.0))
    cons = asyncio.create_task(consumer(q, flush_every=5))
    await asyncio.sleep(run_time)
    prod.cancel()
    await q.join()
    cons.cancel()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["producer", "consumer", "demo"], default="demo")
    parser.add_argument("--run-time", type=int, default=10, help="demo duration in seconds")
    args = parser.parse_args()

    if args.mode == "demo":
        asyncio.run(demo(run_time=args.run_time))
    elif args.mode == "producer":
        q = asyncio.Queue()
        asyncio.run(producer(q, rate=1.0))
    elif args.mode == "consumer":
        q = asyncio.Queue()
        asyncio.run(consumer(q, flush_every=10))


if __name__ == "__main__":
    main()
