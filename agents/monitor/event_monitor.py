"""
Event Monitor Module

This module is responsible for monitoring blockchain events on the Polygon network.
It detects significant on-chain activities like large token swaps, whale wallet 
transactions, or trending contracts.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any, Tuple
from web3 import Web3
from web3.contract import Contract
from web3.types import EventData, FilterParams, BlockData
import pandas as pd
import time
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EventMonitor:
    """Monitor blockchain events on Polygon."""
    
    def __init__(
        self, 
        web3_provider: str,
        quickswap_router_address: str,
        usdc_address: str,
        min_swap_value_usd: float = 100000.0,  # $100k minimum for "large" swaps
        min_wallet_value_usd: float = 1000000.0,  # $1M minimum for "whale" wallets
        trend_threshold: int = 10,  # Number of transactions to consider "trending"
        polling_interval: int = 15,  # Seconds between checks
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        Initialize the event monitor.
        
        Args:
            web3_provider: URL of the Polygon node
            quickswap_router_address: Address of the Quickswap router
            usdc_address: Address of the USDC token
            min_swap_value_usd: Minimum USD value for a swap to be considered "large"
            min_wallet_value_usd: Minimum USD value for a wallet to be considered a "whale"
            trend_threshold: Number of transactions to consider a contract "trending"
            polling_interval: Seconds between checks
            event_callback: Function to call when an event is detected
        """
        self.web3 = Web3(Web3.HTTPProvider(web3_provider))
        
        # Validate connection
        if not self.web3.is_connected():
            raise ConnectionError(f"Failed to connect to {web3_provider}")
        
        self.quickswap_router_address = Web3.to_checksum_address(quickswap_router_address)
        self.usdc_address = Web3.to_checksum_address(usdc_address)
        
        # Load contract ABIs
        self.router_abi = self._load_abi('quickswap_router')
        self.erc20_abi = self._load_abi('erc20')
        
        # Initialize contracts
        self.router_contract = self.web3.eth.contract(
            address=self.quickswap_router_address, 
            abi=self.router_abi
        )
        self.usdc_contract = self.web3.eth.contract(
            address=self.usdc_address,
            abi=self.erc20_abi
        )
        
        # Configuration
        self.min_swap_value_usd = min_swap_value_usd
        self.min_wallet_value_usd = min_wallet_value_usd
        self.trend_threshold = trend_threshold
        self.polling_interval = polling_interval
        self.event_callback = event_callback
        
        # State
        self.latest_processed_block = self.web3.eth.block_number
        self.transaction_count = {}  # Track transaction counts per contract
        self.swap_events = []  # Store recent swap events
        self.whale_movements = []  # Store recent whale movements
        self.trending_contracts = []  # Store recently trending contracts
        
        logger.info(f"EventMonitor initialized, connected to Polygon at block {self.latest_processed_block}")
    
    def _load_abi(self, name: str) -> List[Dict[str, Any]]:
        """Load contract ABI from file."""
        # In a real implementation, we would load from files
        # For this example, we'll return minimal ABIs
        
        if name == 'quickswap_router':
            return [
                {
                    "inputs": [
                        {"name": "amountIn", "type": "uint256"},
                        {"name": "path", "type": "address[]"}
                    ],
                    "name": "getAmountsOut",
                    "outputs": [{"name": "amounts", "type": "uint256[]"}],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {"indexed": True, "name": "sender", "type": "address"},
                        {"indexed": False, "name": "amount0In", "type": "uint256"},
                        {"indexed": False, "name": "amount1In", "type": "uint256"},
                        {"indexed": False, "name": "amount0Out", "type": "uint256"},
                        {"indexed": False, "name": "amount1Out", "type": "uint256"},
                        {"indexed": True, "name": "to", "type": "address"}
                    ],
                    "name": "Swap",
                    "type": "event"
                }
            ]
        elif name == 'erc20':
            return [
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "anonymous": False,
                    "inputs": [
                        {"indexed": True, "name": "from", "type": "address"},
                        {"indexed": True, "name": "to", "type": "address"},
                        {"indexed": False, "name": "value", "type": "uint256"}
                    ],
                    "name": "Transfer",
                    "type": "event"
                }
            ]
        else:
            raise ValueError(f"Unknown ABI: {name}")
    
    async def start_monitoring(self):
        """Start monitoring blockchain events."""
        logger.info("Starting blockchain event monitoring")
        
        while True:
            try:
                # Process new blocks
                current_block = self.web3.eth.block_number
                if current_block > self.latest_processed_block:
                    logger.info(f"Processing blocks {self.latest_processed_block + 1} to {current_block}")
                    
                    for block_num in range(self.latest_processed_block + 1, current_block + 1):
                        await self._process_block(block_num)
                    
                    self.latest_processed_block = current_block
                
                # Check for trending contracts
                self._identify_trending_contracts()
                
                # Clean up old data
                self._cleanup_old_data()
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
            
            # Wait before next iteration
            await asyncio.sleep(self.polling_interval)
    
    async def _process_block(self, block_number: int):
        """Process a single block for events."""
        logger.debug(f"Processing block {block_number}")
        
        # Get block data
        block = self.web3.eth.get_block(block_number, full_transactions=True)
        
        # Process each transaction
        for tx in block.transactions:
            # Update transaction count for the recipient contract
            if tx.to:
                if tx.to not in self.transaction_count:
                    self.transaction_count[tx.to] = 0
                self.transaction_count[tx.to] += 1
            
            # Check for token swaps
            if tx.to == self.quickswap_router_address:
                swap_event = self._check_for_swap(tx, block)
                if swap_event:
                    logger.info(f"Large swap detected: {swap_event}")
                    self.swap_events.append(swap_event)
                    if self.event_callback:
                        self.event_callback({
                            "type": "large_swap",
                            "data": swap_event
                        })
            
            # Check for whale movements
            whale_event = self._check_for_whale_movement(tx, block)
            if whale_event:
                logger.info(f"Whale movement detected: {whale_event}")
                self.whale_movements.append(whale_event)
                if self.event_callback:
                    self.event_callback({
                        "type": "whale_movement",
                        "data": whale_event
                    })
    
    def _check_for_swap(self, tx, block) -> Optional[Dict[str, Any]]:
        """Check if a transaction is a large token swap."""
        # In a real implementation, we would parse the transaction input data
        # and check logs to identify swaps and their amounts
        
        # For this example, we'll use a simplified approach
        # Assume we're looking at method signature for swapExactTokensForTokens
        
        # Return None since this is just a placeholder implementation
        return None
    
    def _check_for_whale_movement(self, tx, block) -> Optional[Dict[str, Any]]:
        """Check if a transaction is a whale movement."""
        # A whale movement is a large transfer of tokens
        
        # In a real implementation, we would check token transfer events
        # and look for large values
        
        # Return None since this is just a placeholder implementation
        return None
    
    def _identify_trending_contracts(self):
        """Identify trending contracts based on transaction count."""
        # Find contracts with transaction counts above threshold
        trending = []
        
        for contract_addr, count in self.transaction_count.items():
            if count >= self.trend_threshold:
                trend_data = {
                    "contract_address": contract_addr,
                    "transaction_count": count,
                    "timestamp": datetime.now().isoformat()
                }
                trending.append(trend_data)
                
                # Only notify for new trending contracts
                if contract_addr not in [t["contract_address"] for t in self.trending_contracts]:
                    logger.info(f"Trending contract detected: {trend_data}")
                    if self.event_callback:
                        self.event_callback({
                            "type": "trending_contract",
                            "data": trend_data
                        })
        
        self.trending_contracts = trending
    
    def _cleanup_old_data(self):
        """Clean up old event data."""
        # Keep only recent events (last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        cutoff_str = cutoff_time.isoformat()
        
        self.swap_events = [e for e in self.swap_events 
                           if e.get("timestamp", "") > cutoff_str]
        
        self.whale_movements = [e for e in self.whale_movements 
                               if e.get("timestamp", "") > cutoff_str]
        
        self.trending_contracts = [e for e in self.trending_contracts 
                                  if e.get("timestamp", "") > cutoff_str]
        
        # Reset transaction counts periodically (every 24 hours)
        # In a real implementation, we would use a timestamp-based approach
        self.transaction_count = {}
    
    def get_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent events, optionally filtered by type."""
        if event_type == "large_swap":
            return self.swap_events
        elif event_type == "whale_movement":
            return self.whale_movements
        elif event_type == "trending_contract":
            return self.trending_contracts
        else:
            # Return all events
            return (
                [{"type": "large_swap", **e} for e in self.swap_events] +
                [{"type": "whale_movement", **e} for e in self.whale_movements] +
                [{"type": "trending_contract", **e} for e in self.trending_contracts]
            )


# Example usage
async def example_callback(event):
    """Example callback function for events."""
    print(f"Event detected: {event['type']}")
    print(f"Data: {event['data']}")


async def main():
    """Example usage of EventMonitor."""
    # Replace with actual values
    web3_provider = "https://polygon-rpc.com"
    quickswap_router = "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff"
    usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    
    monitor = EventMonitor(
        web3_provider=web3_provider,
        quickswap_router_address=quickswap_router,
        usdc_address=usdc_address,
        event_callback=example_callback
    )
    
    await monitor.start_monitoring()


if __name__ == "__main__":
    # Run the example
    asyncio.run(main()) 