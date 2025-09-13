"""
TRON Blockchain Utilities for SunSwap Automation Bot
Handles TRON network interactions, wallet management, and contract operations
"""

import os
import time
import random
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_DOWN
import toml
import requests
from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy.providers import HTTPProvider
from tronpy.contract import Contract
from tronpy.exceptions import TronError
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TronUtils:
    """Utility class for TRON blockchain operations"""
    
    def __init__(self, config_path: str = "config.toml", wallets_path: str = "wallets.toml"):
        """Initialize TRON utilities with configuration"""
        self.config = self._load_config(config_path)
        self.wallets = self._load_wallets(wallets_path)
        self.tron = self._init_tron_client()
        self.contracts = self._init_contracts()
        self.active_wallets = []
        self._validate_wallets()
        
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from TOML file"""
        try:
            with open(config_path, 'r') as f:
                return toml.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file {config_path} not found")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def _load_wallets(self, wallets_path: str) -> Dict:
        """Load wallet configuration from TOML file"""
        try:
            with open(wallets_path, 'r') as f:
                return toml.load(f)
        except FileNotFoundError:
            logger.error(f"Wallets file {wallets_path} not found")
            raise
        except Exception as e:
            logger.error(f"Error loading wallets: {e}")
            raise
    
    def _init_tron_client(self) -> Tron:
        """Initialize TRON client with RPC endpoints"""
        try:
            # Try primary RPC endpoint
            provider = HTTPProvider(self.config['network']['rpc_url'])
            tron = Tron(provider)
            
            # Test connection
            tron.get_latest_block_number()
            logger.info(f"Connected to TRON network: {self.config['network']['rpc_url']}")
            return tron
        except Exception as e:
            logger.warning(f"Primary RPC failed: {e}")
            # Try backup RPC endpoints
            for backup_url in self.config['network'].get('backup_rpc_urls', []):
                try:
                    provider = HTTPProvider(backup_url)
                    tron = Tron(provider)
                    tron.get_latest_block_number()
                    logger.info(f"Connected to TRON network via backup: {backup_url}")
                    return tron
                except Exception as backup_e:
                    logger.warning(f"Backup RPC {backup_url} failed: {backup_e}")
                    continue
            raise Exception("All RPC endpoints failed")
    
    def _init_contracts(self) -> Dict[str, Contract]:
        """Initialize contract instances"""
        contracts = {}
        try:
            # SunSwap Router
            contracts['router'] = self.tron.get_contract(
                self.config['contracts']['router_address']
            )
            
            # USDT (TRC20)
            contracts['usdt'] = self.tron.get_contract(
                self.config['contracts']['usdt_address']
            )
            
            # ODT (TRC20)
            contracts['odt'] = self.tron.get_contract(
                self.config['contracts']['odt_address']
            )
            
            # SunSwap Factory
            contracts['factory'] = self.tron.get_contract(
                self.config['contracts']['factory_address']
            )
            
            logger.info("All contracts initialized successfully")
            return contracts
        except Exception as e:
            logger.error(f"Error initializing contracts: {e}")
            raise
    
    def _validate_wallets(self):
        """Validate wallet private keys and check balances"""
        self.active_wallets = []
        
        for wallet_name, private_key_hex in self.wallets['wallets'].items():
            if private_key_hex == "YOUR_PRIVATE_KEY_HERE":
                logger.warning(f"Skipping {wallet_name} - placeholder private key")
                continue
                
            try:
                # Create private key object
                private_key = PrivateKey(bytes.fromhex(private_key_hex))
                address = private_key.public_key.to_base58check_address()
                
                # Check balances
                trx_balance = self.get_trx_balance(address)
                usdt_balance = self.get_token_balance(address, 'usdt')
                odt_balance = self.get_token_balance(address, 'odt')
                
                # Check if wallet meets minimum requirements
                min_trx = self.wallets['rotation']['min_balance_trx']
                min_usdt = self.wallets['rotation']['min_balance_usdt']
                min_odt = self.wallets['rotation']['min_balance_odt']
                
                if (trx_balance >= min_trx and 
                    usdt_balance >= min_usdt and 
                    odt_balance >= min_odt):
                    
                    wallet_info = {
                        'name': wallet_name,
                        'private_key': private_key,
                        'address': address,
                        'trx_balance': trx_balance,
                        'usdt_balance': usdt_balance,
                        'odt_balance': odt_balance
                    }
                    self.active_wallets.append(wallet_info)
                    logger.info(f"Wallet {wallet_name} ({address}) validated and active")
                else:
                    logger.warning(f"Wallet {wallet_name} ({address}) below minimum balance requirements")
                    
            except Exception as e:
                logger.error(f"Error validating wallet {wallet_name}: {e}")
        
        if not self.active_wallets:
            raise Exception("No active wallets found. Check balances and configuration.")
        
        logger.info(f"Found {len(self.active_wallets)} active wallets")
    
    def get_random_wallet(self) -> Dict:
        """Get a random active wallet for transaction rotation"""
        if not self.active_wallets:
            raise Exception("No active wallets available")
        return random.choice(self.active_wallets)
    
    def get_trx_balance(self, address: str) -> float:
        """Get TRX balance for an address"""
        try:
            account = self.tron.get_account(address)
            return account.get('balance', 0) / 1_000_000  # Convert from sun to TRX
        except Exception as e:
            logger.error(f"Error getting TRX balance for {address}: {e}")
            return 0.0
    
    def get_token_balance(self, address: str, token: str) -> float:
        """Get token balance for an address"""
        try:
            if token not in self.contracts:
                raise ValueError(f"Unknown token: {token}")
            
            contract = self.contracts[token]
            balance = contract.functions.balanceOf(address)
            decimals = contract.functions.decimals()
            
            return balance / (10 ** decimals)
        except Exception as e:
            logger.error(f"Error getting {token} balance for {address}: {e}")
            return 0.0
    
    def get_token_allowance(self, owner: str, spender: str, token: str) -> float:
        """Get token allowance for spender"""
        try:
            if token not in self.contracts:
                raise ValueError(f"Unknown token: {token}")
            
            contract = self.contracts[token]
            allowance = contract.functions.allowance(owner, spender)
            decimals = contract.functions.decimals()
            
            return allowance / (10 ** decimals)
        except Exception as e:
            logger.error(f"Error getting {token} allowance: {e}")
            return 0.0
    
    def approve_token(self, wallet: Dict, token: str, spender: str, amount: float) -> str:
        """Approve token spending for a contract"""
        try:
            private_key = wallet['private_key']
            address = wallet['address']
            
            if token not in self.contracts:
                raise ValueError(f"Unknown token: {token}")
            
            contract = self.contracts[token]
            decimals = contract.functions.decimals()
            amount_wei = int(amount * (10 ** decimals))
            
            # Build approve transaction
            txn = contract.functions.approve(spender, amount_wei)
            txn = txn.with_owner(address).build().sign(private_key)
            
            # Broadcast transaction
            result = txn.broadcast()
            tx_hash = result.get('txid')
            
            logger.info(f"Token approval transaction sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error approving {token}: {e}")
            raise
    
    def wait_for_transaction(self, tx_hash: str, timeout: int = 300) -> bool:
        """Wait for transaction confirmation"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                txn = self.tron.get_transaction(tx_hash)
                if txn and txn.get('ret', [{}])[0].get('contractRet') == 'SUCCESS':
                    logger.info(f"Transaction confirmed: {tx_hash}")
                    return True
                elif txn and txn.get('ret', [{}])[0].get('contractRet') == 'REVERT':
                    logger.error(f"Transaction reverted: {tx_hash}")
                    return False
            except Exception as e:
                logger.debug(f"Transaction not yet confirmed: {e}")
            
            time.sleep(5)
        
        logger.error(f"Transaction timeout: {tx_hash}")
        return False
    
    def get_gas_price(self) -> int:
        """Get current gas price for transactions"""
        try:
            # TRON uses energy and bandwidth instead of gas
            # Return a reasonable energy limit
            return 1000000  # 1M energy units
        except Exception as e:
            logger.error(f"Error getting gas price: {e}")
            return 1000000
    
    def estimate_gas(self, transaction_data: Dict) -> int:
        """Estimate gas/energy required for transaction"""
        try:
            # For TRON, return a conservative estimate
            return 200000  # 200K energy units
        except Exception as e:
            logger.error(f"Error estimating gas: {e}")
            return 200000
    
    def get_current_block_number(self) -> int:
        """Get current block number"""
        try:
            return self.tron.get_latest_block_number()
        except Exception as e:
            logger.error(f"Error getting block number: {e}")
            return 0
    
    def get_token_price_usd(self, token: str) -> float:
        """Get token price in USD (placeholder - integrate with price API)"""
        # This is a placeholder - in production, integrate with a price API
        # like CoinGecko, CoinMarketCap, or DEX aggregators
        price_map = {
            'trx': 0.08,
            'usdt': 1.0,
            'odt': 0.5  # Placeholder price for ODT
        }
        return price_map.get(token, 0.0)
    
    def calculate_slippage(self, amount: float, slippage_tolerance: float) -> Tuple[float, float]:
        """Calculate minimum amount out with slippage tolerance"""
        min_amount = amount * (1 - slippage_tolerance)
        max_amount = amount * (1 + slippage_tolerance)
        return min_amount, max_amount
    
    def format_amount(self, amount: float, decimals: int = 18) -> int:
        """Format amount to wei/sun units"""
        return int(amount * (10 ** decimals))
    
    def parse_amount(self, amount: int, decimals: int = 18) -> float:
        """Parse amount from wei/sun units"""
        return amount / (10 ** decimals)
    
    def get_deadline(self, seconds: int = 300) -> int:
        """Get transaction deadline timestamp"""
        return int(time.time()) + seconds
    
    def is_valid_address(self, address: str) -> bool:
        """Validate TRON address format"""
        try:
            # Basic TRON address validation
            return (len(address) == 34 and 
                   address.startswith('T') and 
                   address[1:].isalnum())
        except:
            return False
    
    def get_wallet_info(self, wallet: Dict) -> Dict:
        """Get comprehensive wallet information"""
        address = wallet['address']
        return {
            'address': address,
            'trx_balance': self.get_trx_balance(address),
            'usdt_balance': self.get_token_balance(address, 'usdt'),
            'odt_balance': self.get_token_balance(address, 'odt'),
            'usdt_allowance_router': self.get_token_allowance(
                address, 
                self.config['contracts']['router_address'], 
                'usdt'
            ),
            'odt_allowance_router': self.get_token_allowance(
                address, 
                self.config['contracts']['router_address'], 
                'odt'
            )
        }
    
    def log_transaction(self, tx_hash: str, operation: str, wallet: str, details: Dict):
        """Log transaction details for audit trail"""
        log_entry = {
            'timestamp': time.time(),
            'tx_hash': tx_hash,
            'operation': operation,
            'wallet': wallet,
            'details': details
        }
        
        # Log to file
        log_file = self.config['logging']['log_file']
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        logger.info(f"Transaction logged: {operation} - {tx_hash}")