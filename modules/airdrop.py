"""
Airdrop Module for TRON SunSwap Automation Bot
Handles token distribution to multiple recipients
"""

import time
import random
import logging
import csv
import json
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
import pandas as pd

from utils_tron import TronUtils
from .guards import SafetyGuard, RetryHandler

logger = logging.getLogger(__name__)

class AirdropManager:
    """Manages airdrop operations for ODT token distribution"""
    
    def __init__(self, tron_utils: TronUtils, safety_guard: SafetyGuard, retry_handler: RetryHandler):
        self.tron_utils = tron_utils
        self.safety_guard = safety_guard
        self.retry_handler = retry_handler
        
        # Airdrop statistics
        self.total_recipients = 0
        self.successful_drops = 0
        self.failed_drops = 0
        self.total_amount_distributed = 0.0
        
        # Results tracking
        self.airdrop_results = []
        
    def load_recipients(self, csv_file: str) -> List[Dict[str, Any]]:
        """Load recipient addresses and amounts from CSV file"""
        try:
            recipients = []
            
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    address = row.get('address', '').strip()
                    amount_str = row.get('amount_odt', '').strip()
                    notes = row.get('notes', '').strip()
                    
                    if not address:
                        logger.warning(f"Skipping row with empty address: {row}")
                        continue
                    
                    if not self.tron_utils.is_valid_address(address):
                        logger.warning(f"Invalid address format: {address}")
                        continue
                    
                    try:
                        amount = float(amount_str) if amount_str else self.tron_utils.config['airdrop']['default_airdrop_amount']
                    except ValueError:
                        logger.warning(f"Invalid amount for {address}: {amount_str}, using default")
                        amount = self.tron_utils.config['airdrop']['default_airdrop_amount']
                    
                    recipients.append({
                        'address': address,
                        'amount': amount,
                        'notes': notes
                    })
            
            self.total_recipients = len(recipients)
            logger.info(f"Loaded {self.total_recipients} recipients from {csv_file}")
            return recipients
            
        except Exception as e:
            logger.error(f"Error loading recipients from {csv_file}: {e}")
            raise
    
    def send_token(self, wallet: Dict, recipient_address: str, amount: float) -> str:
        """Send ODT tokens to a recipient address"""
        try:
            sender_address = wallet['address']
            private_key = wallet['private_key']
            
            # Get ODT contract
            odt_contract = self.tron_utils.contracts['odt']
            
            # Format amount
            amount_wei = self.tron_utils.format_amount(amount, 18)  # ODT has 18 decimals
            
            # Build transfer transaction
            txn = odt_contract.functions.transfer(recipient_address, amount_wei)
            txn = txn.with_owner(sender_address).build().sign(private_key)
            
            # Broadcast transaction
            result = txn.broadcast()
            tx_hash = result.get('txid')
            
            logger.info(f"Token transfer sent: {amount} ODT to {recipient_address} - {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error sending tokens to {recipient_address}: {e}")
            raise
    
    def execute_airdrop(self, recipients: List[Dict[str, Any]], 
                       batch_size: int = 10, delay_between_batches: float = 30.0) -> Dict[str, Any]:
        """Execute airdrop to all recipients with batching"""
        try:
            logger.info(f"Starting airdrop to {len(recipients)} recipients")
            
            # Reset statistics
            self.successful_drops = 0
            self.failed_drops = 0
            self.total_amount_distributed = 0.0
            self.airdrop_results = []
            
            # Process recipients in batches
            total_batches = (len(recipients) + batch_size - 1) // batch_size
            
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(recipients))
                batch_recipients = recipients[start_idx:end_idx]
                
                logger.info(f"Processing batch {batch_num + 1}/{total_batches} "
                          f"({len(batch_recipients)} recipients)")
                
                # Process batch
                batch_results = self._process_batch(batch_recipients)
                self.airdrop_results.extend(batch_results)
                
                # Wait between batches (except for the last one)
                if batch_num < total_batches - 1:
                    logger.info(f"Waiting {delay_between_batches} seconds before next batch...")
                    time.sleep(delay_between_batches)
            
            # Generate summary
            summary = self._generate_summary()
            logger.info(f"Airdrop completed: {summary}")
            
            # Save results to CSV
            self._save_results_to_csv()
            
            return summary
            
        except Exception as e:
            logger.error(f"Error executing airdrop: {e}")
            raise
    
    def _process_batch(self, batch_recipients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of recipients"""
        batch_results = []
        
        for recipient in batch_recipients:
            try:
                # Get random wallet for distribution
                wallet = self.tron_utils.get_random_wallet()
                wallet_info = self.tron_utils.get_wallet_info(wallet)
                
                # Check wallet has sufficient ODT balance
                required_amount = recipient['amount']
                available_odt = wallet_info.get('odt_balance', 0)
                
                if available_odt < required_amount:
                    logger.warning(f"Insufficient ODT balance in wallet {wallet['address']}: "
                                 f"{available_odt} < {required_amount}")
                    result = {
                        'recipient_address': recipient['address'],
                        'amount': required_amount,
                        'status': 'FAILED',
                        'error': 'Insufficient wallet balance',
                        'tx_hash': None,
                        'timestamp': datetime.now().isoformat()
                    }
                    batch_results.append(result)
                    self.failed_drops += 1
                    continue
                
                # Safety checks
                amounts = {'odt': required_amount}
                if not self.safety_guard.check_all_guards(
                    "airdrop", 
                    amounts, 
                    wallet_info, 
                    0  # No USD volume for airdrop
                ):
                    logger.warning(f"Safety checks failed for airdrop to {recipient['address']}")
                    result = {
                        'recipient_address': recipient['address'],
                        'amount': required_amount,
                        'status': 'FAILED',
                        'error': 'Safety checks failed',
                        'tx_hash': None,
                        'timestamp': datetime.now().isoformat()
                    }
                    batch_results.append(result)
                    self.failed_drops += 1
                    continue
                
                # Send tokens with retry
                def _send_tokens():
                    return self.send_token(wallet, recipient['address'], required_amount)
                
                tx_hash = self.retry_handler.execute_with_retry(_send_tokens)
                
                # Wait for confirmation
                if self.tron_utils.wait_for_transaction(tx_hash):
                    # Record success
                    self.safety_guard.record_success("airdrop", tx_hash)
                    self.successful_drops += 1
                    self.total_amount_distributed += required_amount
                    
                    # Log transaction
                    self.tron_utils.log_transaction(tx_hash, "airdrop", 
                                                  wallet['address'], {
                        'recipient': recipient['address'],
                        'amount': required_amount,
                        'notes': recipient.get('notes', '')
                    })
                    
                    result = {
                        'recipient_address': recipient['address'],
                        'amount': required_amount,
                        'status': 'SUCCESS',
                        'error': None,
                        'tx_hash': tx_hash,
                        'timestamp': datetime.now().isoformat(),
                        'sender_wallet': wallet['address']
                    }
                    
                    logger.info(f"Successfully sent {required_amount} ODT to {recipient['address']}")
                else:
                    # Record failure
                    self.safety_guard.record_failure("airdrop", "Transaction failed")
                    result = {
                        'recipient_address': recipient['address'],
                        'amount': required_amount,
                        'status': 'FAILED',
                        'error': 'Transaction confirmation failed',
                        'tx_hash': tx_hash,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.failed_drops += 1
                    logger.error(f"Failed to send {required_amount} ODT to {recipient['address']}")
                
                batch_results.append(result)
                
                # Small delay between individual transfers
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                logger.error(f"Error processing recipient {recipient['address']}: {e}")
                result = {
                    'recipient_address': recipient['address'],
                    'amount': recipient['amount'],
                    'status': 'FAILED',
                    'error': str(e),
                    'tx_hash': None,
                    'timestamp': datetime.now().isoformat()
                }
                batch_results.append(result)
                self.failed_drops += 1
        
        return batch_results
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate airdrop summary statistics"""
        success_rate = (self.successful_drops / self.total_recipients * 100) if self.total_recipients > 0 else 0
        
        summary = {
            'total_recipients': self.total_recipients,
            'successful_drops': self.successful_drops,
            'failed_drops': self.failed_drops,
            'success_rate_percent': success_rate,
            'total_amount_distributed': self.total_amount_distributed,
            'average_amount_per_recipient': (self.total_amount_distributed / self.successful_drops) 
                                          if self.successful_drops > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }
        
        return summary
    
    def _save_results_to_csv(self):
        """Save airdrop results to CSV file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"airdrop_results_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as f:
                if self.airdrop_results:
                    fieldnames = self.airdrop_results[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.airdrop_results)
            
            logger.info(f"Airdrop results saved to {filename}")
            
        except Exception as e:
            logger.error(f"Error saving results to CSV: {e}")
    
    def execute_single_airdrop(self, recipient_address: str, amount: float) -> Optional[str]:
        """Execute airdrop to a single recipient"""
        try:
            if not self.tron_utils.is_valid_address(recipient_address):
                logger.error(f"Invalid recipient address: {recipient_address}")
                return None
            
            # Get random wallet
            wallet = self.tron_utils.get_random_wallet()
            wallet_info = self.tron_utils.get_wallet_info(wallet)
            
            # Check wallet balance
            available_odt = wallet_info.get('odt_balance', 0)
            if available_odt < amount:
                logger.error(f"Insufficient ODT balance: {available_odt} < {amount}")
                return None
            
            # Safety checks
            amounts = {'odt': amount}
            if not self.safety_guard.check_all_guards("airdrop", amounts, wallet_info, 0):
                logger.warning("Safety checks failed for single airdrop")
                return None
            
            # Send tokens
            def _send_tokens():
                return self.send_token(wallet, recipient_address, amount)
            
            tx_hash = self.retry_handler.execute_with_retry(_send_tokens)
            
            # Wait for confirmation
            if self.tron_utils.wait_for_transaction(tx_hash):
                self.safety_guard.record_success("airdrop", tx_hash)
                
                # Log transaction
                self.tron_utils.log_transaction(tx_hash, "airdrop", 
                                              wallet['address'], {
                    'recipient': recipient_address,
                    'amount': amount
                })
                
                logger.info(f"Single airdrop successful: {amount} ODT to {recipient_address}")
                return tx_hash
            else:
                self.safety_guard.record_failure("airdrop", "Transaction failed")
                logger.error("Single airdrop failed")
                return None
                
        except Exception as e:
            logger.error(f"Error executing single airdrop: {e}")
            return None
    
    def get_airdrop_status(self) -> Dict[str, Any]:
        """Get current airdrop status"""
        return {
            'total_recipients': self.total_recipients,
            'successful_drops': self.successful_drops,
            'failed_drops': self.failed_drops,
            'total_amount_distributed': self.total_amount_distributed,
            'success_rate_percent': (self.successful_drops / self.total_recipients * 100) 
                                  if self.total_recipients > 0 else 0
        }
    
    def validate_recipients_file(self, csv_file: str) -> Dict[str, Any]:
        """Validate recipients CSV file before airdrop"""
        try:
            recipients = self.load_recipients(csv_file)
            
            validation_results = {
                'total_recipients': len(recipients),
                'valid_addresses': 0,
                'invalid_addresses': 0,
                'total_amount': 0.0,
                'errors': []
            }
            
            for recipient in recipients:
                address = recipient['address']
                amount = recipient['amount']
                
                if self.tron_utils.is_valid_address(address):
                    validation_results['valid_addresses'] += 1
                    validation_results['total_amount'] += amount
                else:
                    validation_results['invalid_addresses'] += 1
                    validation_results['errors'].append(f"Invalid address: {address}")
            
            logger.info(f"Recipients validation completed: {validation_results}")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating recipients file: {e}")
            return {
                'total_recipients': 0,
                'valid_addresses': 0,
                'invalid_addresses': 0,
                'total_amount': 0.0,
                'errors': [str(e)]
            }

class AirdropScheduler:
    """Schedules airdrop operations"""
    
    def __init__(self, airdrop_manager: AirdropManager):
        self.airdrop_manager = airdrop_manager
        self.is_running = False
    
    def schedule_airdrop(self, recipients_file: str, batch_size: int = 10, 
                        delay_between_batches: float = 30.0):
        """Schedule an airdrop operation"""
        try:
            logger.info(f"Scheduling airdrop from {recipients_file}")
            
            # Validate recipients file first
            validation = self.airdrop_manager.validate_recipients_file(recipients_file)
            if validation['invalid_addresses'] > 0:
                logger.warning(f"Found {validation['invalid_addresses']} invalid addresses")
                for error in validation['errors']:
                    logger.warning(f"  - {error}")
            
            # Load recipients
            recipients = self.airdrop_manager.load_recipients(recipients_file)
            
            # Execute airdrop
            results = self.airdrop_manager.execute_airdrop(
                recipients, batch_size, delay_between_batches
            )
            
            logger.info(f"Airdrop completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error scheduling airdrop: {e}")
            raise

def create_airdrop_manager(tron_utils: TronUtils, safety_guard: SafetyGuard, 
                          retry_handler: RetryHandler) -> AirdropManager:
    """Factory function to create airdrop manager"""
    return AirdropManager(tron_utils, safety_guard, retry_handler)

def create_airdrop_scheduler(airdrop_manager: AirdropManager) -> AirdropScheduler:
    """Factory function to create airdrop scheduler"""
    return AirdropScheduler(airdrop_manager)