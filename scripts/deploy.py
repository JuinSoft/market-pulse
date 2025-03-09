"""
Deploy Script for MarketPulse Contracts

This script deploys the MarketPulse contracts to the Polygon network.
"""

import os
import json
import argparse
import logging
from brownie import (
    network,
    accounts,
    config,
    project,
    ReactionToken,
    EventVault,
    VaultFactory
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_account(index=None, id=None):
    """
    Get a brownie account for deployment.
    
    Args:
        index: Index of the local account to use
        id: ID of a saved account to use
    
    Returns:
        A brownie account
    """
    if index:
        return accounts[index]
    if id:
        return accounts.load(id)
    if (
        network.show_active() in ["development", "ganache-local", "hardhat", "mainnet-fork"]
    ):
        return accounts[0]
    return accounts.add(config["wallets"]["from_key"])

def deploy_token_blueprint():
    """Deploy the ReactionToken blueprint."""
    logger.info("Deploying ReactionToken blueprint")
    account = get_account()
    
    # Deploy the blueprint
    token_blueprint = ReactionToken.deploy(
        {"from": account},
        publish_source=config["networks"][network.show_active()].get("verify", False)
    )
    
    logger.info(f"ReactionToken blueprint deployed at: {token_blueprint.address}")
    return token_blueprint

def deploy_vault_blueprint():
    """Deploy the EventVault blueprint."""
    logger.info("Deploying EventVault blueprint")
    account = get_account()
    
    # Deploy the blueprint
    vault_blueprint = EventVault.deploy(
        {"from": account},
        publish_source=config["networks"][network.show_active()].get("verify", False)
    )
    
    logger.info(f"EventVault blueprint deployed at: {vault_blueprint.address}")
    return vault_blueprint

def deploy_factory(token_blueprint, vault_blueprint, treasury, treasury_fee, usdc, router):
    """
    Deploy the VaultFactory contract.
    
    Args:
        token_blueprint: Address of the ReactionToken blueprint
        vault_blueprint: Address of the EventVault blueprint
        treasury: Address of the treasury
        treasury_fee: Treasury fee in basis points
        usdc: Address of the USDC token
        router: Address of the Quickswap router
    """
    logger.info("Deploying VaultFactory")
    account = get_account()
    
    # Deploy the factory
    factory = VaultFactory.deploy(
        treasury,
        treasury_fee,
        usdc,
        router,
        vault_blueprint.address,
        token_blueprint.address,
        {"from": account},
        publish_source=config["networks"][network.show_active()].get("verify", False)
    )
    
    logger.info(f"VaultFactory deployed at: {factory.address}")
    return factory

def save_contract_addresses(addresses, filename="contract_addresses.json"):
    """
    Save deployed contract addresses to a file.
    
    Args:
        addresses: Dict of contract addresses
        filename: Name of the file to save to
    """
    # Ensure the data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Save addresses to file
    with open(f"data/{filename}", "w") as f:
        json.dump(addresses, f, indent=4)
    
    logger.info(f"Contract addresses saved to data/{filename}")

def main(args):
    """Main deployment function."""
    # Configure network
    network.connect(args.network)
    logger.info(f"Connected to network: {network.show_active()}")
    
    # Deploy blueprints
    token_blueprint = deploy_token_blueprint()
    vault_blueprint = deploy_vault_blueprint()
    
    # Deploy factory
    factory = deploy_factory(
        token_blueprint,
        vault_blueprint,
        args.treasury,
        args.treasury_fee,
        args.usdc,
        args.router
    )
    
    # Save addresses
    addresses = {
        "network": network.show_active(),
        "token_blueprint": token_blueprint.address,
        "vault_blueprint": vault_blueprint.address,
        "factory": factory.address
    }
    save_contract_addresses(addresses)
    
    # Return addresses for programmatic use
    return addresses

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy MarketPulse contracts")
    parser.add_argument("--network", default="polygon-main", help="Network to deploy to")
    parser.add_argument("--treasury", required=True, help="Treasury address")
    parser.add_argument("--treasury-fee", type=int, default=50, help="Treasury fee in basis points")
    parser.add_argument(
        "--usdc",
        default="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        help="USDC address on Polygon"
    )
    parser.add_argument(
        "--router",
        default="0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
        help="Quickswap router address on Polygon"
    )
    
    args = parser.parse_args()
    main(args) 