"""简洁终端日志。"""


def info(tag, message):
    print(f"[{tag}] {message}", flush=True)


def step(tag, message):
    """关键步骤（带箭头，便于追踪流程）。"""
    print(f"[{tag}] -> {message}", flush=True)


def warn(tag, message):
    print(f"[{tag}] WARN {message}", flush=True)


def error(tag, message):
    print(f"[{tag}] ERROR {message}", flush=True)