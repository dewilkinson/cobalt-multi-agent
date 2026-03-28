# Cobalt Multiagent - High-fidelity financial analysis platform
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>
# License: PolyForm Noncommercial 1.0.0

# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import functools
import inspect
import logging
import time
from typing import Any, Callable, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def log_io(func: Callable) -> Callable:
    """
    A decorator that logs the input parameters and output of a tool function.

    Args:
        func: The tool function to be decorated

    Returns:
        The wrapped function with input/output logging
    """

    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            func_name = func.__name__
            params = ", ".join(
                [*(str(arg) for arg in args), *(f"{k}={v}" for k, v in kwargs.items())]
            )
            logger.debug(f"[ENTRY] Tool {func_name} invoked with parameters: {params}")

            try:
                result = await func(*args, **kwargs)
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                logger.debug(f"[EXIT] Tool {func_name} returned successfully in {duration_ms:.2f}ms. Result (truncated): {str(result)[:500]}")
                logger.debug(f"Tool {func_name} executed in {duration_ms:.2f}ms.")
                return result
            except Exception as e:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                logger.error(f"[ERROR] Tool {func_name} failed after {duration_ms:.2f}ms with error: {str(e)}", exc_info=True)
                raise
        return async_wrapper
    else:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            # Log input parameters
            func_name = func.__name__
            params = ", ".join(
                [*(str(arg) for arg in args), *(f"{k}={v}" for k, v in kwargs.items())]
            )
            logger.debug(f"[ENTRY] Tool {func_name} invoked with parameters: {params}")

            # Execute the function
            try:
                result = func(*args, **kwargs)
                
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                # Log the output
                logger.debug(f"[EXIT] Tool {func_name} returned successfully in {duration_ms:.2f}ms. Result (truncated): {str(result)[:500]}")
                logger.debug(f"Tool {func_name} executed in {duration_ms:.2f}ms.")
                return result
            except Exception as e:
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                logger.error(f"[ERROR] Tool {func_name} failed after {duration_ms:.2f}ms with error: {str(e)}", exc_info=True)
                raise

        return wrapper


class LoggedToolMixin:
    """A mixin class that adds logging functionality to any tool."""

    def _log_operation(self, method_name: str, *args: Any, **kwargs: Any) -> None:
        """Helper method to log tool operations."""
        tool_name = self.__class__.__name__.replace("Logged", "")
        params = ", ".join(
            [*(str(arg) for arg in args), *(f"{k}={v}" for k, v in kwargs.items())]
        )
        logger.debug(f"[ENTRY] Tool {tool_name}.{method_name} invoked with parameters: {params}")

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Override _run method to add logging."""
        self._log_operation("_run", *args, **kwargs)
        start_time = time.time()
        try:
            result = super()._run(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(
                f"[EXIT] Tool {self.__class__.__name__.replace('Logged', '')} returned successfully in {duration_ms:.2f}ms. Result (truncated): {str(result)[:500]}"
            )
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"[ERROR] Tool {self.__class__.__name__.replace('Logged', '')} failed after {duration_ms:.2f}ms with error: {str(e)}", exc_info=True)
            raise


def create_logged_tool(base_tool_class: Type[T]) -> Type[T]:
    """
    Factory function to create a logged version of any tool class.

    Args:
        base_tool_class: The original tool class to be enhanced with logging

    Returns:
        A new class that inherits from both LoggedToolMixin and the base tool class
    """

    class LoggedTool(LoggedToolMixin, base_tool_class):
        pass

    # Set a more descriptive name for the class
    LoggedTool.__name__ = f"Logged{base_tool_class.__name__}"
    return LoggedTool
