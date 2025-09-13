"""
Liquidity Management Module for TRON SunSwap Automation Bot
Handles adding/removing liquidity for ODT/USDT pool
"""

import time
import random
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_DOWN
import json
from datetime import datetime

from utils_tron import TronUtils
from .guards import SafetyGuard, RetryHandler

logger = logging.getLogger(__name__)

class LiquidityManager:
    """Manages liquidity operations on SunSwap DEX"""
    
    def __init__(self, tron_utils: TronUtils, safety_guard: SafetyGuard, retry_handler: RetryHandler):
        self.tron_utils = tron_utils
        self.safety_guard = safety_guard
        self.retry_handler = retry_handler
        
        # Liquidity statistics
        self.daily_liquidity_volume = 0.0
        self.daily_add_operations = 0
        self.daily_remove_operations = 0
        self.target_daily_volume = self.tron_utils.config['trading']['daily_liquidity_volume_usd']
        
        # Pool information
        self.pool_address = None
        self.pool_reserves = {'usdt': 0.0, 'odt': 0.0}
        self.pool_token_supply = 0.0
        
    def get_pool_address(self) -> str:
        """Get the ODT/USDT pool address"""
        try:
            if self.pool_address:
                return self.pool_address
            
            factory = self.tron_utils.contracts['factory']
            usdt_addr = self.tron_utils.config['contracts']['usdt_address']
            odt_addr = self.tron_utils.config['contracts']['odt_address']
            
            # Get pair address from factory
            pair_address = factory.functions.getPair(usdt_addr, odt_addr)
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                raise ValueError("ODT/USDT pool does not exist")
            
            self.pool_address = pair_address
            logger.info(f"ODT/USDT pool address: {pair_address}")
            return pair_address
            
        except Exception as e:
            logger.error(f"Error getting pool address: {e}")
            raise
    
    def get_pool_reserves(self) -> Dict[str, float]:
        """Get current pool reserves"""
        try:
            pool_address = self.get_pool_address()
            pool_contract = self.tron_utils.tron.get_contract(pool_address)
            
            # Get reserves
            reserves = pool_contract.functions.getReserves()
            
            # Get token addresses to determine which is which
            token0 = pool_contract.functions.token0()
            token1 = pool_contract.functions.token1()
            
            usdt_addr = self.tron_utils.config['contracts']['usdt_address']
            odt_addr = self.tron_utils.config['contracts']['odt_address']
            
            # Determine which reserve is which token
            if token0 == usdt_addr:
                usdt_reserve = reserves[0] / (10 ** 6)  # USDT has 6 decimals
                odt_reserve = reserves[1] / (10 ** 18)  # ODT has 18 decimals
            else:
                usdt_reserve = reserves[1] / (10 ** 6)
                odt_reserve = reserves[0] / (10 ** 18)
            
            self.pool_reserves = {
                'usdt': usdt_reserve,
                'odt': odt_reserve
            }
            
            logger.debug(f"Pool reserves: USDT={usdt_reserve:.2f}, ODT={odt_reserve:.2f}")
            return self.pool_reserves
            
        except Exception as e:
            logger.error(f"Error getting pool reserves: {e}")
            return {'usdt': 0.0, 'odt': 0.0}
    
    def get_pool_token_balance(self, wallet_address: str) -> float:
        """Get pool token balance for a wallet"""
        try:
            pool_address = self.get_pool_address()
            pool_contract = self.tron_utils.tron.get_contract(pool_address)
            
            balance = pool_contract.functions.balanceOf(wallet_address)
            decimals = pool_contract.functions.decimals()
            
            return balance / (10 ** decimals)
            
        except Exception as e:
            logger.error(f"Error getting pool token balance: {e}")
            return 0.0
    
    def calculate_liquidity_amounts(self, usdt_amount: float) -> Tuple[float, float]:
        """Calculate optimal liquidity amounts based on current pool ratio"""
        try:
            reserves = self.get_pool_reserves()
            
            if reserves['usdt'] <= 0 or reserves['odt'] <= 0:
                raise ValueError("Invalid pool reserves")
            
            # Calculate ODT amount based on current ratio
            odt_amount = (usdt_amount * reserves['odt']) / reserves['usdt']
            
            return usdt_amount, odt_amount
            
        except Exception as e:
            logger.error(f"Error calculating liquidity amounts: {e}")
            raise
    
    def add_liquidity(self, wallet: Dict, usdt_amount: float, odt_amount: float) -> str:
        """Add liquidity to ODT/USDT pool"""
        try:
            address = wallet['address']
            private_key = wallet['private_key']
            
            usdt_addr = self.tron_utils.config['contracts']['usdt_address']
            odt_addr = self.tron_utils.config['contracts']['odt_address']
            router_addr = self.tron_utils.config['contracts']['router_address']
            
            # Get deadline
            deadline = self.tron_utils.get_deadline(
                self.tron_utils.config['risk_controls']['tx_deadline']
            )
            
            # Format amounts
            usdt_amount_wei = self.tron_utils.format_amount(usdt_amount, 6)  # USDT has 6 decimals
            odt_amount_wei = self.tron_utils.format_amount(odt_amount, 18)  # ODT has 18 decimals
            
            # Calculate minimum amounts (with slippage tolerance)
            slippage = self.tron_utils.config['risk_controls']['slippage_tolerance']
            min_usdt = usdt_amount_wei * (1 - slippage)
            min_odt = odt_amount_wei * (1 - slippage)
            
            # Get router contract
            router = self.tron_utils.contracts['router']
            
            # Build add liquidity transaction
            txn = router.functions.addLiquidity(
                usdt_addr,
                odt_addr,
                usdt_amount_wei,
                odt_amount_wei,
                min_usdt,
                min_odt,
                address,  # to address
                deadline
            )
            
            txn = txn.with_owner(address).build().sign(private_key)
            
            # Broadcast transaction
            result = txn.broadcast()
            tx_hash = result.get('txid')
            
            logger.info(f"Add liquidity transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error adding liquidity: {e}")
            raise
    
    def remove_liquidity(self, wallet: Dict, pool_token_amount: float) -> str:
        """Remove liquidity from ODT/USDT pool"""
        try:
            address = wallet['address']
            private_key = wallet['private_key']
            
            usdt_addr = self.tron_utils.config['contracts']['usdt_address']
            odt_addr = self.tron_utils.config['contracts']['odt_address']
            router_addr = self.tron_utils.config['contracts']['router_address']
            
            # Get deadline
            deadline = self.tron_utils.get_deadline(
                self.tron_utils.config['risk_controls']['tx_deadline']
            )
            
            # Format pool token amount
            pool_token_amount_wei = self.tron_utils.format_amount(pool_token_amount, 18)
            
            # Calculate minimum amounts (with slippage tolerance)
            slippage = self.tron_utils.config['risk_controls']['slippage_tolerance']
            min_usdt = 0  # Will be calculated by router
            min_odt = 0   # Will be calculated by router
            
            # Get router contract
            router = self.tron_utils.contracts['router']
            
            # Build remove liquidity transaction
            txn = router.functions.removeLiquidity(
                usdt_addr,
                odt_addr,
                pool_token_amount_wei,
                min_usdt,
                min_odt,
                address,  # to address
                deadline
            )
            
            txn = txn.with_owner(address).build().sign(private_key)
            
            # Broadcast transaction
            result = txn.broadcast()
            tx_hash = result.get('txid')
            
            logger.info(f"Remove liquidity transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error removing liquidity: {e}")
            raise
    
    def ensure_token_approvals(self, wallet: Dict, usdt_amount: float, odt_amount: float) -> bool:
        """Ensure both tokens are approved for router spending"""
        try:
            router_addr = self.tron_utils.config['contracts']['router_address']
            
            # Check USDT allowance
            usdt_allowance = self.tron_utils.get_token_allowance(
                wallet['address'], router_addr, 'usdt'
            )
            
            if usdt_allowance < usdt_amount:
                logger.info(f"Approving USDT for router: {usdt_amount}")
                tx_hash = self.tron_utils.approve_token(wallet, 'usdt', router_addr, usdt_amount)
                if not self.tron_utils.wait_for_transaction(tx_hash):
                    logger.error("USDT approval failed")
                    return False
            
            # Check ODT allowance
            odt_allowance = self.tron_utils.get_token_allowance(
                wallet['address'], router_addr, 'odt'
            )
            
            if odt_allowance < odt_amount:
                logger.info(f"Approving ODT for router: {odt_amount}")
                tx_hash = self.tron_utils.approve_token(wallet, 'odt', router_addr, odt_amount)
                if not self.tron_utils.wait_for_transaction(tx_hash):
                    logger.error("ODT approval failed")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring token approvals: {e}")
            return False
    
    def execute_add_liquidity(self, amount_usd: float) -> Optional[str]:
        """Execute add liquidity operation with all safety checks"""
        try:
            # Get random wallet
            wallet = self.tron_utils.get_random_wallet()
            wallet_info = self.tron_utils.get_wallet_info(wallet)
            
            # Calculate liquidity amounts
            usdt_amount = amount_usd / 2  # Split equally between tokens
            usdt_amount, odt_amount = self.calculate_liquidity_amounts(usdt_amount)
            
            # Prepare amounts for validation
            amounts = {
                'usdt': usdt_amount,
                'odt': odt_amount
            }
            
            # Safety checks
            if not self.safety_guard.check_all_guards(
                "add_liquidity", 
                amounts, 
                wallet_info, 
                amount_usd
            ):
                logger.warning("Safety checks failed for add liquidity")
                return None
            
            # Ensure token approvals
            if not self.ensure_token_approvals(wallet, usdt_amount, odt_amount):
                logger.error("Failed to approve tokens for liquidity")
                return None
            
            # Execute add liquidity with retry
            def _execute_add_liquidity():
                return self.add_liquidity(wallet, usdt_amount, odt_amount)
            
            tx_hash = self.retry_handler.execute_with_retry(_execute_add_liquidity)
            
            # Wait for confirmation
            if self.tron_utils.wait_for_transaction(tx_hash):
                # Record success
                self.safety_guard.record_success("add_liquidity", tx_hash)
                self.daily_liquidity_volume += amount_usd
                self.daily_add_operations += 1
                
                # Log transaction
                self.tron_utils.log_transaction(tx_hash, "add_liquidity", 
                                              wallet['address'], {
                    'usdt_amount': usdt_amount,
                    'odt_amount': odt_amount,
                    'amount_usd': amount_usd
                })
                
                logger.info(f"Liquidity added: {usdt_amount} USDT + {odt_amount} ODT")
                return tx_hash
            else:
                # Record failure
                self.safety_guard.record_failure("add_liquidity", "Transaction failed")
                logger.error("Add liquidity transaction failed")
                return None
                
        except Exception as e:
            logger.error(f"Error executing add liquidity: {e}")
            self.safety_guard.record_failure("add_liquidity", str(e))
            return None
    
    def execute_remove_liquidity(self, pool_token_amount: float) -> Optional[str]:
        """Execute remove liquidity operation with all safety checks"""
        try:
            # Get random wallet
            wallet = self.tron_utils.get_random_wallet()
            wallet_info = self.tron_utils.get_wallet_info(wallet)
            
            # Check pool token balance
            pool_balance = self.get_pool_token_balance(wallet['address'])
            if pool_balance < pool_token_amount:
                logger.warning(f"Insufficient pool token balance: {pool_balance} < {pool_token_amount}")
                return None
            
            # Estimate USD value of removal
            reserves = self.get_pool_reserves()
            pool_token_supply = self.get_pool_token_supply()
            
            if pool_token_supply > 0:
                usdt_value = (pool_token_amount / pool_token_supply) * reserves['usdt']
                odt_value = (pool_token_amount / pool_token_supply) * reserves['odt']
                amount_usd = usdt_value + (odt_value * self.tron_utils.get_token_price_usd('odt'))
            else:
                amount_usd = 0
            
            # Prepare amounts for validation (no specific token amounts needed for removal)
            amounts = {}
            
            # Safety checks
            if not self.safety_guard.check_all_guards(
                "remove_liquidity", 
                amounts, 
                wallet_info, 
                amount_usd
            ):
                logger.warning("Safety checks failed for remove liquidity")
                return None
            
            # Execute remove liquidity with retry
            def _execute_remove_liquidity():
                return self.remove_liquidity(wallet, pool_token_amount)
            
            tx_hash = self.retry_handler.execute_with_retry(_execute_remove_liquidity)
            
            # Wait for confirmation
            if self.tron_utils.wait_for_transaction(tx_hash):
                # Record success
                self.safety_guard.record_success("remove_liquidity", tx_hash)
                self.daily_liquidity_volume += amount_usd
                self.daily_remove_operations += 1
                
                # Log transaction
                self.tron_utils.log_transaction(tx_hash, "remove_liquidity", 
                                              wallet['address'], {
                    'pool_token_amount': pool_token_amount,
                    'amount_usd': amount_usd
                })
                
                logger.info(f"Liquidity removed: {pool_token_amount} pool tokens")
                return tx_hash
            else:
                # Record failure
                self.safety_guard.record_failure("remove_liquidity", "Transaction failed")
                logger.error("Remove liquidity transaction failed")
                return None
                
        except Exception as e:
            logger.error(f"Error executing remove liquidity: {e}")
            self.safety_guard.record_failure("remove_liquidity", str(e))
            return None
    
    def get_pool_token_supply(self) -> float:
        """Get total supply of pool tokens"""
        try:
            pool_address = self.get_pool_address()
            pool_contract = self.tron_utils.tron.get_contract(pool_address)
            
            total_supply = pool_contract.functions.totalSupply()
            decimals = pool_contract.functions.decimals()
            
            return total_supply / (10 ** decimals)
            
        except Exception as e:
            logger.error(f"Error getting pool token supply: {e}")
            return 0.0
    
    def execute_random_liquidity_operation(self) -> Optional[str]:
        """Execute a random liquidity operation (add or remove)"""
        try:
            # Randomly choose add or remove (70% add, 30% remove)
            operation = random.choices(['add', 'remove'], weights=[70, 30])[0]
            
            if operation == 'add':
                # Random amount between $1000 and $10000
                amount_usd = random.uniform(1000, 10000)
                logger.info(f"Executing add liquidity: ${amount_usd:.2f}")
                return self.execute_add_liquidity(amount_usd)
            else:
                # Get random wallet and check pool token balance
                wallet = self.tron_utils.get_random_wallet()
                pool_balance = self.get_pool_token_balance(wallet['address'])
                
                if pool_balance > 0:
                    # Remove 10-50% of balance
                    remove_percentage = random.uniform(0.1, 0.5)
                    pool_token_amount = pool_balance * remove_percentage
                    logger.info(f"Executing remove liquidity: {pool_token_amount:.2f} pool tokens")
                    return self.execute_remove_liquidity(pool_token_amount)
                else:
                    logger.info("No pool tokens to remove, skipping remove liquidity")
                    return None
                    
        except Exception as e:
            logger.error(f"Error executing random liquidity operation: {e}")
            return None
    
    def get_daily_progress(self) -> Dict[str, float]:
        """Get daily liquidity progress"""
        return {
            'volume_usd': self.daily_liquidity_volume,
            'target_volume_usd': self.target_daily_volume,
            'progress_percent': (self.daily_liquidity_volume / self.target_daily_volume) * 100,
            'add_operations': self.daily_add_operations,
            'remove_operations': self.daily_remove_operations
        }
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_liquidity_volume = 0.0
        self.daily_add_operations = 0
        self.daily_remove_operations = 0
        logger.info("Daily liquidity statistics reset")
    
    def should_continue_trading(self) -> bool:
        """Check if we should continue liquidity operations based on daily targets"""
        if self.daily_liquidity_volume >= self.target_daily_volume:
            logger.info(f"Daily liquidity volume target reached: {self.daily_liquidity_volume}")
            return False
        
        return True

