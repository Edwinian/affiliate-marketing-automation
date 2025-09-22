import time
import random
from functools import wraps
from typing import Callable, Any, Optional


def get_with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    retry_on_empty: bool = True,
    retry_on_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorator for API calls with exponential backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        retry_on_empty: Whether to retry when the function returns empty result (None, [], '')
        retry_on_exceptions: Tuple of exception types to catch and retry on
        logger: Logger instance for logging retry attempts

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            last_exception = None

            while attempt < max_retries:
                try:
                    result = func(*args, **kwargs)

                    # Check for empty results if retry_on_empty is True
                    if retry_on_empty:
                        if result is None or result == [] or result == "":
                            raise ValueError(f"Empty result from {func.__name__}")

                    # Success! Return the result
                    return result

                except tuple(retry_on_exceptions) as e:
                    last_exception = e
                    attempt += 1

                    if attempt >= max_retries:
                        # Max retries reached, re-raise the last exception
                        print(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )
                        raise last_exception

                    # Calculate exponential backoff delay with jitter
                    delay = min(
                        initial_delay * (2 ** (attempt - 1)) + random.uniform(0, 1),
                        max_delay,
                    )

                    # Log retry attempt
                    print(
                        f"{func.__name__} attempt {attempt}/{max_retries} failed: {e}, "
                        f"retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)

            # This line should never be reached, but just in case
            raise RuntimeError(f"{func.__name__} exhausted all retries")

        return wrapper

    return decorator
