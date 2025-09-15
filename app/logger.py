import sys
from datetime import datetime
from pathlib import Path

from loguru import logger


def init_logger():
    log_path = Path(__file__).parent.parent / "logs"
    log_path.mkdir(exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_path / f"log_{date_str}.log"

    logger.remove()

    logger.add(
        sys.stdout, 
        level="INFO", 
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}"
    )

    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
        enqueue=True,
        backtrace=True,
        diagnose=True
    )