class LiquidityScheduler:
    """Schedules liquidity operations to meet daily volume targets"""
    
    def __init__(self, liquidity_manager: LiquidityManager):
        self.liquidity_manager = liquidity_manager
        self.is_running = False
        
    def start_trading(self):
        """Start automated liquidity operations"""
        self.is_running = True
        logger.info("Starting automated liquidity operations")
        
        while self.is_running and self.liquidity_manager.should_continue_trading():
            try:
                # Check if we need to wait
                self.safety_guard.wait_if_needed()
                
                # Execute random liquidity operation
                tx_hash = self.liquidity_manager.execute_random_liquidity_operation()
                
                if tx_hash:
                    logger.info(f"Liquidity operation executed: {tx_hash}")
                else:
                    logger.warning("Liquidity operation failed")
                
                # Get progress
                progress = self.liquidity_manager.get_daily_progress()
                logger.info(f"Daily liquidity progress: {progress['progress_percent']:.1f}% "
                          f"({progress['volume_usd']:.2f}/{progress['target_volume_usd']:.2f} USD)")
                
                # Random delay between operations
                delay = random.uniform(120, 600)  # 2-10 minutes
                logger.info(f"Waiting {delay:.1f} seconds before next operation...")
                time.sleep(delay)
                
            except KeyboardInterrupt:
                logger.info("Liquidity operations stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in liquidity operations loop: {e}")
                time.sleep(60)  # Wait before retrying
        
        logger.info("Automated liquidity operations stopped")
    
    def stop_trading(self):
        """Stop automated liquidity operations"""
        self.is_running = False
        logger.info("Stopping automated liquidity operations")

def create_liquidity_manager(tron_utils: TronUtils, safety_guard: SafetyGuard, 
                           retry_handler: RetryHandler) -> LiquidityManager:
    """Factory function to create liquidity manager"""
    return LiquidityManager(tron_utils, safety_guard, retry_handler)

def create_liquidity_scheduler(liquidity_manager: LiquidityManager) -> LiquidityScheduler:
    """Factory function to create liquidity scheduler"""
    return LiquidityScheduler(liquidity_manager)