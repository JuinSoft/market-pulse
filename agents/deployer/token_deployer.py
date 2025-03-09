"""
Token Deployer Module

This module is responsible for deploying ERC20 "reaction tokens" and vaults
through the VaultFactory contract on Polygon.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from web3 import Web3
from web3.exceptions import ContractLogicError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TokenDeployer:
    """Deploy tokens and vaults through the VaultFactory contract."""
    
    def __init__(
        self,
        web3_provider: Optional[str] = None,
        factory_address: Optional[str] = None,
        private_key: Optional[str] = None,
        gas_price_multiplier: float = 1.1,
        max_retries: int = 3
    ):
        """
        Initialize the token deployer.
        
        Args:
            web3_provider: URL of the Polygon node
            factory_address: Address of the VaultFactory contract
            private_key: Private key for transactions
            gas_price_multiplier: Multiplier for gas price
            max_retries: Maximum number of retries for failed transactions
        """
        self.web3_provider = web3_provider
        self.factory_address = factory_address
        self.private_key = private_key
        self.gas_price_multiplier = gas_price_multiplier
        self.max_retries = max_retries
        
        # Initialize Web3 if provider is given
        if web3_provider:
            self.web3 = Web3(Web3.HTTPProvider(web3_provider))
            
            # Initialize account if private key is given
            if private_key:
                self.account = self.web3.eth.account.from_key(private_key)
                logger.info(f"Initialized account: {self.account.address}")
        
        # Load factory ABI
        self.factory_abi = self._load_factory_abi()
        
        # Initialize factory contract if address is given
        if factory_address and web3_provider:
            self.factory_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(factory_address),
                abi=self.factory_abi
            )
            logger.info(f"Initialized factory contract at: {factory_address}")
        
        logger.info("TokenDeployer initialized")
    
    def _load_factory_abi(self) -> list:
        """Load factory contract ABI."""
        # In a real implementation, we would load from file
        # For this example, we'll return a placeholder
        return [
            {
                "inputs": [
                    {"name": "_token", "type": "address"},
                    {"name": "_event_id", "type": "uint256"},
                    {"name": "_name", "type": "string"},
                    {"name": "_symbol", "type": "string"},
                    {"name": "_target_liquidity_percent", "type": "uint256"},
                    {"name": "_max_slippage", "type": "uint256"},
                    {"name": "_expiry_duration", "type": "uint256"}
                ],
                "name": "create_vault",
                "outputs": [{"name": "", "type": "address"}],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
    
    def deploy_vault(
        self,
        token_address: str,
        event_id: int,
        name: str,
        symbol: str,
        target_liquidity_percent: int = 8000,  # 80% default
        max_slippage: int = 100,  # 1% default
        expiry_duration: int = 604800  # 7 days default
    ) -> Optional[Dict[str, Any]]:
        """
        Deploy a new vault through the factory.
        
        Args:
            token_address: Address of the token to manage
            event_id: ID of the event that triggered this vault
            name: Name for the reaction token
            symbol: Symbol for the reaction token
            target_liquidity_percent: Target percentage of assets to allocate to LP
            max_slippage: Maximum slippage allowed
            expiry_duration: Duration in seconds for vault expiry
            
        Returns:
            Information about the deployed vault, or None if deployment failed
        """
        if not self.web3_provider or not self.factory_address or not self.private_key:
            logger.error("Missing required configuration")
            return None
        
        try:
            # Prepare transaction
            tx = self.factory_contract.functions.create_vault(
                Web3.to_checksum_address(token_address),
                event_id,
                name,
                symbol,
                target_liquidity_percent,
                max_slippage,
                expiry_duration
            ).build_transaction({
                'from': self.account.address,
                'gas': 3000000,  # Gas limit
                'gasPrice': int(self.web3.eth.gas_price * self.gas_price_multiplier),
                'nonce': self.web3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send transaction
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Vault deployment transaction sent: {tx_hash.hex()}")
            
            # Wait for transaction receipt
            tx_receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            if tx_receipt.status == 1:
                # Extract vault address from event logs
                vault_address = self._extract_vault_address(tx_receipt)
                
                if vault_address:
                    logger.info(f"Vault deployed successfully at: {vault_address}")
                    
                    # Return deployment info
                    return {
                        'tx_hash': tx_hash.hex(),
                        'vault_address': vault_address,
                        'name': name,
                        'symbol': symbol,
                        'token_address': token_address,
                        'event_id': event_id
                    }
                else:
                    logger.error("Failed to extract vault address from transaction receipt")
            else:
                logger.error(f"Vault deployment failed: {tx_receipt}")
            
            return None
        
        except ContractLogicError as e:
            logger.error(f"Contract logic error: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Error deploying vault: {e}", exc_info=True)
            return None
    
    def _extract_vault_address(self, tx_receipt) -> Optional[str]:
        """Extract vault address from transaction receipt."""
        # In a real implementation, we would parse the VaultCreated event
        # For this example, we'll return a placeholder
        return "0x0000000000000000000000000000000000000000"
    
    def get_vault_info(self, vault_address: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a deployed vault.
        
        Args:
            vault_address: Address of the vault
        
        Returns:
            Information about the vault, or None if retrieval failed
        """
        # In a real implementation, we would query the vault contract
        # For this example, we'll return a placeholder
        return {
            'vault_address': vault_address,
            'token_address': "0x0000000000000000000000000000000000000000",
            'name': "Placeholder",
            'symbol': "PLHDR"
        } 