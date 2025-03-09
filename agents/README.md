# MarketPulse AI Agents

This directory contains the AI agent components for the MarketPulse system.

## Agent Architecture

The MarketPulse agent architecture consists of the following components:

1. **Event Monitor (monitor/event_monitor.py)**
   - Continuously tracks on-chain activities on Polygon
   - Detects large token swaps, whale wallet transactions, and trending contracts
   - Filters events based on configurable thresholds

2. **AI Predictor (predictor/ai_predictor.py)**
   - Uses OpenAI's API to assess the market impact of detected events
   - Predicts price impact, trading volume increase, and volatility
   - Determines if an event is significant enough to deploy a vault

3. **Token Deployer (deployer/token_deployer.py)**
   - Deploys ERC20 "reaction tokens" via the VaultFactory contract
   - Manages transaction retries and confirmations
   - Tracks successful deployments

4. **Liquidity Manager (manager/liquidity_manager.py)**
   - Manages liquidity in Quickswap pools for deployed vaults
   - Dynamically adjusts liquidity based on AI predictions
   - Monitors and redistributes yields

5. **Yield Distributor (distributor/)**
   - Distributes trading fees (yields) to reaction token holders
   - Manages automated reinvestment options
   - Tracks yield distribution history

## Directory Structure

```
agents/
├── monitor/      # Event monitoring module
├── predictor/    # AI prediction module
├── deployer/     # Token deployment module
├── manager/      # Liquidity management module
└── distributor/  # Yield distribution module
```

## Integration with OpenAI

The AI Predictor component integrates with OpenAI's API to provide intelligent market impact assessments. The integration:

1. Sends event data to the OpenAI API with a structured prompt
2. Processes the response to extract predictions
3. Caches predictions to minimize API calls
4. Includes fallback mechanisms for API failures

## Configuration

Agent behavior is configured through the `config/config.json` file, which includes:

- Blockchain connection parameters
- Event detection thresholds
- AI model settings
- Liquidity management parameters

## Orchestration

The agents are orchestrated by the main script (`main.py`), which:

1. Initializes all agent components
2. Manages event flow between components
3. Handles errors and retries
4. Provides logging and monitoring

## Requirements

See `requirements.txt` for the Python dependencies required to run the agents. 