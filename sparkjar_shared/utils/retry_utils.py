"""Shared retry utilities with exponential backoff."""
import asyncio
import random
from typing import TypeVar, Callable, Optional, Union
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RetryConfig:
    """Configuration for retry behavior."""
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        exponential_base: float = 2.0,
        max_delay: float = 60.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.exponential_base = exponential_base
        self.max_delay = max_delay
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (0-indexed)."""
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            # Add random jitter between 0-25% of delay
            delay = delay * (1 + random.random() * 0.25)
        
        return delay

async def retry_with_exponential_backoff(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    retry_on: Optional[tuple] = None,
    **kwargs
) -> T:
    """
    Execute a function with exponential backoff retry logic.
    
    Args:
        func: The async function to execute
        config: Retry configuration (uses defaults if not provided)
        retry_on: Tuple of exception types to retry on (default: all exceptions)
        *args, **kwargs: Arguments to pass to the function
    
    Returns:
        The result of the function call
    
    Raises:
        The last exception if all retries are exhausted
    """
    config = config or RetryConfig()
    retry_on = retry_on or (Exception,)
    
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except retry_on as e:
            last_exception = e
            
            if attempt < config.max_retries:
                delay = config.get_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {str(e)}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {config.max_retries + 1} attempts failed. Last error: {str(e)}"
                )
    
    raise last_exception

def retry_async(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
    retry_on: Optional[tuple] = None,
):
    """
    Decorator for async functions to add retry logic with exponential backoff.
    
    Usage:
        @retry_async(max_retries=3, initial_delay=1.0)
        async def my_api_call():
            ...
    """
    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        exponential_base=exponential_base,
        max_delay=max_delay,
    )
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_exponential_backoff(
                func, *args, config=config, retry_on=retry_on, **kwargs
            )
        return wrapper
    return decorator

class CircuitBreaker:
    """
    Simple circuit breaker to prevent excessive API calls when service is down.
    """
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_attempts: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_attempts = half_open_attempts
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open
        self.half_open_count = 0
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
                self.half_open_count = 0
            else:
                raise Exception("Circuit breaker is open - service unavailable")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try again."""
        if self.last_failure_time is None:
            return False
        
        return (asyncio.get_event_loop().time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        if self.state == "half-open":
            self.half_open_count += 1
            if self.half_open_count >= self.half_open_attempts:
                self.state = "closed"
                self.failure_count = 0
                logger.info("Circuit breaker closed - service recovered")
        else:
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = asyncio.get_event_loop().time()
        
        if self.state == "half-open":
            self.state = "open"
            logger.warning("Circuit breaker opened again - recovery failed")
        elif self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.error(f"Circuit breaker opened after {self.failure_count} failures")