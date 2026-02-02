# Bitcoin Relay 🔗

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Bitcoin](https://img.shields.io/badge/Bitcoin-Testnet%20%7C%20Mainnet-orange.svg)](https://bitcoin.org)

A personal Bitcoin privacy tool that autonomously relays your funds through multiple intermediate addresses with Fibonacci-paced timing delays.

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
- **🔄 Auto-recovery** — Engine automatically recovers stuck transactions
- **📊 Real-time status** — Live balance updates every 10 seconds
- **🌐 Web interface** — Clean, dark-themed dashboard
- **🧪 Testnet support** — Test safely before using real funds

## 🚀 Quick Start

### One-liner Install (Linux/Mac)

```bash
git clone https://github.com/TheMimitProject/Bitcoinrelay.git && cd Bitcoinrelay/bitcoin-relay && chmod +x run.sh && ./run.sh
```

### Step-by-Step

```bash
# Clone the repository
git clone https://github.com/TheMimitProject/Bitcoinrelay.git

# Navigate to the project
cd Bitcoinrelay/bitcoin-relay

# Make run script executable
chmod +x run.sh

# Run it
./run.sh
```

Then open **http://localhost:5000** in your browser.

### Windows

```cmd
git clone https://github.com/TheMimitProject/Bitcoinrelay.git
cd Bitcoinrelay\bitcoin-relay
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m src.app
```

## 📖 Usage

### First-Time Setup

1. Open `http://localhost:5000`
2. Create a master password (minimum 8 characters)
3. **⚠️ WRITE THIS PASSWORD DOWN** — it cannot be recovered!
4. Stay on **Testnet** (default) until you've tested

### Creating a Relay Chain

1. Click **"Show Form"** under Create New Relay Chain
2. Configure:
   - **Name:** Any name you want
   - **Hops:** 2-10 intermediate addresses
   - **Fee Priority:** Affects confirmation speed
   - **Final Destination:** Generate new or use your own address
3. Click **"Create Chain"**
4. **Copy the intake address**
5. Click on the chain → **"Activate"**
6. Send funds to the intake address

### Monitoring

The relay engine automatically:
- Detects incoming funds (checks every 30 seconds)
- Relays through each hop when confirmed
- Updates UI in real-time (every 10 seconds)
- Recovers stuck transactions automatically

### Recovery Options

If a chain gets stuck:
- **Retry/Fix Button** — Manually triggers all pending relays
- **Sync Status Button** — Updates database to match blockchain state

## ⏱️ Fibonacci Delays

| Hop | Delay (blocks) | ~Time |
|-----|---------------|-------|
| 1   | 1             | 10 min |
| 2   | 1             | 10 min |
| 3   | 2             | 20 min |
| 4   | 3             | 30 min |
| 5   | 5             | 50 min |
| 6   | 8             | 80 min |

## 🔐 Security

| Component | Protection |
|-----------|------------|
| Private Keys | AES-256-GCM encryption |
| Key Derivation | PBKDF2 with 480,000 iterations |
| Master Password | SHA-256 hashed with salt |
| Storage | Local SQLite database only |

Your private keys **never leave your machine** unencrypted.

## 📁 Project Structure

```
bitcoin-relay/
├── src/
│   ├── app.py              # Flask application & API
│   ├── bitcoin_utils.py    # Bitcoin operations
│   ├── database.py         # SQLite operations
│   ├── encryption.py       # Key encryption
│   ├── config.py           # Configuration
│   └── relay_engine.py     # Background relay worker
├── templates/
│   └── index.html          # Web interface
├── requirements.txt
├── run.sh
└── README.md
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/setup` | POST | Set master password |
| `/api/auth/login` | POST | Login |
| `/api/network` | GET/POST | Get/set network |
| `/api/chains` | GET/POST | List/create chains |
| `/api/chains/<id>/activate` | POST | Activate chain |
| `/api/chains/<id>/retry` | POST | Retry stuck chain |
| `/api/chains/<id>/fix-status` | POST | Sync with blockchain |
| `/api/chains/<id>/export` | GET | Export keys |
| `/api/status` | GET | Engine status |

## ⚠️ Important Warnings

> **🧪 TEST ON TESTNET FIRST**  
> Always test with testnet before using mainnet.

> **🔑 BACKUP YOUR PASSWORD**  
> Your master password cannot be recovered.

> **💾 EXPORT YOUR KEYS**  
> Always backup keys before sending significant funds.

> **💸 UNDERSTAND THE FEES**  
> Each hop incurs a transaction fee (~200 sats each).

## 🧪 Testnet Faucets

- [mempool.space Faucet](https://testnet-faucet.mempool.co/)
- [coinfaucet.eu](https://coinfaucet.eu/en/btc-testnet/)
- [bitcoinfaucet.uo1.net](https://bitcoinfaucet.uo1.net/)

## 🛠️ Troubleshooting

**Port 5000 in use (Mac)**
```bash
lsof -ti:5000 | xargs kill -9
./run.sh
```

**Chain stuck / not relaying**
1. Click on the chain
2. Click "Retry/Fix" button
3. Or click "Sync Status" to update database

**Password not working**
- Make sure you're using the password you set during setup
- If you forgot it, delete `relay.db` and start fresh

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## ⚖️ Disclaimer

This tool is for educational and personal privacy purposes only. Users are responsible for complying with laws in their jurisdiction and securing their own funds.
