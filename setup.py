#!/usr/bin/env python3
"""
Setup script for TRON SunSwap Automation Bot
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.9 or higher"""
    if sys.version_info < (3, 9):
        print("❌ Python 3.9 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version}")
    return True

def install_dependencies():
    """Install required dependencies"""
    try:
        print("📦 Installing dependencies...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ["logs", "data", "backups"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 Created directory: {directory}")

def setup_config_files():
    """Setup configuration files from examples"""
    config_files = [
        ("config.example.toml", "config.toml"),
        ("wallets.example.toml", "wallets.toml")
    ]
    
    for example_file, target_file in config_files:
        if not os.path.exists(target_file):
            if os.path.exists(example_file):
                shutil.copy2(example_file, target_file)
                print(f"📋 Created {target_file} from {example_file}")
            else:
                print(f"⚠️  Example file {example_file} not found")
        else:
            print(f"ℹ️  {target_file} already exists")

def create_sample_recipients():
    """Create sample recipients CSV file"""
    recipients_file = "recipients.csv"
    if not os.path.exists(recipients_file):
        sample_content = """address,amount_odt,notes
TQmUqBptCwC3AyqP4pos65rvXuwuz6HoCS,1000.0,Example recipient 1
TExampleAddress123456789012345678901234567890,500.0,Example recipient 2
TAnotherExampleAddress123456789012345678901234,2000.0,Example recipient 3"""
        
        with open(recipients_file, "w") as f:
            f.write(sample_content)
        print(f"📋 Created sample {recipients_file}")

def check_tronpy_installation():
    """Check if tronpy is properly installed"""
    try:
        import tronpy
        print(f"✅ tronpy version: {tronpy.__version__}")
        return True
    except ImportError:
        print("❌ tronpy not installed")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up TRON SunSwap Automation Bot")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Check tronpy installation
    if not check_tronpy_installation():
        print("❌ tronpy installation failed")
        sys.exit(1)
    
    # Setup config files
    setup_config_files()
    
    # Create sample files
    create_sample_recipients()
    
    print("\n" + "=" * 50)
    print("✅ Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit config.toml with your settings")
    print("2. Edit wallets.toml with your private keys")
    print("3. Update ODT contract address in config.toml")
    print("4. Run: python bot.py --help")
    print("\n⚠️  Remember to never commit wallets.toml to version control!")

if __name__ == "__main__":
    main()