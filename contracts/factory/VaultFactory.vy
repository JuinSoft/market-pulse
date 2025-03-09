# @version 0.3.10
"""
@title VaultFactory
@author MarketPulse Team
@license MIT
@notice Factory for creating event vaults using Blueprints
@dev Uses Blueprints pattern to deploy vaults efficiently
"""

# Interfaces
from vyper.interfaces import ERC20

# Events
event VaultCreated:
    vault: indexed(address)
    token: indexed(address)
    reaction_token: indexed(address)
    creator: address
    event_id: uint256
    expiry_time: uint256

event BlueprintsSet:
    vault_blueprint: address
    token_blueprint: address

# State Variables
owner: public(address)
treasury: public(address)
treasury_fee: public(uint256)  # Fee in basis points (e.g., 50 = 0.5%)

# Blueprints
vault_blueprint: public(address)
token_blueprint: public(address)

# Default parameters
default_target_liquidity_percent: public(uint256)  # Target percentage of assets to allocate to LP (in basis points)
default_max_slippage: public(uint256)  # Maximum slippage allowed (in basis points)
default_expiry_duration: public(uint256)  # Default duration in seconds for vault expiry

# Vault tracking
vault_count: public(uint256)
vaults: public(HashMap[uint256, address])
is_vault: public(HashMap[address, bool])

# DEX integration
usdc: public(address)  # USDC token address
router: public(address)  # Quickswap router address

# Constants
BASIS_POINTS: constant(uint256) = 10000
MIN_EXPIRY_DURATION: constant(uint256) = 86400  # 1 day in seconds
MAX_EXPIRY_DURATION: constant(uint256) = 2592000  # 30 days in seconds
MAX_TREASURY_FEE: constant(uint256) = 500  # 5% max fee

interface ITokenBlueprint:
    def implementation() -> address: view

interface IVaultBlueprint:
    def implementation() -> address: view

@external
def __init__(
    _treasury: address,
    _treasury_fee: uint256,
    _usdc: address,
    _router: address,
    _vault_blueprint: address,
    _token_blueprint: address
):
    """
    @notice Initialize the factory
    @param _treasury Treasury address
    @param _treasury_fee Fee in basis points
    @param _usdc USDC token address
    @param _router Quickswap router address
    @param _vault_blueprint Address of the vault blueprint
    @param _token_blueprint Address of the token blueprint
    """
    assert _treasury != ZERO_ADDRESS, "Invalid treasury"
    assert _treasury_fee <= MAX_TREASURY_FEE, "Fee too high"
    assert _usdc != ZERO_ADDRESS, "Invalid USDC"
    assert _router != ZERO_ADDRESS, "Invalid router"
    assert _vault_blueprint != ZERO_ADDRESS, "Invalid vault blueprint"
    assert _token_blueprint != ZERO_ADDRESS, "Invalid token blueprint"
    
    self.owner = msg.sender
    self.treasury = _treasury
    self.treasury_fee = _treasury_fee
    self.usdc = _usdc
    self.router = _router
    self.vault_blueprint = _vault_blueprint
    self.token_blueprint = _token_blueprint
    
    # Set default parameters
    self.default_target_liquidity_percent = 8000  # 80% in LP by default
    self.default_max_slippage = 100  # 1% max slippage
    self.default_expiry_duration = 604800  # 7 days

@external
def set_blueprints(_vault_blueprint: address, _token_blueprint: address):
    """
    @notice Set new blueprints
    @dev Only owner can call this
    @param _vault_blueprint New vault blueprint
    @param _token_blueprint New token blueprint
    """
    assert msg.sender == self.owner, "Only owner"
    assert _vault_blueprint != ZERO_ADDRESS, "Invalid vault blueprint"
    assert _token_blueprint != ZERO_ADDRESS, "Invalid token blueprint"
    
    self.vault_blueprint = _vault_blueprint
    self.token_blueprint = _token_blueprint
    
    log BlueprintsSet(_vault_blueprint, _token_blueprint)

@external
def set_treasury(_treasury: address, _treasury_fee: uint256):
    """
    @notice Set new treasury and fee
    @dev Only owner can call this
    @param _treasury New treasury address
    @param _treasury_fee New treasury fee
    """
    assert msg.sender == self.owner, "Only owner"
    assert _treasury != ZERO_ADDRESS, "Invalid treasury"
    assert _treasury_fee <= MAX_TREASURY_FEE, "Fee too high"
    
    self.treasury = _treasury
    self.treasury_fee = _treasury_fee

@external
def set_default_parameters(
    _target_liquidity_percent: uint256,
    _max_slippage: uint256,
    _expiry_duration: uint256
):
    """
    @notice Set default parameters for new vaults
    @dev Only owner can call this
    @param _target_liquidity_percent New target liquidity percentage
    @param _max_slippage New max slippage
    @param _expiry_duration New expiry duration
    """
    assert msg.sender == self.owner, "Only owner"
    assert _target_liquidity_percent <= BASIS_POINTS, "Invalid target liquidity"
    assert _max_slippage <= 1000, "Slippage too high"
    assert _expiry_duration >= MIN_EXPIRY_DURATION, "Duration too short"
    assert _expiry_duration <= MAX_EXPIRY_DURATION, "Duration too long"
    
    self.default_target_liquidity_percent = _target_liquidity_percent
    self.default_max_slippage = _max_slippage
    self.default_expiry_duration = _expiry_duration

