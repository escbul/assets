"""
Swaps Module for TRON SunSwap Automation Bot
Handles TRX/ODT and USDT/ODT trading operations
"""

import time
import random
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_DOWN
import json
from datetime import datetime

from utils_tron import TronUtils
from .guards import SafetyGuard, RetryHandler, TradingHoursGuard

logger = logging.getLogger(__name__)

class SwapManager:
    """Manages swap operations on SunSwap DEX"""
    
    def __init__(self, tron_utils: TronUtils, safety_guard: SafetyGuard, retry_handler: RetryHandler):
        self.tron_utils = tron_utils
        self.safety_guard = safety_guard
        self.retry_handler = retry_handler
        self.trading_hours_guard = TradingHoursGuard(
            start_hour=self.tron_utils.config['trading']['trading_start_hour'],
            end_hour=self.tron_utils.config['trading']['trading_end_hour']
        )
        
        # Trading statistics
        self.daily_swap_volume = 0.0
        self.daily_swap_count = 0
        self.target_daily_volume = self.tron_utils.config['trading']['daily_swap_volume_usd']
        
    def get_swap_amounts(self, token_in: str, token_out: str, 
                        min_amount_usd: float, max_amount_usd: float) -> Tuple[float, float]:
        """Calculate swap amounts based on current prices and limits"""
        try:
            # Get current token prices
            price_in = self.tron_utils.get_token_price_usd(token_in)
            price_out = self.tron_utils.get_token_price_usd(token_out)
            
            if price_in <= 0 or price_out <= 0:
                raise ValueError(f"Invalid token prices: {token_in}={price_in}, {token_out}={price_out}")
            
            # Calculate random amount within limits
            amount_usd = random.uniform(min_amount_usd, max_amount_usd)
            
            # Convert to token amounts
            amount_in = amount_usd / price_in
            amount_out = amount_usd / price_out
            
            return amount_in, amount_out
            
        except Exception as e:
            logger.error(f"Error calculating swap amounts: {e}")
            raise
    
    def get_amounts_out(self, amount_in: float, path: List[str]) -> float:
        """Get expected amount out for a swap path"""
        try:
            router = self.tron_utils.contracts['router']
            
            # Get amounts out from router
            amounts_out = router.functions.getAmountsOut(
                self.tron_utils.format_amount(amount_in, 18),  # Assuming 18 decimals
                path
            )
            
            if not amounts_out or len(amounts_out) < 2:
                raise ValueError("Invalid amounts out from router")
            
            # Return the last amount (final output)
            return self.tron_utils.parse_amount(amounts_out[-1], 18)
            
        except Exception as e:
            logger.error(f"Error getting amounts out: {e}")
            # Return a conservative estimate
            return amount_in * 0.95  # 5% slippage estimate
    
    def swap_exact_tokens_for_tokens(self, wallet: Dict, amount_in: float, 
                                   token_in: str, token_out: str, 
                                   min_amount_out: float) -> str:
        """Execute exact token swap"""
        try:
            address = wallet['address']
            private_key = wallet['private_key']
            
            # Get token addresses
            token_in_addr = self.tron_utils.config['contracts'][f'{token_in}_address']
            token_out_addr = self.tron_utils.config['contracts'][f'{token_out}_address']
            router_addr = self.tron_utils.config['contracts']['router_address']
            
            # Create swap path
            path = [token_in_addr, token_out_addr]
            
            # Get deadline
            deadline = self.tron_utils.get_deadline(
                self.tron_utils.config['risk_controls']['tx_deadline']
            )
            
            # Format amounts
            amount_in_wei = self.tron_utils.format_amount(amount_in, 18)
            min_amount_out_wei = self.tron_utils.format_amount(min_amount_out, 18)
            
            # Get router contract
            router = self.tron_utils.contracts['router']
            
            # Build swap transaction
            txn = router.functions.swapExactTokensForTokens(
                amount_in_wei,
                min_amount_out_wei,
                path,
                address,  # to address
                deadline
            )
            
            txn = txn.with_owner(address).build().sign(private_key)
            
            # Broadcast transaction
            result = txn.broadcast()
            tx_hash = result.get('txid')
            
            logger.info(f"Swap transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error executing token swap: {e}")
            raise
    
    def swap_exact_trx_for_tokens(self, wallet: Dict, amount_in: float, 
                                token_out: str, min_amount_out: float) -> str:
        """Execute TRX to token swap"""
        try:
            address = wallet['address']
            private_key = wallet['private_key']
            
            # Get token address
            token_out_addr = self.tron_utils.config['contracts'][f'{token_out}_address']
            router_addr = self.tron_utils.config['contracts']['router_address']
            
            # Create swap path (TRX -> Token)
            path = [self.tron_utils.config['contracts']['wtrx_address'], token_out_addr]
            
            # Get deadline
            deadline = self.tron_utils.get_deadline(
                self.tron_utils.config['risk_controls']['tx_deadline']
            )
            
            # Format amounts
            amount_in_sun = self.tron_utils.format_amount(amount_in, 6)  # TRX has 6 decimals
            min_amount_out_wei = self.tron_utils.format_amount(min_amount_out, 18)
            
            # Get router contract
            router = self.tron_utils.contracts['router']
            
            # Build swap transaction
            txn = router.functions.swapExactTRXForTokens(
                min_amount_out_wei,
                path,
                address,  # to address
                deadline
            )
            
            # Add TRX value
            txn = txn.with_owner(address).build().sign(private_key)
            
            # Broadcast transaction
            result = txn.broadcast()
            tx_hash = result.get('txid')
            
            logger.info(f"TRX swap transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error executing TRX swap: {e}")
            raise
    
    def swap_exact_tokens_for_trx(self, wallet: Dict, amount_in: float, 
                                token_in: str, min_amount_out: float) -> str:
        """Execute token to TRX swap"""
        try:
            address = wallet['address']
            private_key = wallet['private_key']
            
            # Get token address
            token_in_addr = self.tron_utils.config['contracts'][f'{token_in}_address']
            router_addr = self.tron_utils.config['contracts']['router_address']
            
            # Create swap path (Token -> TRX)
            path = [token_in_addr, self.tron_utils.config['contracts']['wtrx_address']]
            
            # Get deadline
            deadline = self.tron_utils.get_deadline(
                self.tron_utils.config['risk_controls']['tx_deadline']
            )
            
            # Format amounts
            amount_in_wei = self.tron_utils.format_amount(amount_in, 18)
            min_amount_out_sun = self.tron_utils.format_amount(min_amount_out, 6)
            
            # Get router contract
            router = self.tron_utils.contracts['router']
            
            # Build swap transaction
            txn = router.functions.swapExactTokensForTRX(
                amount_in_wei,
                min_amount_out_sun,
                path,
                address,  # to address
                deadline
            )
            
            txn = txn.with_owner(address).build().sign(private_key)
            
            # Broadcast transaction
            result = txn.broadcast()
            tx_hash = result.get('txid')
            
            logger.info(f"Token to TRX swap transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error executing token to TRX swap: {e}")
            raise
    
    def ensure_token_approval(self, wallet: Dict, token: str, amount: float) -> bool:
        """Ensure token is approved for router spending"""
        try:
            address = wallet['address']
            router_addr = self.tron_utils.config['contracts']['router_address']
            
            # Check current allowance
            current_allowance = self.tron_utils.get_token_allowance(address, router_addr, token)
            
            if current_allowance >= amount:
                logger.debug(f"Token {token} already approved for {amount}")
                return True
            
            # Approve token
            logger.info(f"Approving {token} for router spending: {amount}")
            tx_hash = self.tron_utils.approve_token(wallet, token, router_addr, amount)
            
            # Wait for approval
            if self.tron_utils.wait_for_transaction(tx_hash):
                logger.info(f"Token {token} approval confirmed")
                return True
            else:
                logger.error(f"Token {token} approval failed")
                return False
                
        except Exception as e:
            logger.error(f"Error ensuring token approval: {e}")
            return False
    
    def execute_swap(self, token_in: str, token_out: str, amount_usd: float) -> Optional[str]:
        """Execute a complete swap operation with all safety checks"""
        try:
            # Check trading hours
            if not self.trading_hours_guard.is_trading_hours():
                wait_time = self.trading_hours_guard.get_time_until_trading()
                logger.info(f"Outside trading hours. Waiting {wait_time} seconds...")
                return None
            
            # Get random wallet
            wallet = self.tron_utils.get_random_wallet()
            wallet_info = self.tron_utils.get_wallet_info(wallet)
            
            # Calculate swap amounts
            min_amount_usd = self.tron_utils.config['trading']['min_trade_size_usd']
            max_amount_usd = self.tron_utils.config['trading']['max_trade_size_usd']
            
            amount_in, expected_amount_out = self.get_swap_amounts(
                token_in, token_out, min_amount_usd, max_amount_usd
            )
            
            # Apply slippage tolerance
            slippage = self.tron_utils.config['risk_controls']['slippage_tolerance']
            min_amount_out = expected_amount_out * (1 - slippage)
            
            # Prepare amounts for validation
            amounts = {token_in: amount_in}
            if token_out == 'trx':
                amounts['trx'] = expected_amount_out
            else:
                amounts[token_out] = expected_amount_out
            
            # Safety checks
            if not self.safety_guard.check_all_guards(
                f"swap_{token_in}_{token_out}", 
                amounts, 
                wallet_info, 
                amount_usd
            ):
                logger.warning("Safety checks failed for swap")
                return None
            
            # Ensure token approval if needed
            if token_in != 'trx':
                if not self.ensure_token_approval(wallet, token_in, amount_in):
                    logger.error(f"Failed to approve {token_in}")
                    return None
            
            # Execute swap with retry
            def _execute_swap():
                if token_in == 'trx' and token_out != 'trx':
                    return self.swap_exact_trx_for_tokens(wallet, amount_in, token_out, min_amount_out)
                elif token_in != 'trx' and token_out == 'trx':
                    return self.swap_exact_tokens_for_trx(wallet, amount_in, token_in, min_amount_out)
                else:
                    return self.swap_exact_tokens_for_tokens(wallet, amount_in, token_in, token_out, min_amount_out)
            
            tx_hash = self.retry_handler.execute_with_retry(_execute_swap)
            
            # Wait for confirmation
            if self.tron_utils.wait_for_transaction(tx_hash):
                # Record success
                self.safety_guard.record_success(f"swap_{token_in}_{token_out}", tx_hash)
                self.daily_swap_volume += amount_usd
                self.daily_swap_count += 1
                
                # Log transaction
                self.tron_utils.log_transaction(tx_hash, f"swap_{token_in}_{token_out}", 
                                              wallet['address'], {
                    'amount_in': amount_in,
                    'amount_out': expected_amount_out,
                    'token_in': token_in,
                    'token_out': token_out,
                    'amount_usd': amount_usd
                })
                
                logger.info(f"Swap completed: {amount_in} {token_in} -> {expected_amount_out} {token_out}")
                return tx_hash
            else:
                # Record failure
                self.safety_guard.record_failure(f"swap_{token_in}_{token_out}", "Transaction failed")
                logger.error("Swap transaction failed")
                return None
                
        except Exception as e:
            logger.error(f"Error executing swap: {e}")
            self.safety_guard.record_failure(f"swap_{token_in}_{token_out}", str(e))
            return None
    
    def execute_random_swap(self) -> Optional[str]:
        """Execute a random swap operation"""
        try:
            # Define possible swap pairs
            swap_pairs = [
                ('trx', 'odt'),
                ('odt', 'trx'),
                ('usdt', 'odt'),
                ('odt', 'usdt')
            ]
            
            # Select random pair
            token_in, token_out = random.choice(swap_pairs)
            
            # Calculate random amount
            min_amount_usd = self.tron_utils.config['trading']['min_trade_size_usd']
            max_amount_usd = self.tron_utils.config['trading']['max_trade_size_usd']
            amount_usd = random.uniform(min_amount_usd, max_amount_usd)
            
            logger.info(f"Executing random swap: {token_in} -> {token_out}, ${amount_usd:.2f}")
            return self.execute_swap(token_in, token_out, amount_usd)
            
        except Exception as e:
            logger.error(f"Error executing random swap: {e}")
            return None
    
    def get_daily_progress(self) -> Dict[str, float]:
        """Get daily trading progress"""
        return {
            'volume_usd': self.daily_swap_volume,
            'target_volume_usd': self.target_daily_volume,
            'progress_percent': (self.daily_swap_volume / self.target_daily_volume) * 100,
            'swap_count': self.daily_swap_count
        }
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_swap_volume = 0.0
        self.daily_swap_count = 0
        logger.info("Daily swap statistics reset")
    
    def should_continue_trading(self) -> bool:
        """Check if we should continue trading based on daily targets"""
        if self.daily_swap_volume >= self.target_daily_volume:
            logger.info(f"Daily swap volume target reached: {self.daily_swap_volume}")
            return False
        
        return True

