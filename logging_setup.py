"""
███╗   ██╗ ██████╗ ██████╗ ███████╗███████╗███████╗███████╗██╗  ██╗     ██████╗  ██████╗ ████████╗
████╗  ██║██╔═══██╗██╔══██╗██╔════╝██╔════╝██╔════╝██╔════╝██║ ██╔╝     ██╔══██╗██╔═══██╗╚══██╔══╝
██╔██╗ ██║██║   ██║██║  ██║█████╗  ███████╗█████╗  █████╗  █████╔╝█████╗██████╔╝██║   ██║   ██║
██║╚██╗██║██║   ██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██╔══╝  ██╔═██╗╚════╝██╔══██╗██║   ██║   ██║
██║ ╚████║╚██████╔╝██████╔╝███████╗███████║███████╗███████╗██║  ██╗     ██████╔╝╚██████╔╝   ██║
╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝     ╚═════╝  ╚═════╝    ╚═╝

"""
import sys
import inspect
import logging
from pathlib import Path
from datetime import date

from loguru import logger

default_format: str = (
    "<g>{time:MM-DD HH:mm:ss}</g> "
    "[<lvl>{level}</lvl>] "
    "<c><u>{name}</u></c> | "
    "<lvl>{message}</lvl>"
)

file_format: str = (
    "{time:MM-DD HH:mm:ss} [{level}] {name} | {message}\n{exception}"
)


class LoguruHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging():
    """初始化 loguru 日志系统"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    latest = logs_dir / "latest.log"

    # 归档上次的 latest.log
    if latest.exists():
        today = date.today().isoformat()
        n = 1
        while (logs_dir / f"{today}_{n}.log").exists():
            n += 1
        latest.rename(logs_dir / f"{today}_{n}.log")

    # 只保留最近 10 个归档
    archives = sorted(
        [f for f in logs_dir.iterdir() if f.name != "latest.log"],
        key=lambda f: f.stat().st_mtime
    )
    for old in archives[:-10]:
        old.unlink()

    logger.remove()

    logger.add(
        sys.stdout,
        level="INFO",
        diagnose=False,
        format=default_format,
    )

    logger.add(
        str(latest),
        level="DEBUG",
        diagnose=False,
        format=file_format,
        encoding="utf-8",
    )

    logging.basicConfig(handlers=[LoguruHandler()], level=0, force=True)

    # 屏蔽 apscheduler 的 INFO 日志（添加/启动 job 的噪音）
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
