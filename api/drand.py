# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

import asyncio

from loguru import logger
from curl_cffi import requests as cffi_requests

DRAND_BASE = (
    "https://api.drand.sh"
    "/8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce"
)
DRAND_GENESIS = 1595431050  # 链的创世时间（秒）
DRAND_PERIOD = 30           # 每轮间隔（秒）


def _timestamp_to_round(timestamp_ms: int) -> int:
    return int((timestamp_ms / 1000 - DRAND_GENESIS) / DRAND_PERIOD)


async def fetch_randomness(timestamp_ms: int) -> str:
    """获取指定时间戳对应的 Drand 随机数（hex string）"""
    round_num = _timestamp_to_round(timestamp_ms)
    url = f"{DRAND_BASE}/public/{round_num}"

    def _fetch() -> str:
        session = cffi_requests.Session()
        resp = session.get(url, impersonate='chrome142', timeout=30)
        resp.raise_for_status()
        return resp.json()['randomness']

    loop = asyncio.get_event_loop()
    randomness = await loop.run_in_executor(None, _fetch)
    logger.debug(f"Drand round {round_num} randomness: {randomness[:16]}...")
    return randomness
