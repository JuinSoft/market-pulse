# MarketPulse Smart Contracts

This directory contains the Vyper smart contracts for the MarketPulse system.

## Contract Architecture

The MarketPulse contract architecture consists of the following components:

1. **ReactionToken (tokens/ReactionToken.vy)**
   - ERC20 token that represents a stake in a yield-farming pool
   - Implements Snekmate modules for compliance with the ERC20 standard
   - Includes minting and burning functionality controlled by the vault

2. **EventVault (vaults/EventVault.vy)**
   - Manages liquidity for event-triggered yield farming
   - Handles deposits, withdrawals, and LP management on Quickswap
   - Implements yield distribution to token holders

3. **VaultFactory (factory/VaultFactory.vy)**
   - Creates new vaults for specific events
   - Uses Blueprints pattern for efficient deployment
   - Manages parameters for created vaults

## Directory Structure

```
contracts/
├── interfaces/    # Interface definitions
├── tokens/        # ERC20 token implementations
├── factory/       # Factory contracts for deployment
├── vaults/        # Vault contracts for liquidity management
└── tests/         # Contract tests
```

## Deployment

The contracts are deployed in the following order:
1. ReactionToken blueprint
2. EventVault blueprint
3. VaultFactory

See the `scripts/deploy.py` script for deployment details.

## Testing

Contract tests are in the `tests/` directory. Run them with:

```bash
brownie test
```

## Integrations

- **Quickswap**: Used for liquidity pools and swaps
- **Snekmate**: Used for ERC20 implementation
- **Blueprints**: Used for efficient contract deployment 