class SwapScheduler:
    """Schedules swap operations to meet daily volume targets"""
    
    def __init__(self, swap_manager: SwapManager):
        self.swap_manager = swap_manager
        self.is_running = False
        self.last_swap_time = 0
        
    def start_trading(self):
        """Start automated trading"""
        self.is_running = True
        logger.info("Starting automated swap trading")
        
        while self.is_running and self.swap_manager.should_continue_trading():
            try:
                # Check if we need to wait
                self.safety_guard.wait_if_needed()
                
                # Execute random swap
                tx_hash = self.swap_manager.execute_random_swap()
                
                if tx_hash:
                    self.last_swap_time = time.time()
                    logger.info(f"Swap executed: {tx_hash}")
                else:
                    logger.warning("Swap execution failed")
                
                # Get progress
                progress = self.swap_manager.get_daily_progress()
                logger.info(f"Daily progress: {progress['progress_percent']:.1f}% "
                          f"({progress['volume_usd']:.2f}/{progress['target_volume_usd']:.2f} USD)")
                
                # Random delay between trades
                delay = random.uniform(60, 300)  # 1-5 minutes
                logger.info(f"Waiting {delay:.1f} seconds before next trade...")
                time.sleep(delay)
                
            except KeyboardInterrupt:
                logger.info("Trading stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                time.sleep(60)  # Wait before retrying
        
        logger.info("Automated trading stopped")
    
    def stop_trading(self):
        """Stop automated trading"""
        self.is_running = False
        logger.info("Stopping automated trading")

def create_swap_manager(tron_utils: TronUtils, safety_guard: SafetyGuard, 
                       retry_handler: RetryHandler) -> SwapManager:
    """Factory function to create swap manager"""
    return SwapManager(tron_utils, safety_guard, retry_handler)

def create_swap_scheduler(swap_manager: SwapManager) -> SwapScheduler:
    """Factory function to create swap scheduler"""
    return SwapScheduler(swap_manager)