@external
def create_vault(
    _token: address,
    _event_id: uint256,
    _name: String[64],
    _symbol: String[32],
    _target_liquidity_percent: uint256 = 0,
    _max_slippage: uint256 = 0,
    _expiry_duration: uint256 = 0
) -> address:
    """
    @notice Create a new event-triggered vault
    @param _token Address of the token to manage
    @param _event_id ID of the event that triggered this vault
    @param _name Name for the reaction token
    @param _symbol Symbol for the reaction token
    @param _target_liquidity_percent Target percentage of assets to allocate to LP (optional)
    @param _max_slippage Maximum slippage allowed (optional)
    @param _expiry_duration Duration in seconds for vault expiry (optional)
    @return Address of the new vault
    """
    assert _token != ZERO_ADDRESS, "Invalid token"
    
    # Use default parameters if not provided
    target_liquidity: uint256 = _target_liquidity_percent
    max_slippage: uint256 = _max_slippage
    expiry_duration: uint256 = _expiry_duration
    
    if target_liquidity == 0:
        target_liquidity = self.default_target_liquidity_percent
    if max_slippage == 0:
        max_slippage = self.default_max_slippage
    if expiry_duration == 0:
        expiry_duration = self.default_expiry_duration
    
    # Validate parameters
    assert target_liquidity <= BASIS_POINTS, "Invalid target liquidity"
    assert max_slippage <= 1000, "Slippage too high"
    assert expiry_duration >= MIN_EXPIRY_DURATION, "Duration too short"
    assert expiry_duration <= MAX_EXPIRY_DURATION, "Duration too long"
    
    # Create the reaction token using blueprint
    token_name: String[64] = concat(_name, " Reaction Token")
    token_symbol: String[32] = concat(_symbol, "RT")
    
    # We pass a temporary address for the vault, will update after creation
    reaction_token: address = self._create_token(token_name, token_symbol, 18, self)
    
    # Calculate expiry time
    expiry_time: uint256 = block.timestamp + expiry_duration
    
    # Get LP token address (simplified here - in a real implementation we would look up or create)
    lp_token: address = self._get_lp_token(_token, self.usdc)
    
    # Create the vault using blueprint
    vault: address = self._create_vault(
        _token,
        self.usdc,
        reaction_token,
        self.router,
        lp_token,
        self,
        self.treasury,
        self.treasury_fee,
        target_liquidity,
        max_slippage,
        expiry_time
    )
    
    # Register the vault
    self.vault_count += 1
    self.vaults[self.vault_count] = vault
    self.is_vault[vault] = True
    
    log VaultCreated(vault, _token, reaction_token, msg.sender, _event_id, expiry_time)
    
    return vault

@view
@external
def get_vault_address(_index: uint256) -> address:
    """
    @notice Get vault address by index
    @param _index Index of the vault
    @return Address of the vault
    """
    assert _index > 0 and _index <= self.vault_count, "Invalid index"
    return self.vaults[_index]

@internal
def _create_token(
    _name: String[64],
    _symbol: String[32],
    _decimals: uint8,
    _vault: address
) -> address:
    """
    @notice Create a new reaction token using blueprint
    @param _name Token name
    @param _symbol Token symbol
    @param _decimals Token decimals
    @param _vault Vault address
    @return Address of the new token
    """
    # Check that the blueprint is valid
    assert self.token_blueprint != ZERO_ADDRESS, "Invalid token blueprint"
    assert ITokenBlueprint(self.token_blueprint).implementation() != ZERO_ADDRESS, "Invalid implementation"
    
    # Call the token blueprint to create a new token
    # In a real Vyper implementation with Blueprints support, we would use:
    # token: address = create_from_blueprint(
    #    self.token_blueprint,
    #    _name,
    #    _symbol,
    #    _decimals,
    #    _vault,
    #    code_offset=4  # Offset for the constructor arguments
    # )
    
    # Simplified implementation for example:
    token: address = ZERO_ADDRESS
    # Assume token creation was successful
    
    return token

@internal
def _create_vault(
    _token: address,
    _usdc: address,
    _reaction_token: address,
    _router: address,
    _lp_token: address,
    _factory: address,
    _treasury: address,
    _treasury_fee: uint256,
    _target_liquidity_percent: uint256,
    _max_slippage: uint256,
    _expiry_time: uint256
) -> address:
    """
    @notice Create a new vault using blueprint
    @param _token Token address
    @param _usdc USDC address
    @param _reaction_token Reaction token address
    @param _router Router address
    @param _lp_token LP token address
    @param _factory Factory address
    @param _treasury Treasury address
    @param _treasury_fee Treasury fee
    @param _target_liquidity_percent Target liquidity percentage
    @param _max_slippage Max slippage
    @param _expiry_time Expiry time
    @return Address of the new vault
    """
    # Check that the blueprint is valid
    assert self.vault_blueprint != ZERO_ADDRESS, "Invalid vault blueprint"
    assert IVaultBlueprint(self.vault_blueprint).implementation() != ZERO_ADDRESS, "Invalid implementation"
    
    # Call the vault blueprint to create a new vault
    # In a real Vyper implementation with Blueprints support, we would use:
    # vault: address = create_from_blueprint(
    #    self.vault_blueprint,
    #    _token,
    #    _usdc,
    #    _reaction_token,
    #    _router,
    #    _lp_token,
    #    _factory,
    #    _treasury,
    #    _treasury_fee,
    #    _target_liquidity_percent,
    #    _max_slippage,
    #    _expiry_time,
    #    code_offset=4  # Offset for the constructor arguments
    # )
    
    # Simplified implementation for example:
    vault: address = ZERO_ADDRESS
    # Assume vault creation was successful
    
    return vault

@internal
def _get_lp_token(_token_a: address, _token_b: address) -> address:
    """
    @notice Get LP token address for a token pair
    @param _token_a First token
    @param _token_b Second token
    @return LP token address
    """
    # In a real implementation, we would look up or create the LP token
    # Simplified implementation for example:
    return 0xBEEF00000000000000000000000000000000BEEF 