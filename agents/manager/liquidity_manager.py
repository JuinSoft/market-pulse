"""
Liquidity Manager Module

This module is responsible for managing liquidity in Quickswap pools
for the deployed vaults.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from web3 import Web3
from web3.exceptions import ContractLogicError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LiquidityManager:
    """Manage liquidity in Quickswap pools for the deployed vaults."""
    
    def __init__(
        self,
        web3_provider: Optional[str] = None,
        router_address: Optional[str] = None,
        usdc_address: Optional[str] = None,
        private_key: Optional[str] = None,
        gas_price_multiplier: float = 1.1,
        check_interval: int = 3600,  # 1 hour
        min_rebalance_threshold: int = 500  # 5% deviation
    ):
        """
        Initialize the liquidity manager.
        
        Args:
            web3_provider: URL of the Polygon node
            router_address: Address of the Quickswap router
            usdc_address: Address of the USDC token
            private_key: Private key for transactions
            gas_price_multiplier: Multiplier for gas price
            check_interval: Interval between checks (seconds)
            min_rebalance_threshold: Minimum deviation to trigger rebalance (basis points)
        """
        self.web3_provider = web3_provider
        self.router_address = router_address
        self.usdc_address = usdc_address
        self.private_key = private_key
        self.gas_price_multiplier = gas_price_multiplier
        self.check_interval = check_interval
        self.min_rebalance_threshold = min_rebalance_threshold
        
        # Initialize Web3 if provider is given
        if web3_provider:
            self.web3 = Web3(Web3.HTTPProvider(web3_provider))
            
            # Initialize account if private key is given
            if private_key:
                self.account = self.web3.eth.account.from_key(private_key)
                logger.info(f"Initialized account: {self.account.address}")
        
        # Load contract ABIs
        self.router_abi = self._load_router_abi()
        self.vault_abi = self._load_vault_abi()
        
        # Initialize router contract if address is given
        if router_address and web3_provider:
            self.router_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(router_address),
                abi=self.router_abi
            )
            logger.info(f"Initialized router contract at: {router_address}")
        
        # Track managed vaults
        self.managed_vaults = {}
        
        logger.info("LiquidityManager initialized")
    
    def _load_router_abi(self) -> list:
        """Load Quickswap router ABI."""
        # In a real implementation, we would load from file
        # For this example, we'll return a placeholder
        return [
            {
                "inputs": [
                    {"name": "tokenA", "type": "address"},
                    {"name": "tokenB", "type": "address"},
                    {"name": "amountADesired", "type": "uint256"},
                    {"name": "amountBDesired", "type": "uint256"},
                    {"name": "amountAMin", "type": "uint256"},
                    {"name": "amountBMin", "type": "uint256"},
                    {"name": "to", "type": "address"},
                    {"name": "deadline", "type": "uint256"}
                ],
                "name": "addLiquidity",
                "outputs": [
                    {"name": "amountA", "type": "uint256"},
                    {"name": "amountB", "type": "uint256"},
                    {"name": "liquidity", "type": "uint256"}
                ],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "tokenA", "type": "address"},
                    {"name": "tokenB", "type": "address"},
                    {"name": "liquidity", "type": "uint256"},
                    {"name": "amountAMin", "type": "uint256"},
                    {"name": "amountBMin", "type": "uint256"},
                    {"name": "to", "type": "address"},
                    {"name": "deadline", "type": "uint256"}
                ],
                "name": "removeLiquidity",
                "outputs": [
                    {"name": "amountA", "type": "uint256"},
                    {"name": "amountB", "type": "uint256"}
                ],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
    
    def _load_vault_abi(self) -> list:
        """Load EventVault ABI."""
        # In a real implementation, we would load from file
        # For this example, we'll return a placeholder
        return [
            {
                "inputs": [],
                "name": "token",
                "outputs": [{"name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "target_liquidity_percent",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "is_active",
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "_rebalance_liquidity",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "distribute_yield",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
    
    def add_vault(self, vault_address: str, vault_info: Dict[str, Any] = None) -> bool:
        """
        Add a vault to be managed.
        
        Args:
            vault_address: Address of the vault
            vault_info: Information about the vault (optional)
            
        Returns:
            Success boolean
        """
        if not self.web3_provider:
            logger.error("Missing web3 provider")
            return False
        
        try:
            # Initialize vault contract
            vault_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(vault_address),
                abi=self.vault_abi
            )
            
            # Get vault information if not provided
            if vault_info is None:
                token_address = vault_contract.functions.token().call()
                target_liquidity_percent = vault_contract.functions.target_liquidity_percent().call()
                is_active = vault_contract.functions.is_active().call()
                
                vault_info = {
                    'vault_address': vault_address,
                    'token_address': token_address,
                    'target_liquidity_percent': target_liquidity_percent,
                    'is_active': is_active,
                    'last_check': 0,
                    'last_rebalance': 0,
                    'last_yield_distribution': 0
                }
            
            # Add to managed vaults
            self.managed_vaults[vault_address] = {
                'info': vault_info,
                'contract': vault_contract
            }
            
            logger.info(f"Added vault to management: {vault_address}")
            return True
        
        except Exception as e:
            logger.error(f"Error adding vault: {e}", exc_info=True)
            return False
    
    def remove_vault(self, vault_address: str) -> bool:
        """
        Remove a vault from management.
        
        Args:
            vault_address: Address of the vault
            
        Returns:
            Success boolean
        """
        if vault_address in self.managed_vaults:
            del self.managed_vaults[vault_address]
            logger.info(f"Removed vault from management: {vault_address}")
            return True
        else:
            logger.warning(f"Vault not found: {vault_address}")
            return False
    
    def check_and_manage_vaults(self):
        """Check and manage all vaults."""
        logger.info(f"Checking {len(self.managed_vaults)} vaults")
        
        current_time = time.time()
        
        for vault_address, vault_data in list(self.managed_vaults.items()):
            try:
                vault_info = vault_data['info']
                vault_contract = vault_data['contract']
                
                # Skip inactive vaults
                if not vault_info.get('is_active', False):
                    logger.info(f"Skipping inactive vault: {vault_address}")
                    continue
                
                # Check if it's time to check this vault
                last_check = vault_info.get('last_check', 0)
                if current_time - last_check < self.check_interval:
                    logger.debug(f"Skipping check for vault {vault_address} (checked recently)")
                    continue
                
                # Update last check time
                vault_info['last_check'] = current_time
                
                # Check if vault is still active
                try:
                    is_active = vault_contract.functions.is_active().call()
                    vault_info['is_active'] = is_active
                    
                    if not is_active:
                        logger.info(f"Vault is no longer active: {vault_address}")
                        continue
                except Exception as e:
                    logger.error(f"Error checking vault status: {e}")
                    continue
                
                # Check if rebalance is needed
                self._check_and_rebalance_if_needed(vault_address, vault_data)
                
                # Check if yield distribution is needed
                self._check_and_distribute_yield_if_needed(vault_address, vault_data)
                
            except Exception as e:
                logger.error(f"Error managing vault {vault_address}: {e}", exc_info=True)
    
    def _check_and_rebalance_if_needed(self, vault_address: str, vault_data: Dict[str, Any]):
        """
        Check if a vault needs rebalancing and execute if needed.
        
        Args:
            vault_address: Address of the vault
            vault_data: Vault data
        """
        # In a real implementation, we would:
        # 1. Calculate current liquidity allocation
        # 2. Compare with target allocation
        # 3. Rebalance if deviation exceeds threshold
        
        # For this example, we'll just log the action
        logger.info(f"Checking if vault needs rebalancing: {vault_address}")
        
        # Simulate rebalancing
        current_time = time.time()
        vault_data['info']['last_rebalance'] = current_time
        
        logger.info(f"Rebalanced liquidity for vault: {vault_address}")
    
    def _check_and_distribute_yield_if_needed(self, vault_address: str, vault_data: Dict[str, Any]):
        """
        Check if a vault needs yield distribution and execute if needed.
        
        Args:
            vault_address: Address of the vault
            vault_data: Vault data
        """
        # In a real implementation, we would:
        # 1. Check if there's yield to distribute
        # 2. Call distribute_yield if needed
        
        # For this example, we'll just log the action
        logger.info(f"Checking if vault has yield to distribute: {vault_address}")
        
        # Simulate yield distribution
        current_time = time.time()
        vault_data['info']['last_yield_distribution'] = current_time
        
        logger.info(f"Distributed yield for vault: {vault_address}")
    
    async def run_manager_loop(self):
        """Run the liquidity manager loop continuously."""
        logger.info("Starting liquidity manager loop")
        
        while True:
            try:
                self.check_and_manage_vaults()
            except Exception as e:
                logger.error(f"Error in manager loop: {e}", exc_info=True)
            
            # Wait before next iteration
            logger.info(f"Sleeping for {self.check_interval} seconds")
            await asyncio.sleep(self.check_interval)

# For imports to work in the main script
import asyncio 