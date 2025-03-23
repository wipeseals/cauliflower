import time


# ログ制御用
class LogLevel:
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3
    TRACE = 4

    @classmethod
    def to_str(cls, level: int) -> str:
        if level == cls.ERROR:
            return "ERROR"
        elif level == cls.WARN:
            return "WARN"
        elif level == cls.INFO:
            return "INFO"
        elif level == cls.DEBUG:
            return "DEBUG"
        elif level == cls.TRACE:
            return "TRACE"
        else:
            return "UNKNOWN"


# ログレベルの設定 (default)
CURRENT_LOG_LEVEL = LogLevel.TRACE


def log(level: int, msg: str) -> None:
    if level <= CURRENT_LOG_LEVEL:
        print(f"[{time.ticks_us()}][{LogLevel.to_str(level)}]{msg}")
    else:
        pass


def error(msg: str) -> None:
    log(LogLevel.ERROR, msg)


def warn(msg: str) -> None:
    log(LogLevel.WARN, msg)


def info(msg: str) -> None:
    log(LogLevel.INFO, msg)


def debug(msg: str) -> None:
    log(LogLevel.DEBUG, msg)


def trace(msg: str) -> None:
    log(LogLevel.TRACE, msg)
