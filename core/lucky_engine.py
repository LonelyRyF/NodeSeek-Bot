# ███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
# ████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
# ██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
# ██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
# ██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
# ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

import asyncio
from datetime import datetime
from typing import List, Optional

from loguru import logger
from aiogram import Bot
from aiogram.enums import ParseMode

from api.forum import ForumAPI
from api.drand import fetch_randomness
from core.models import LuckyTask


# ========== 算法移植 ==========

def _u32(n: int) -> int:
    return n & 0xFFFFFFFF


def _s32(n: int) -> int:
    n = n & 0xFFFFFFFF
    return n - 0x100000000 if n >= 0x80000000 else n


def _shr(n: int, bits: int) -> int:
    """无符号右移 (>>> in JS)"""
    return (n & 0xFFFFFFFF) >> bits


def _imul(a: int, b: int) -> int:
    """Math.imul - 32位有符号整数乘法"""
    return _s32((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF))


def ns_hash(t: str) -> List[int]:
    n = 1779033703
    r = 3144134277
    i = 1013904242
    a = 2773480762

    for ch in t:
        e = ord(ch)
        n = r ^ _imul(n ^ e, 597399067)
        r = i ^ _imul(r ^ e, 2869860233)
        i = a ^ _imul(i ^ e, 951274213)
        a = n ^ _imul(a ^ e, 2716044179)

    n_old, r_old, i_old, a_old = n, r, i, a
    n = _imul(i_old ^ _shr(n_old, 18), 597399067)
    r = _imul(a_old ^ _shr(r_old, 22), 2869860233)
    i = _imul(n ^ _shr(i_old, 17), 951274213)
    a = _imul(r ^ _shr(a_old, 19), 2716044179)

    return [
        _u32(n ^ r ^ i ^ a),
        _u32(r ^ n),
        _u32(i ^ n),
        _u32(a ^ n),
    ]


def ns_prng(seed: List[int]):
    n = _u32(seed[0])
    r = _u32(seed[1])
    i = _u32(seed[2])
    a = _u32(seed[3])

    def _next() -> float:
        nonlocal n, r, i, a

        # var t = (n >>>= 0) + (r >>>= 0) | 0
        t = _s32(_u32(n) + _u32(r))

        # n = r ^ r >>> 9
        n_new = r ^ _shr(r, 9)

        # r = (i >>>= 0) + (i << 3) | 0
        i_u = _u32(i)
        r_new = _s32(i_u + _u32(i_u << 3))

        # i = (i = i << 21 | i >>> 11) + (t = t + (a = 1 + (a >>>= 0) | 0) | 0) | 0
        i_rot = _u32((i_u << 21) | _shr(i_u, 11))
        a_new = _s32(1 + _u32(a))
        t_new = _s32(t + a_new)
        i_new = _s32(i_rot + t_new)

        n, r, i, a = n_new, r_new, i_new, a_new

        # return (t >>> 0) / 4294967296
        return _u32(t_new) / 4294967296.0

    return _next


def calculate_winners(randomness: str, data_length: int) -> List[int]:
    hash_result = ns_hash(randomness)
    prng = ns_prng(hash_result)
    values = [(prng(), idx) for idx in range(data_length)]
    values.sort(key=lambda x: x[0])
    return [idx for _, idx in values]


# ========== 执行引擎 ==========

class LuckyEngine:

    def __init__(self, apis: dict, store, bot: Bot, admin_id: str):
        self.apis = apis  # {'nodeseek': ForumAPI, 'deepflood': ForumAPI, ...}
        self.store = store
        self.bot = bot
        self.admin_id = admin_id

    def _api_for(self, task: LuckyTask):
        return self.apis.get(task.platform, next(iter(self.apis.values())))

    async def run_draw(self, task: LuckyTask):
        api = self._api_for(task)
        base_url = api.BASE_URL
        logger.info(f"[Lucky] 开始执行抽奖: platform={task.platform} post={task.post}")
        try:
            loop = asyncio.get_event_loop()

            # 1. 获取楼层数据
            floor_resp = await loop.run_in_executor(
                None, api.get_floor_data, task.post, task.time
            )
            if not floor_resp.get('success'):
                raise RuntimeError(f"获取楼层数据失败: {floor_resp.get('message') or floor_resp.get('error')}")

            floors = floor_resp['data']

            # 2. 标记重复用户
            seen_members: set = set()
            for idx, f in enumerate(floors):
                floor_num = idx + 1
                if floor_num < task.start:
                    f['dup'] = False
                elif f['member_id'] in seen_members:
                    f['dup'] = True
                else:
                    f['dup'] = False
                    seen_members.add(f['member_id'])

            # 3. 获取 Drand 随机数
            randomness = await fetch_randomness(task.time)

            # 4. 计算中奖序列
            lucky_sequence = calculate_winners(randomness, len(floors))

            # 5. 筛选中奖者
            winners = []
            win_count = 0
            for floor_idx in lucky_sequence:
                if win_count >= task.count:
                    break
                floor = floors[floor_idx]
                floor_num = floor_idx + 1
                if floor_num < task.start:
                    continue
                if floor.get('dup') and not task.duplicate:
                    continue
                winners.append(floor)
                win_count += 1

            winners.sort(key=lambda f: f['floor_id'])

            # 6. 构建消息并发送
            title = task.title or f'帖子 {task.post}'
            msg = (
                f"[{title}]({base_url}/post-{task.post}-1)\n"
                f"[开奖链接]({base_url}/lucky?post={task.post}&time={task.time})\n\n"
            )
            for idx, w in enumerate(winners):
                msg += (
                    f"{idx + 1}. [{w['member_name']}]"
                    f"({base_url}/space/{w['member_id']}) "
                    f"({w['floor_id']} 楼)\n"
                )

            await self.bot.send_message(
                self.admin_id, msg,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )

            # 7. 更新任务状态
            self.store.update_lucky_task_status(
                task.id,
                status='completed',
                winners=[{'name': w['member_name'], 'floor': w['floor_id']} for w in winners],
                completed_at=datetime.now().isoformat()
            )
            logger.info(f"[Lucky] 抽奖完成: {task.id}, 中奖 {len(winners)} 人")

        except Exception as e:
            logger.error(f"[Lucky] 抽奖失败 {task.id}: {e}", exc_info=True)
            self.store.update_lucky_task_status(task.id, status='failed')
            await self.bot.send_message(
                self.admin_id,
                f"抽奖失败 (Post: {task.post}): {e}\n"
                f"URL: {base_url}/lucky?post={task.post}&time={task.time}"
            )
