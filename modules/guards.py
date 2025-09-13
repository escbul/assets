"""
Risk Controls and Guards Module for TRON SunSwap Automation Bot
Implements rate limiting, transaction size controls, and safety checks
"""

import time
import random
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict, deque
import threading

logger = logging.getLogger(__name__)

@dataclass
class TransactionLimits:
    """Transaction size limits for different operations"""
    max_trx: float
    max_usdt: float
    max_odt: float
    min_trx: float = 0.001
    min_usdt: float = 1.0
    min_odt: float = 1.0

@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""
    min_delay: float
    max_delay: float
    max_transactions_per_hour: int
    max_transactions_per_day: int

class RateLimiter:
    """Rate limiter with exponential backoff and jitter"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.transaction_times = deque()
        self.last_transaction_time = 0
        self.lock = threading.Lock()
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
    def can_proceed(self) -> bool:
        """Check if we can proceed with a new transaction"""
        with self.lock:
            now = time.time()
            
            # Check hourly limit
            hour_ago = now - 3600
            recent_transactions = [t for t in self.transaction_times if t > hour_ago]
            if len(recent_transactions) >= self.config.max_transactions_per_hour:
                logger.warning("Hourly transaction limit reached")
                return False
            
            # Check daily limit
            day_ago = now - 86400
            daily_transactions = [t for t in self.transaction_times if t > day_ago]
            if len(daily_transactions) >= self.config.max_transactions_per_day:
                logger.warning("Daily transaction limit reached")
                return False
            
            # Check minimum delay
            if now - self.last_transaction_time < self.config.min_delay:
                logger.debug("Minimum delay not met")
                return False
            
            return True
    
    def record_transaction(self):
        """Record a successful transaction"""
        with self.lock:
            now = time.time()
            self.transaction_times.append(now)
            self.last_transaction_time = now
            self.consecutive_failures = 0
            
            # Clean old transaction times
            day_ago = now - 86400
            while self.transaction_times and self.transaction_times[0] < day_ago:
                self.transaction_times.popleft()
    
    def record_failure(self):
        """Record a failed transaction"""
        with self.lock:
            self.consecutive_failures += 1
    
    def get_delay(self) -> float:
        """Get delay before next transaction with jitter"""
        base_delay = random.uniform(
            self.config.min_delay, 
            self.config.max_delay
        )
        
        # Add exponential backoff for consecutive failures
        if self.consecutive_failures > 0:
            backoff_multiplier = min(2 ** self.consecutive_failures, 32)
            base_delay *= backoff_multiplier
        
        # Add jitter to avoid thundering herd
        jitter = random.uniform(0.8, 1.2)
        return base_delay * jitter
    
    def wait_if_needed(self):
        """Wait if necessary before proceeding"""
        if not self.can_proceed():
            delay = self.get_delay()
            logger.info(f"Rate limiting: waiting {delay:.2f} seconds")
            time.sleep(delay)

class TransactionValidator:
    """Validates transactions against risk controls"""
    
    def __init__(self, limits: TransactionLimits):
        self.limits = limits
        self.daily_volume = defaultdict(float)
        self.daily_volume_lock = threading.Lock()
    
    def validate_transaction_size(self, operation: str, amounts: Dict[str, float]) -> bool:
        """Validate transaction size against limits"""
        try:
            # Check TRX amount
            if 'trx' in amounts:
                trx_amount = amounts['trx']
                if trx_amount < self.limits.min_trx:
                    logger.warning(f"TRX amount {trx_amount} below minimum {self.limits.min_trx}")
                    return False
                if trx_amount > self.limits.max_trx:
                    logger.warning(f"TRX amount {trx_amount} exceeds maximum {self.limits.max_trx}")
                    return False
            
            # Check USDT amount
            if 'usdt' in amounts:
                usdt_amount = amounts['usdt']
                if usdt_amount < self.limits.min_usdt:
                    logger.warning(f"USDT amount {usdt_amount} below minimum {self.limits.min_usdt}")
                    return False
                if usdt_amount > self.limits.max_usdt:
                    logger.warning(f"USDT amount {usdt_amount} exceeds maximum {self.limits.max_usdt}")
                    return False
            
            # Check ODT amount
            if 'odt' in amounts:
                odt_amount = amounts['odt']
                if odt_amount < self.limits.min_odt:
                    logger.warning(f"ODT amount {odt_amount} below minimum {self.limits.min_odt}")
                    return False
                if odt_amount > self.limits.max_odt:
                    logger.warning(f"ODT amount {odt_amount} exceeds maximum {self.limits.max_odt}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating transaction size: {e}")
            return False
    
    def validate_daily_volume(self, operation: str, volume_usd: float) -> bool:
        """Validate against daily volume limits"""
        try:
            today = datetime.now().date()
            
            with self.daily_volume_lock:
                current_volume = self.daily_volume[today]
                new_volume = current_volume + volume_usd
                
                # Check if this would exceed daily limits
                max_daily_volume = 1000000  # $1M daily limit
                if new_volume > max_daily_volume:
                    logger.warning(f"Daily volume limit would be exceeded: {new_volume} > {max_daily_volume}")
                    return False
                
                # Update volume
                self.daily_volume[today] = new_volume
                logger.info(f"Daily volume updated: {new_volume:.2f} USD")
                return True
                
        except Exception as e:
            logger.error(f"Error validating daily volume: {e}")
            return False
    
    def validate_wallet_balance(self, wallet_info: Dict, required_amounts: Dict[str, float]) -> bool:
        """Validate wallet has sufficient balance for transaction"""
        try:
            # Check TRX balance
            if 'trx' in required_amounts:
                required_trx = required_amounts['trx']
                available_trx = wallet_info.get('trx_balance', 0)
                if available_trx < required_trx:
                    logger.warning(f"Insufficient TRX balance: {available_trx} < {required_trx}")
                    return False
            
            # Check USDT balance
            if 'usdt' in required_amounts:
                required_usdt = required_amounts['usdt']
                available_usdt = wallet_info.get('usdt_balance', 0)
                if available_usdt < required_usdt:
                    logger.warning(f"Insufficient USDT balance: {available_usdt} < {required_usdt}")
                    return False
            
            # Check ODT balance
            if 'odt' in required_amounts:
                required_odt = required_amounts['odt']
                available_odt = wallet_info.get('odt_balance', 0)
                if available_odt < required_odt:
                    logger.warning(f"Insufficient ODT balance: {available_odt} < {required_odt}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating wallet balance: {e}")
            return False

class SafetyGuard:
    """Main safety guard that coordinates all risk controls"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.limits = TransactionLimits(
            max_trx=config['risk_controls']['max_tx_size_trx'],
            max_usdt=config['risk_controls']['max_tx_size_usdt'],
            max_odt=config['risk_controls']['max_tx_size_odt']
        )
        
        rate_limit_config = RateLimitConfig(
            min_delay=config['risk_controls']['min_delay_seconds'],
            max_delay=config['risk_controls']['max_delay_seconds'],
            max_transactions_per_hour=100,  # Configurable
            max_transactions_per_day=1000   # Configurable
        )
        
        self.rate_limiter = RateLimiter(rate_limit_config)
        self.validator = TransactionValidator(self.limits)
        self.circuit_breaker = CircuitBreaker()
        
    def check_all_guards(self, operation: str, amounts: Dict[str, float], 
                        wallet_info: Dict, volume_usd: float = 0) -> bool:
        """Check all safety guards before allowing transaction"""
        try:
            # Circuit breaker check
            if not self.circuit_breaker.can_proceed():
                logger.error("Circuit breaker is open - transaction blocked")
                return False
            
            # Rate limiting check
            if not self.rate_limiter.can_proceed():
                logger.warning("Rate limiting - transaction blocked")
                return False
            
            # Transaction size validation
            if not self.validator.validate_transaction_size(operation, amounts):
                logger.warning("Transaction size validation failed")
                return False
            
            # Wallet balance validation
            if not self.validator.validate_wallet_balance(wallet_info, amounts):
                logger.warning("Wallet balance validation failed")
                return False
            
            # Daily volume validation
            if volume_usd > 0 and not self.validator.validate_daily_volume(operation, volume_usd):
                logger.warning("Daily volume validation failed")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in safety guard checks: {e}")
            return False
    
    def record_success(self, operation: str, tx_hash: str):
        """Record successful transaction"""
        self.rate_limiter.record_transaction()
        self.circuit_breaker.record_success()
        logger.info(f"Transaction success recorded: {operation} - {tx_hash}")
    
    def record_failure(self, operation: str, error: str):
        """Record failed transaction"""
        self.rate_limiter.record_failure()
        self.circuit_breaker.record_failure()
        logger.warning(f"Transaction failure recorded: {operation} - {error}")
    
    def wait_if_needed(self):
        """Wait if rate limiting is required"""
        self.rate_limiter.wait_if_needed()

