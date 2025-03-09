# MarketPulse - AI-Powered Event-Triggered Yield Farming Agent

A decentralized, autonomous AI agent that monitors blockchain events, predicts market impact, and deploys ERC20-based yield farming pools on Polygon.

## Overview

MarketPulse is an innovative solution that:
- Monitors on-chain events on Polygon in real-time
- Uses AI to assess market impact of detected events
- Deploys ERC20 "reaction tokens" using Vyper smart contracts
- Manages liquidity on Quickswap to maximize yield
- Distributes earnings to participants automatically

## Project Structure

```
marketpulse/
├── contracts/                # Vyper smart contracts
│   ├── interfaces/          # Contract interfaces
│   ├── tokens/              # ERC20 token implementation
│   ├── factory/             # Factory contracts using Blueprints
│   ├── vaults/              # Liquidity management vaults
│   └── tests/               # Smart contract tests
├── agents/                  # AI agent components
│   ├── monitor/             # Event monitoring module
│   ├── predictor/           # AI prediction module
│   ├── deployer/            # Token deployment module
│   ├── manager/             # Liquidity management module
│   └── distributor/         # Yield distribution module
├── models/                  # AI models and training scripts
├── data/                    # Data processing and storage
├── api/                     # API for agent interaction
├── scripts/                 # Utility scripts
└── config/                  # Configuration files
```

## Technologies Used

- **Vyper**: For efficient and secure smart contract development
- **Snekmate**: For building ERC20 tokens and other contracts
- **Blueprints**: For implementing factory contracts
- **Polygon**: As the target blockchain
- **Tesseract**: For image recognition and processing
- **OpenAI API**: For AI-driven decision making
- **Quickswap**: For liquidity pool integration
- **Ape/Brownie**: For contract testing and deployment

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 16+
- Vyper
- Polygon node access (via Alchemy, Infura, etc.)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/jintukumardas/marketpulse.git
cd marketpulse
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

4. Compile contracts:
```bash
brownie compile
```

## Features

1. **Event Monitoring**
   - Real-time tracking of on-chain activities
   - Detection of large token swaps, whale movements, and trending contracts

2. **AI Prediction**
   - Market impact assessment using machine learning
   - Prediction of trading volume and price volatility

3. **Token Deployment**
   - ERC20 "reaction tokens" via Vyper smart contracts
   - Each token represents a stake in a yield-farming pool

4. **Liquidity Management**
   - Dynamic adjustment of liquidity on Quickswap
   - Optimization based on AI predictions

5. **Yield Distribution**
   - Proportional reward distribution to participants
   - Automated reinvestment options

## License

This project is licensed under the MIT License - see the LICENSE file for details.