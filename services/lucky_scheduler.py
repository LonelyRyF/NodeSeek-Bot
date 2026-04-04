"""
███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

"""
import asyncio
from datetime import datetime

from loguru import logger

from core.lucky_engine import LuckyEngine


class LuckyScheduler:

    def __init__(self, engine: LuckyEngine, store):
        self.engine = engine
        self.store = store
        self._running: set = set()

    async def tick(self):
        now_ms = int(datetime.now().timestamp() * 1000)
        pending = self.store.get_pending_lucky_tasks()

        for task in pending:
            if task.id in self._running:
                continue
            if now_ms >= task.time:
                self._running.add(task.id)
                asyncio.create_task(self._run(task))

    async def _run(self, task):
        try:
            await self.engine.run_draw(task)
        finally:
            self._running.discard(task.id)
