#!/usr/bin/env python3
"""
TRON SunSwap Automation Bot - Main Entry Point
Orbit Dollar (ODT) Token Trading and Liquidity Management Bot
"""

import os
import sys
import time
import signal
import logging
import argparse
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils_tron import TronUtils
from modules.guards import create_safety_guard, create_retry_handler
from modules.swaps import create_swap_manager, create_swap_scheduler
from modules.liquidity import create_liquidity_manager, create_liquidity_scheduler
from modules.airdrop import create_airdrop_manager, create_airdrop_scheduler

# Configure logging
def setup_logging(log_level: str = "INFO", log_file: str = "logs/bot.log"):
    """Setup logging configuration"""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    
    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger

class SunSwapBot:
    """Main bot class that coordinates all operations"""
    
    def __init__(self, config_path: str = "config.toml", wallets_path: str = "wallets.toml"):
        """Initialize the bot with configuration"""
        self.config_path = config_path
        self.wallets_path = wallets_path
        
        # Initialize components
        self.tron_utils = None
        self.safety_guard = None
        self.retry_handler = None
        self.swap_manager = None
        self.liquidity_manager = None
        self.airdrop_manager = None
        
        # Schedulers
        self.swap_scheduler = None
        self.liquidity_scheduler = None
        self.airdrop_scheduler = None
        
        # Control flags
        self.is_running = False
        self.threads = []
        
        # Statistics
        self.start_time = None
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0
        
    def initialize(self):
        """Initialize all bot components"""
        try:
            logger.info("Initializing TRON SunSwap Automation Bot...")
            
            # Initialize TRON utilities
            logger.info("Initializing TRON utilities...")
            self.tron_utils = TronUtils(self.config_path, self.wallets_path)
            
            # Initialize safety guard
            logger.info("Initializing safety guard...")
            self.safety_guard = create_safety_guard(self.tron_utils.config)
            
            # Initialize retry handler
            logger.info("Initializing retry handler...")
            self.retry_handler = create_retry_handler(self.tron_utils.config)
            
            # Initialize managers
            logger.info("Initializing swap manager...")
            self.swap_manager = create_swap_manager(self.tron_utils, self.safety_guard, self.retry_handler)
            
            logger.info("Initializing liquidity manager...")
            self.liquidity_manager = create_liquidity_manager(self.tron_utils, self.safety_guard, self.retry_handler)
            
            logger.info("Initializing airdrop manager...")
            self.airdrop_manager = create_airdrop_manager(self.tron_utils, self.safety_guard, self.retry_handler)
            
            # Initialize schedulers
            logger.info("Initializing schedulers...")
            self.swap_scheduler = create_swap_scheduler(self.swap_manager)
            self.liquidity_scheduler = create_liquidity_scheduler(self.liquidity_manager)
            self.airdrop_scheduler = create_airdrop_scheduler(self.airdrop_manager)
            
            logger.info("Bot initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing bot: {e}")
            return False
    
    def start_automated_trading(self):
        """Start automated trading operations"""
        try:
            if not self.is_running:
                logger.info("Starting automated trading operations...")
                self.is_running = True
                self.start_time = datetime.now()
                
                # Start swap trading in separate thread
                swap_thread = threading.Thread(target=self._run_swap_trading, daemon=True)
                swap_thread.start()
                self.threads.append(swap_thread)
                
                # Start liquidity operations in separate thread
                liquidity_thread = threading.Thread(target=self._run_liquidity_operations, daemon=True)
                liquidity_thread.start()
                self.threads.append(liquidity_thread)
                
                # Start monitoring thread
                monitor_thread = threading.Thread(target=self._run_monitoring, daemon=True)
                monitor_thread.start()
                self.threads.append(monitor_thread)
                
                logger.info("Automated trading started successfully")
                return True
            else:
                logger.warning("Bot is already running")
                return False
                
        except Exception as e:
            logger.error(f"Error starting automated trading: {e}")
            return False
    
    def stop_automated_trading(self):
        """Stop automated trading operations"""
        try:
            if self.is_running:
                logger.info("Stopping automated trading operations...")
                self.is_running = False
                
                # Stop schedulers
                if self.swap_scheduler:
                    self.swap_scheduler.stop_trading()
                if self.liquidity_scheduler:
                    self.liquidity_scheduler.stop_trading()
                
                # Wait for threads to finish
                for thread in self.threads:
                    if thread.is_alive():
                        thread.join(timeout=10)
                
                logger.info("Automated trading stopped")
                return True
            else:
                logger.warning("Bot is not running")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping automated trading: {e}")
            return False
    
    def _run_swap_trading(self):
        """Run swap trading operations"""
        try:
            logger.info("Starting swap trading thread...")
            self.swap_scheduler.start_trading()
        except Exception as e:
            logger.error(f"Error in swap trading thread: {e}")
    
    def _run_liquidity_operations(self):
        """Run liquidity operations"""
        try:
            logger.info("Starting liquidity operations thread...")
            self.liquidity_scheduler.start_trading()
        except Exception as e:
            logger.error(f"Error in liquidity operations thread: {e}")
    
    def _run_monitoring(self):
        """Run monitoring and statistics collection"""
        try:
            logger.info("Starting monitoring thread...")
            
            while self.is_running:
                try:
                    # Collect statistics
                    self._collect_statistics()
                    
                    # Log progress
                    self._log_progress()
                    
                    # Check if we should reset daily stats
                    self._check_daily_reset()
                    
                    # Wait before next monitoring cycle
                    time.sleep(300)  # 5 minutes
                    
                except Exception as e:
                    logger.error(f"Error in monitoring thread: {e}")
                    time.sleep(60)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"Error in monitoring thread: {e}")
    
    def _collect_statistics(self):
        """Collect and update statistics"""
        try:
            # Get swap statistics
            swap_progress = self.swap_manager.get_daily_progress()
            
            # Get liquidity statistics
            liquidity_progress = self.liquidity_manager.get_daily_progress()
            
            # Get airdrop statistics
            airdrop_status = self.airdrop_manager.get_airdrop_status()
            
            # Update bot statistics
            self.total_operations = (
                swap_progress['swap_count'] + 
                liquidity_progress['add_operations'] + 
                liquidity_progress['remove_operations'] +
                airdrop_status['successful_drops']
            )
            
            self.successful_operations = (
                swap_progress['swap_count'] + 
                liquidity_progress['add_operations'] + 
                liquidity_progress['remove_operations'] +
                airdrop_status['successful_drops']
            )
            
        except Exception as e:
            logger.error(f"Error collecting statistics: {e}")
    
    def _log_progress(self):
        """Log current progress"""
        try:
            if not self.is_running:
                return
            
            # Get current progress
            swap_progress = self.swap_manager.get_daily_progress()
            liquidity_progress = self.liquidity_manager.get_daily_progress()
            
            # Calculate uptime
            uptime = datetime.now() - self.start_time if self.start_time else timedelta(0)
            
            logger.info("=== BOT STATUS ===")
            logger.info(f"Uptime: {uptime}")
            logger.info(f"Total Operations: {self.total_operations}")
            logger.info(f"Successful Operations: {self.successful_operations}")
            logger.info(f"Failed Operations: {self.failed_operations}")
            logger.info(f"Swap Progress: {swap_progress['progress_percent']:.1f}% "
                       f"({swap_progress['volume_usd']:.2f}/{swap_progress['target_volume_usd']:.2f} USD)")
            logger.info(f"Liquidity Progress: {liquidity_progress['progress_percent']:.1f}% "
                       f"({liquidity_progress['volume_usd']:.2f}/{liquidity_progress['target_volume_usd']:.2f} USD)")
            logger.info("==================")
            
        except Exception as e:
            logger.error(f"Error logging progress: {e}")
    
    def _check_daily_reset(self):
        """Check if daily statistics should be reset"""
        try:
            current_hour = datetime.now().hour
            if current_hour == 0:  # Reset at midnight
                logger.info("Resetting daily statistics...")
                self.swap_manager.reset_daily_stats()
                self.liquidity_manager.reset_daily_stats()
                self.airdrop_manager = create_airdrop_manager(
                    self.tron_utils, self.safety_guard, self.retry_handler
                )
                logger.info("Daily statistics reset completed")
        except Exception as e:
            logger.error(f"Error checking daily reset: {e}")
    
    def execute_airdrop(self, recipients_file: str, batch_size: int = 10) -> Dict[str, Any]:
        """Execute airdrop operation"""
        try:
            logger.info(f"Executing airdrop from {recipients_file}")
            
            # Validate file exists
            if not os.path.exists(recipients_file):
                raise FileNotFoundError(f"Recipients file not found: {recipients_file}")
            
            # Execute airdrop
            results = self.airdrop_scheduler.schedule_airdrop(recipients_file, batch_size)
            
            logger.info(f"Airdrop completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error executing airdrop: {e}")
            raise
    
    def get_bot_status(self) -> Dict[str, Any]:
        """Get comprehensive bot status"""
        try:
            status = {
                'is_running': self.is_running,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
                'total_operations': self.total_operations,
                'successful_operations': self.successful_operations,
                'failed_operations': self.failed_operations,
                'active_wallets': len(self.tron_utils.active_wallets) if self.tron_utils else 0,
                'swap_progress': self.swap_manager.get_daily_progress() if self.swap_manager else {},
                'liquidity_progress': self.liquidity_manager.get_daily_progress() if self.liquidity_manager else {},
                'airdrop_status': self.airdrop_manager.get_airdrop_status() if self.airdrop_manager else {}
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting bot status: {e}")
            return {'error': str(e)}
    
    def shutdown(self):
        """Gracefully shutdown the bot"""
        try:
            logger.info("Shutting down bot...")
            
            # Stop automated trading
            self.stop_automated_trading()
            
            # Save final statistics
            self._collect_statistics()
            self._log_progress()
            
            logger.info("Bot shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    if 'bot' in globals():
        bot.shutdown()
    sys.exit(0)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='TRON SunSwap Automation Bot')
    parser.add_argument('--config', default='config.toml', help='Configuration file path')
    parser.add_argument('--wallets', default='wallets.toml', help='Wallets file path')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Log level')
    parser.add_argument('--airdrop', help='Execute airdrop from CSV file')
    parser.add_argument('--batch-size', type=int, default=10, help='Airdrop batch size')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.log_level)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize bot
        bot = SunSwapBot(args.config, args.wallets)
        
        if not bot.initialize():
            logger.error("Failed to initialize bot")
            sys.exit(1)
        
        # Handle airdrop mode
        if args.airdrop:
            logger.info(f"Executing airdrop from {args.airdrop}")
            results = bot.execute_airdrop(args.airdrop, args.batch_size)
            print(json.dumps(results, indent=2))
            return
        
        # Start automated trading
        if not bot.start_automated_trading():
            logger.error("Failed to start automated trading")
            sys.exit(1)
        
        # Keep running
        if args.daemon:
            logger.info("Running as daemon...")
            while True:
                time.sleep(60)
        else:
            logger.info("Press Ctrl+C to stop the bot")
            while bot.is_running:
                time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        if 'bot' in locals():
            bot.shutdown()

if __name__ == "__main__":
    main()