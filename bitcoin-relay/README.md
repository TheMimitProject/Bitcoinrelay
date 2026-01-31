# Bitcoin Relay 🔗

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Bitcoin](https://img.shields.io/badge/Bitcoin-Testnet%20%7C%20Mainnet-orange.svg)](https://bitcoin.org)

A personal Bitcoin privacy tool that autonomously relays your funds through multiple intermediate addresses with Fibonacci-paced timing delays.

<p align="center">
  <img src="docs/images/dashboard-preview.png" alt="Dashboard Preview" width="800">
</p>

```
    ┌──────────┐      ┌───────┐      ┌───────┐      ┌───────┐      ┌───────────┐
    │  Intake  │ ───▶ │ Hop 1 │ ───▶ │ Hop 2 │ ───▶ │ Hop 3 │ ───▶ │   Final   │
    │ Address  │      │(1 blk)│      │(1 blk)│      │(2 blk)│      │Destination│
    └──────────┘      └───────┘      └───────┘      └───────┘      └───────────┘
```

## ✨ Features

- **🔢 Fibonacci-paced delays** — Hops occur at 1, 1, 2, 3, 5, 8... block intervals
- **🔐 Encrypted key storage** — AES-256-GCM with PBKDF2 key derivation
- **🏠 Self-hosted** — Runs entirely on your machine, no third parties
- **📊 Fee estimation** — Know your costs before committing
- **🔄 Autonomous operation** — Set it and forget it
- **🌐 Web interface** — Clean, dark-themed dashboard
- **🧪 Testnet support** — Test safely before using real funds
- **💾 Key export** — Full backup capability for all generated keys

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Internet connection (for blockchain API access)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/bitcoin-relay.git
cd bitcoin-relay

# Run the application
chmod +x run.sh
./run.sh
```

The script will automatically:
1. Create a virtual environment
2. Install dependencies
3. Initialize the database
4. Start the web server

Then open **http://localhost:5000** in your browser.

### Manual Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

## 📖 Usage

### First-Time Setup

1. Open the web interface at `http://localhost:5000`
2. Create a master password (minimum 8 characters)
3. **⚠️ WRITE THIS PASSWORD DOWN** — it cannot be recovered!
4. Start on **TESTNET** (selected by default)

### Creating a Relay Chain

1. Click "Show Form" in the Create New Relay Chain section
2. Set your desired number of hops (2-10)
3. Choose fee priority (affects confirmation speed)
4. Choose destination type:
   - **Generate new address** (recommended) — keys stored encrypted
   - **Use my own address** — provide your existing address
5. Review the fee and timing estimate
6. Click "Create Chain"
7. **Copy the intake address**
8. Click on the chain and "Activate" it
9. Send funds to the intake address

### Monitoring

Once activated, the relay engine automatically:
- Monitors the intake address for incoming funds
- Waits for confirmations
- Relays through each hop with Fibonacci delays
- Sends final amount to destination

## 🔧 How It Works

### Fibonacci Delays

Each hop waits a Fibonacci number of blocks before relaying:

| Hop | Delay (blocks) | ~Time |
|-----|---------------|-------|
| 1   | 1             | 10 min |
| 2   | 1             | 10 min |
| 3   | 2             | 20 min |
| 4   | 3             | 30 min |
| 5   | 5             | 50 min |
| 6   | 8             | 80 min |
| 7   | 13            | 2+ hrs |

This creates a non-linear timing pattern that helps break temporal analysis.

### Security Model

| Component | Protection |
|-----------|------------|
| Private Keys | AES-256-GCM encryption |
| Key Derivation | PBKDF2 with 480,000 iterations |
| Master Password | SHA-256 hashed with salt |
| Session | Secure random tokens |
| Network | Uses public blockchain APIs only |

Your private keys **never leave your machine** unencrypted.

## 📁 Project Structure

```
bitcoin-relay/
├── src/
│   ├── __init__.py
│   ├── app.py              # Flask application & API routes
│   ├── bitcoin_utils.py    # Bitcoin operations
│   ├── database.py         # SQLite operations
│   ├── encryption.py       # Key encryption
│   ├── config.py           # Configuration
│   └── relay_engine.py     # Background relay worker
├── templates/
│   └── index.html          # Web interface
├── static/                 # Static assets
├── docs/
│   ├── API.md              # API documentation
│   └── images/             # Documentation images
├── tests/
│   └── test_core.py        # Unit tests
├── requirements.txt
├── run.sh
├── LICENSE
└── README.md
```

## 🔌 API Reference

See [docs/API.md](docs/API.md) for complete API documentation.

### Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Authenticate |
| `/api/network` | GET/POST | Get/set network |
| `/api/fees/estimate` | POST | Estimate fees |
| `/api/chains` | GET/POST | List/create chains |
| `/api/chains/<id>/activate` | POST | Activate chain |
| `/api/chains/<id>/export` | GET | Export keys |

## ⚠️ Important Warnings

> **🧪 TEST ON TESTNET FIRST**  
> Always test with testnet before using mainnet. Get testnet BTC from faucets listed below.

> **🔑 BACKUP YOUR PASSWORD**  
> Your master password cannot be recovered. If you lose it, you lose access to all encrypted keys.

> **💾 EXPORT YOUR KEYS**  
> Always export and backup keys for generated addresses before sending significant funds.

> **💸 UNDERSTAND THE FEES**  
> Each hop incurs a transaction fee. With 5 hops, you pay 6 transaction fees total.

> **⏱️ TIMING IS VARIABLE**  
> Block times average 10 minutes but can vary significantly.

## 🧪 Testnet Resources

Get testnet Bitcoin for testing:

- [mempool.space Testnet Faucet](https://testnet-faucet.mempool.co/)
- [coinfaucet.eu](https://coinfaucet.eu/en/btc-testnet/)
- [Bitcoin Testnet Faucet](https://bitcoinfaucet.uo1.net/)

## 🛠️ Troubleshooting

<details>
<summary><strong>Engine not starting</strong></summary>

- Check your internet connection
- Verify API access to blockstream.info
- Check console for error messages
</details>

<details>
<summary><strong>Transaction failed</strong></summary>

- Insufficient funds (need amount + all hop fees)
- Amount below dust threshold (~546 sats)
- Network congestion (try higher fee priority)
</details>

<details>
<summary><strong>Decryption failed</strong></summary>

- Wrong password entered
- Database may be corrupted (restore from backup)
</details>

<details>
<summary><strong>Address marked invalid</strong></summary>

- Using wrong network (testnet address on mainnet or vice versa)
- Typo in the address
</details>

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚖️ Disclaimer

This tool is provided for educational and personal privacy purposes only. The author is not responsible for any loss of funds, legal issues, or other problems arising from use of this software. 

**Users are responsible for:**
- Understanding and complying with laws in their jurisdiction
- Securing their master password and key backups
- Testing thoroughly before using with significant funds
- Understanding Bitcoin transaction mechanics and fees

## 🙏 Acknowledgments

- [bit](https://github.com/ofek/bit) — Bitcoin library for Python
- [Flask](https://flask.palletsprojects.com/) — Web framework
- [Blockstream](https://blockstream.info/) — Blockchain API
- [mempool.space](https://mempool.space/) — Fee estimation API
