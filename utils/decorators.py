import time
import functools
from typing import Callable

from utils.logger import logger


def timing_decorator(
    func: Callable = None, *, log_args: bool = True, threshold_ms: float = 0
) -> Callable:
    """
    测量函数执行时间的装饰器，支持配置

    Args:
        func: 要测量的函数
        log_args: 是否记录函数参数
        threshold_ms: 只记录执行时间超过此阈值的调用（毫秒）

    用法:
    @timing_decorator
    def normal_function(): pass

    @timing_decorator(log_args=False)
    def sensitive_function(): pass

    @timing_decorator(threshold_ms=100)
    def slow_function(): pass
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = fn(*args, **kwargs)
            end_time = time.perf_counter()

            execution_time = (end_time - start_time) * 1000

            # 只记录超过阈值的调用
            if execution_time >= threshold_ms:
                func_name = fn.__name__

                # 根据配置决定是否记录参数
                if log_args:
                    args_repr = [repr(a) for a in args]
                    kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                    signature = ", ".join(args_repr + kwargs_repr)
                    msg = f"Function: {func_name}({signature})"
                else:
                    msg = f"Function: {func_name}"

                logger.info(f"{msg} took {execution_time:.2f} ms to execute")

            return result

        return wrapper

    if func is None:
        return decorator
    return decorator(func)