class CircuitBreaker:
    """Circuit breaker pattern for handling cascading failures"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.lock = threading.Lock()
    
    def can_proceed(self) -> bool:
        """Check if circuit breaker allows operation"""
        with self.lock:
            if self.state == "CLOSED":
                return True
            elif self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    logger.info("Circuit breaker moving to HALF_OPEN state")
                    return True
                return False
            elif self.state == "HALF_OPEN":
                return True
            return False
    
    def record_success(self):
        """Record successful operation"""
        with self.lock:
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info("Circuit breaker reset to CLOSED state")
    
    def record_failure(self):
        """Record failed operation"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")

class RetryHandler:
    """Handles retries with exponential backoff"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 60.0, backoff_multiplier: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.backoff_multiplier ** attempt),
                        self.max_delay
                    )
                    # Add jitter
                    delay *= random.uniform(0.8, 1.2)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")
        
        raise last_exception

class TradingHoursGuard:
    """Guard for trading hours restrictions"""
    
    def __init__(self, start_hour: int = 0, end_hour: int = 23):
        self.start_hour = start_hour
        self.end_hour = end_hour
    
    def is_trading_hours(self) -> bool:
        """Check if current time is within trading hours"""
        current_hour = datetime.now().hour
        return self.start_hour <= current_hour <= self.end_hour
    
    def get_time_until_trading(self) -> int:
        """Get seconds until trading hours begin"""
        now = datetime.now()
        if self.is_trading_hours():
            return 0
        
        # Calculate next trading start time
        if now.hour < self.start_hour:
            next_start = now.replace(hour=self.start_hour, minute=0, second=0, microsecond=0)
        else:
            next_start = (now + timedelta(days=1)).replace(
                hour=self.start_hour, minute=0, second=0, microsecond=0
            )
        
        return int((next_start - now).total_seconds())

def create_safety_guard(config: Dict) -> SafetyGuard:
    """Factory function to create safety guard with configuration"""
    return SafetyGuard(config)

def create_retry_handler(config: Dict) -> RetryHandler:
    """Factory function to create retry handler with configuration"""
    return RetryHandler(
        max_retries=config['risk_controls']['max_retries'],
        base_delay=1.0,
        max_delay=60.0,
        backoff_multiplier=config['risk_controls']['retry_delay_multiplier']
    )