# TRON SunSwap Automation Bot

A comprehensive Python 3 application for automated trading, liquidity management, and airdrop distribution on the TRON blockchain using SunSwap DEX. This bot is specifically designed for the **Orbit Dollar (ODT)** token.

## 🚀 Features

### Core Functionality
- **Multi-Wallet Support**: Rotate transactions across multiple wallets for realistic activity
- **Automated Trading**: TRX ↔ ODT and USDT ↔ ODT swaps with configurable parameters
- **Liquidity Management**: Add/remove liquidity for ODT/USDT pool
- **Airdrop Distribution**: Send ODT tokens to multiple recipients from CSV files
- **Risk Controls**: Comprehensive safety guards, rate limiting, and transaction validation
- **Real-time Monitoring**: Live statistics and progress tracking

### Target Performance
- **Daily Swap Volume**: ~$250,000 USD
- **Daily Liquidity Operations**: ~$500,000 USD
- **Multi-wallet Rotation**: Realistic transaction patterns
- **Automated Scheduling**: 24/7 operation with configurable trading hours

## 📋 Prerequisites

- Python 3.9 or higher
- TRON mainnet access
- TronLink wallet or compatible TRON wallet
- Sufficient TRX, USDT, and ODT balances across wallets

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tron-sunswap-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create configuration files**
   ```bash
   cp config.example.toml config.toml
   cp wallets.example.toml wallets.toml
   ```

4. **Configure the bot**
   - Edit `config.toml` with your settings
   - Edit `wallets.toml` with your private keys
   - Update contract addresses for your tokens

## ⚙️ Configuration

### config.toml
```toml
[network]
rpc_url = "https://api.trongrid.io"
backup_rpc_urls = ["https://api.tronstack.io"]

[contracts]
router_address = "TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax"
usdt_address = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
odt_address = "YOUR_ODT_CONTRACT_ADDRESS_HERE"
factory_address = "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE"

[risk_controls]
max_tx_size_trx = 1000.0
max_tx_size_usdt = 1000.0
max_tx_size_odt = 1000000.0
slippage_tolerance = 0.01
tx_deadline = 300
min_delay_seconds = 30
max_delay_seconds = 300

[trading]
daily_swap_volume_usd = 250000
daily_liquidity_volume_usd = 500000
min_trade_size_usd = 100
max_trade_size_usd = 5000
trading_start_hour = 0
trading_end_hour = 23
```

### wallets.toml
```toml
[wallets]
wallet_1 = "YOUR_PRIVATE_KEY_HERE"
wallet_2 = "YOUR_PRIVATE_KEY_HERE"
wallet_3 = "YOUR_PRIVATE_KEY_HERE"
wallet_4 = "YOUR_PRIVATE_KEY_HERE"
wallet_5 = "YOUR_PRIVATE_KEY_HERE"

[rotation]
enable_rotation = true
min_balance_trx = 10.0
min_balance_usdt = 100.0
min_balance_odt = 1000.0
```

## 🚀 Usage

### Basic Operation

1. **Start the bot in daemon mode**
   ```bash
   python bot.py --daemon
   ```

2. **Run with custom configuration**
   ```bash
   python bot.py --config custom_config.toml --wallets custom_wallets.toml
   ```

3. **Execute airdrop only**
   ```bash
   python bot.py --airdrop recipients.csv --batch-size 20
   ```

### Command Line Options

```bash
python bot.py [OPTIONS]

Options:
  --config PATH        Configuration file path (default: config.toml)
  --wallets PATH       Wallets file path (default: wallets.toml)
  --log-level LEVEL    Log level: DEBUG, INFO, WARNING, ERROR (default: INFO)
  --airdrop FILE       Execute airdrop from CSV file
  --batch-size SIZE    Airdrop batch size (default: 10)
  --daemon            Run as daemon
  --help              Show help message
```

### Airdrop CSV Format

Create a `recipients.csv` file with the following format:

```csv
address,amount_odt,notes
TQmUqBptCwC3AyqP4pos65rvXuwuz6HoCS,1000.0,Example recipient 1
TExampleAddress123456789012345678901234567890,500.0,Example recipient 2
TAnotherExampleAddress123456789012345678901234,2000.0,Example recipient 3
```

## 📊 Monitoring

### Real-time Statistics
The bot provides comprehensive monitoring through logs and status reports:

- **Daily Progress**: Swap and liquidity volume progress
- **Operation Counts**: Successful and failed transactions
- **Wallet Status**: Balance and health of all wallets
- **Error Tracking**: Detailed error logs and retry attempts

### Log Files
- **Main Log**: `logs/bot.log` - All bot activities
- **Transaction Log**: Embedded in main log with transaction details
- **Airdrop Results**: `airdrop_results_YYYYMMDD_HHMMSS.csv`

### Status Monitoring
```python
# Get bot status programmatically
from bot import SunSwapBot

bot = SunSwapBot()
bot.initialize()
status = bot.get_bot_status()
print(status)
```

