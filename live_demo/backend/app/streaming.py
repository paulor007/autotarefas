"""Geracao dos eventos SSE do stdout ao vivo (Live-1.3).

Consome a fila do Job e emite Server-Sent Events: uma linha por evento `data:`,
heartbeats para manter a conexao viva atras de proxies, e um evento final `done`
(ou `timeout`) com o resultado consolidado em JSON.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from .jobs import Job

_HEARTBEAT_S = 15.0


def _final_event(job: Job) -> str:
    payload = json.dumps(job.result.as_dict() if job.result else {}, ensure_ascii=False)
    event = "timeout" if job.status == "timeout" else "done"
    return f"event: {event}\ndata: {payload}\n\n"


async def sse_events(job: Job) -> AsyncIterator[str]:
    """Stream SSE: linhas de stdout + heartbeats + evento final."""
    while True:
        if job.status != "running" and job.queue.empty():
            yield _final_event(job)
            return
        try:
            item = await asyncio.wait_for(job.queue.get(), timeout=_HEARTBEAT_S)
        except TimeoutError:
            if job.status != "running" and job.queue.empty():
                yield _final_event(job)
                return
            yield ": keepalive\n\n"
            continue
        if item is None:
            yield _final_event(job)
            return
        yield f"data: {item}\n\n"