## 🔒 Security Features

### Risk Controls
- **Transaction Size Limits**: Maximum amounts per transaction type
- **Rate Limiting**: Minimum delays between transactions
- **Circuit Breaker**: Automatic shutdown on consecutive failures
- **Balance Validation**: Ensures sufficient funds before transactions
- **Slippage Protection**: Configurable slippage tolerance

### Wallet Security
- **Private Key Protection**: Keys stored only in `wallets.toml`
- **Multi-wallet Rotation**: Distributes risk across multiple wallets
- **Balance Monitoring**: Continuous wallet health checks
- **Approval Management**: Automatic token approval handling

### Configuration Security
- **Gitignore Protection**: Sensitive files excluded from version control
- **Environment Isolation**: Separate config files for different environments
- **Log Sanitization**: No private keys in logs

## 🏗️ Architecture

### Core Components

```
bot.py                    # Main entry point
├── utils_tron.py         # TRON blockchain utilities
├── modules/
│   ├── guards.py         # Risk controls and safety
│   ├── swaps.py          # Trading operations
│   ├── liquidity.py      # Liquidity management
│   └── airdrop.py        # Token distribution
├── config.toml           # Configuration (create from example)
├── wallets.toml          # Private keys (create from example)
└── logs/                 # Log files
```

### Module Responsibilities

- **TronUtils**: Blockchain interactions, wallet management, contract operations
- **Guards**: Risk controls, rate limiting, transaction validation
- **Swaps**: TRX/ODT and USDT/ODT trading with SunSwap
- **Liquidity**: Add/remove liquidity for ODT/USDT pool
- **Airdrop**: Batch token distribution to multiple recipients

## 📈 Performance Optimization

### Daily Targets
- **Swap Volume**: $250,000 USD across multiple trades
- **Liquidity Operations**: $500,000 USD in add/remove operations
- **Transaction Distribution**: Randomized amounts and timing
- **Wallet Rotation**: Even distribution across available wallets

### Optimization Features
- **Parallel Processing**: Multiple operation threads
- **Intelligent Scheduling**: Random delays to avoid patterns
- **Retry Logic**: Exponential backoff for failed transactions
- **Gas Optimization**: Efficient transaction batching

## 🐛 Troubleshooting

### Common Issues

1. **"No active wallets found"**
   - Check wallet balances meet minimum requirements
   - Verify private keys are correctly formatted
   - Ensure wallets have sufficient TRX for gas

2. **"Transaction failed"**
   - Check network connectivity
   - Verify contract addresses are correct
   - Ensure sufficient token approvals

3. **"Rate limiting"**
   - Bot is working correctly - wait for next transaction
   - Adjust `min_delay_seconds` in config if needed

4. **"Safety checks failed"**
   - Transaction exceeds configured limits
   - Check wallet balances and transaction amounts
   - Review risk control settings

### Debug Mode
```bash
python bot.py --log-level DEBUG
```

### Log Analysis
```bash
# View recent logs
tail -f logs/bot.log

# Search for errors
grep "ERROR" logs/bot.log

# Monitor specific operations
grep "swap\|liquidity\|airdrop" logs/bot.log
```

## 🔧 Customization

### Adding New Trading Pairs
1. Update contract addresses in `config.toml`
2. Modify swap paths in `modules/swaps.py`
3. Add price feeds for new tokens

### Adjusting Risk Controls
1. Modify limits in `config.toml`
2. Update validation logic in `modules/guards.py`
3. Test with small amounts first

### Custom Airdrop Logic
1. Extend `modules/airdrop.py`
2. Add new CSV formats
3. Implement custom distribution patterns

## 📝 API Reference

### SunSwapBot Class
```python
class SunSwapBot:
    def __init__(self, config_path: str, wallets_path: str)
    def initialize(self) -> bool
    def start_automated_trading(self) -> bool
    def stop_automated_trading(self) -> bool
    def execute_airdrop(self, recipients_file: str, batch_size: int) -> Dict
    def get_bot_status(self) -> Dict
    def shutdown(self)
```

### TronUtils Class
```python
class TronUtils:
    def get_random_wallet(self) -> Dict
    def get_trx_balance(self, address: str) -> float
    def get_token_balance(self, address: str, token: str) -> float
    def send_token(self, wallet: Dict, recipient: str, amount: float) -> str
    def wait_for_transaction(self, tx_hash: str) -> bool
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## ⚠️ Disclaimer

This software is provided for educational and research purposes. Trading cryptocurrencies involves substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this software. Always test with small amounts first and understand the risks involved.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review logs for error details

---

**Orbit Dollar (ODT) Token Information:**
- **Symbol**: ODT
- **Decimals**: 18
- **Network**: TRC20 (TRON mainnet)
- **Pool**: ODT/USDT on SunSwap
- **Contract**: Update in config.toml with actual address