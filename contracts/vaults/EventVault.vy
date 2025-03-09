# @version 0.3.10
"""
@title EventVault
@author MarketPulse Team
@license MIT
@notice Vault that manages liquidity for event-triggered yield farming
@dev Handles deposits, withdrawals, and LP management on Quickswap
"""

# Interfaces
from vyper.interfaces import ERC20

# Import interfaces
interface ReactionToken:
    def mint(_to: address, _value: uint256) -> bool: nonpayable
    def burn(_from: address, _value: uint256) -> bool: nonpayable
    def totalSupply() -> uint256: view
    def balanceOf(_owner: address) -> uint256: view
    def decimals() -> uint8: view

interface IQuickswapRouter:
    def addLiquidity(
        tokenA: address,
        tokenB: address,
        amountADesired: uint256,
        amountBDesired: uint256,
        amountAMin: uint256,
        amountBMin: uint256,
        to: address,
        deadline: uint256
    ) -> (uint256, uint256, uint256): nonpayable
    
    def removeLiquidity(
        tokenA: address,
        tokenB: address,
        liquidity: uint256,
        amountAMin: uint256,
        amountBMin: uint256,
        to: address,
        deadline: uint256
    ) -> (uint256, uint256): nonpayable

    def getAmountsOut(
        amountIn: uint256,
        path: DynArray[address, 2]
    ) -> DynArray[uint256, 2]: view

interface IQuickswapPair:
    def token0() -> address: view
    def token1() -> address: view
    def getReserves() -> (uint112, uint112, uint32): view
    def totalSupply() -> uint256: view
    def balanceOf(owner: address) -> uint256: view

# Events
event Deposit:
    user: indexed(address)
    token_amount: uint256
    shares_minted: uint256

event Withdraw:
    user: indexed(address)
    token_amount: uint256
    shares_burned: uint256

event LiquidityAdded:
    token_amount: uint256
    usdc_amount: uint256
    lp_amount: uint256

event LiquidityRemoved:
    lp_amount: uint256
    token_amount: uint256
    usdc_amount: uint256

event YieldDistributed:
    amount: uint256
    timestamp: uint256

# State Variables
token: public(address)  # The ERC20 token this vault manages
usdc: public(address)   # USDC token address
reaction_token: public(address)  # The ReactionToken for this vault
router: public(address)  # Quickswap router address
lp_token: public(address)  # Quickswap LP token address

factory: public(address)  # Factory that created this vault
owner: public(address)    # Owner of the vault (the AI agent)

# Treasury takes a small fee for the protocol
treasury: public(address)
treasury_fee: public(uint256)  # Fee in basis points (e.g., 50 = 0.5%)

# Liquidity management settings
target_liquidity_percent: public(uint256)  # Target percentage of assets to allocate to LP (in basis points)
max_slippage: public(uint256)  # Maximum slippage allowed (in basis points)

# Lifecycle
is_active: public(bool)  # Whether the vault is actively accepting deposits
expiry_time: public(uint256)  # Time when the vault will stop accepting deposits

# Constants
BASIS_POINTS: constant(uint256) = 10000
USDC_DECIMALS: constant(uint8) = 6
MAX_DEADLINE: constant(uint256) = 2**256 - 1

@external
def __init__(
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
):
    """
    @notice Initialize the vault
    @param _token Address of the token this vault manages
    @param _usdc USDC token address
    @param _reaction_token Address of the ReactionToken for this vault
    @param _router Quickswap router address
    @param _lp_token Quickswap LP token address
    @param _factory Address of the factory that created this vault
    @param _treasury Treasury address
    @param _treasury_fee Fee in basis points
    @param _target_liquidity_percent Target percentage of assets to allocate to LP (in basis points)
    @param _max_slippage Maximum slippage allowed (in basis points)
    @param _expiry_time Time when the vault will stop accepting deposits
    """
    self.token = _token
    self.usdc = _usdc
    self.reaction_token = _reaction_token
    self.router = _router
    self.lp_token = _lp_token
    self.factory = _factory
    self.owner = msg.sender
    self.treasury = _treasury
    self.treasury_fee = _treasury_fee
    self.target_liquidity_percent = _target_liquidity_percent
    self.max_slippage = _max_slippage
    self.expiry_time = _expiry_time
    self.is_active = True

@external
def deposit(_amount: uint256) -> uint256:
    """
    @notice Deposit tokens into the vault
    @param _amount Amount of tokens to deposit
    @return Shares minted
    """
    assert self.is_active, "Vault is not active"
    assert block.timestamp < self.expiry_time, "Vault has expired"
    assert _amount > 0, "Cannot deposit 0"
    
    # Transfer tokens from user to vault
    assert ERC20(self.token).transferFrom(msg.sender, self, _amount), "Token transfer failed"
    
    # Calculate shares to mint
    shares_to_mint: uint256 = 0
    token_supply: uint256 = ReactionToken(self.reaction_token).totalSupply()
    
    if token_supply == 0:
        shares_to_mint = _amount
    else:
        # Calculate proportional share based on vault's total holdings
        total_assets: uint256 = self._total_assets()
        shares_to_mint = (_amount * token_supply) / total_assets
    
    # Mint reaction tokens to the user
    assert ReactionToken(self.reaction_token).mint(msg.sender, shares_to_mint), "Minting failed"
    
    # Rebalance liquidity if needed
    self._rebalance_liquidity()
    
    log Deposit(msg.sender, _amount, shares_to_mint)
    return shares_to_mint

@external
def withdraw(_shares: uint256) -> uint256:
    """
    @notice Withdraw tokens by burning shares
    @param _shares Amount of shares to burn
    @return Amount of tokens returned
    """
    assert _shares > 0, "Cannot withdraw 0"
    assert ReactionToken(self.reaction_token).balanceOf(msg.sender) >= _shares, "Insufficient shares"
    
    token_supply: uint256 = ReactionToken(self.reaction_token).totalSupply()
    assert token_supply > 0, "No supply"
    
    # Calculate tokens to withdraw
    total_assets: uint256 = self._total_assets()
    tokens_to_withdraw: uint256 = (_shares * total_assets) / token_supply
    
    # Calculate fee
    fee_amount: uint256 = (tokens_to_withdraw * self.treasury_fee) / BASIS_POINTS
    tokens_to_withdraw -= fee_amount
    
    # Ensure we have enough non-LP tokens, remove liquidity if needed
    vault_token_balance: uint256 = ERC20(self.token).balanceOf(self)
    if vault_token_balance < tokens_to_withdraw:
        # Remove some liquidity
        self._remove_liquidity_if_needed(tokens_to_withdraw - vault_token_balance)
    
    # Burn reaction tokens
    assert ReactionToken(self.reaction_token).burn(msg.sender, _shares), "Burning failed"
    
    # Transfer tokens to user
    assert ERC20(self.token).transfer(msg.sender, tokens_to_withdraw), "Token transfer failed"
    
    # Transfer fee to treasury
    if fee_amount > 0:
        assert ERC20(self.token).transfer(self.treasury, fee_amount), "Fee transfer failed"
    
    log Withdraw(msg.sender, tokens_to_withdraw, _shares)
    return tokens_to_withdraw

@external
def distribute_yield() -> uint256:
    """
    @notice Distribute yield to reaction token holders
    @dev Only owner can call this
    @return Amount of yield distributed
    """
    assert msg.sender == self.owner, "Only owner"
    
    # Calculate yield as the increase in total assets since last distribution
    # Simplified for this example - in a real implementation, we'd track previous totals
    yield_amount: uint256 = self._calculate_yield()
    assert yield_amount > 0, "No yield to distribute"
    
    # For this example, we distribute yield by adding more liquidity
    # In a real implementation, we could distribute directly to users
    self._add_liquidity_to_pool(yield_amount)
    
    log YieldDistributed(yield_amount, block.timestamp)
    return yield_amount

@external
def deactivate():
    """
    @notice Deactivate the vault
    @dev Only owner can call this
    """
    assert msg.sender == self.owner, "Only owner"
    self.is_active = False

@internal
def _total_assets() -> uint256:
    """
    @notice Calculate total assets managed by this vault
    @return Total asset value in token units
    """
    # Token balance directly held by vault
    token_balance: uint256 = ERC20(self.token).balanceOf(self)
    
    # Token balance in LP position
    lp_balance: uint256 = ERC20(self.lp_token).balanceOf(self)
    
    if lp_balance > 0:
        # Get the reserves from the LP token
        reserve0: uint112 = 0
        reserve1: uint112 = 0
        timestamp: uint32 = 0
        reserve0, reserve1, timestamp = IQuickswapPair(self.lp_token).getReserves()
        
        # Determine which reserve corresponds to our token
        total_lp_supply: uint256 = IQuickswapPair(self.lp_token).totalSupply()
        
        # Get the token value in the LP
        token0: address = IQuickswapPair(self.lp_token).token0()
        
        if token0 == self.token:
            token_in_lp: uint256 = (lp_balance * reserve0) / total_lp_supply
        else:
            token_in_lp: uint256 = (lp_balance * reserve1) / total_lp_supply
        
        token_balance += token_in_lp
    
    return token_balance

@internal
def _rebalance_liquidity():
    """
    @notice Rebalance liquidity to maintain target allocation
    """
    # Get total assets
    total_assets: uint256 = self._total_assets()
    token_balance: uint256 = ERC20(self.token).balanceOf(self)
    
    # Calculate target liquidity amount
    target_liquidity: uint256 = (total_assets * self.target_liquidity_percent) / BASIS_POINTS
    
    # Calculate how much is currently in LP
    lp_balance: uint256 = ERC20(self.lp_token).balanceOf(self)
    token_in_lp: uint256 = 0
    
    if lp_balance > 0:
        reserve0: uint112 = 0
        reserve1: uint112 = 0
        timestamp: uint32 = 0
        reserve0, reserve1, timestamp = IQuickswapPair(self.lp_token).getReserves()
        
        total_lp_supply: uint256 = IQuickswapPair(self.lp_token).totalSupply()
        token0: address = IQuickswapPair(self.lp_token).token0()
        
        if token0 == self.token:
            token_in_lp = (lp_balance * reserve0) / total_lp_supply
        else:
            token_in_lp = (lp_balance * reserve1) / total_lp_supply
    
    # Add more liquidity if needed
    if token_in_lp < target_liquidity and token_balance > 0:
        amount_to_add: uint256 = min(target_liquidity - token_in_lp, token_balance)
        self._add_liquidity_to_pool(amount_to_add)
    
    # Remove liquidity if we have too much
    if token_in_lp > target_liquidity:
        excess_token: uint256 = token_in_lp - target_liquidity
        self._remove_liquidity_if_needed(excess_token)

@internal
def _add_liquidity_to_pool(_amount: uint256):
    """
    @notice Add liquidity to the Quickswap pool
    @param _amount Amount of token to add
    """
    if _amount == 0:
        return
    
    # Get quote for USDC needed to match token amount
    path: DynArray[address, 2] = [self.token, self.usdc]
    amounts_out: DynArray[uint256, 2] = IQuickswapRouter(self.router).getAmountsOut(_amount, path)
    usdc_amount: uint256 = amounts_out[1]
    
    # Calculate min amounts with slippage protection
    min_token_amount: uint256 = (_amount * (BASIS_POINTS - self.max_slippage)) / BASIS_POINTS
    min_usdc_amount: uint256 = (usdc_amount * (BASIS_POINTS - self.max_slippage)) / BASIS_POINTS
    
    # Approve router to spend tokens
    assert ERC20(self.token).approve(self.router, _amount), "Token approval failed"
    assert ERC20(self.usdc).approve(self.router, usdc_amount), "USDC approval failed"
    
    # Add liquidity
    token_amount: uint256 = 0
    usdc_amount_actual: uint256 = 0
    lp_amount: uint256 = 0
    token_amount, usdc_amount_actual, lp_amount = IQuickswapRouter(self.router).addLiquidity(
        self.token,
        self.usdc,
        _amount,
        usdc_amount,
        min_token_amount,
        min_usdc_amount,
        self,
        block.timestamp + 1800  # 30 mins deadline
    )
    
    log LiquidityAdded(token_amount, usdc_amount_actual, lp_amount)

@internal
def _remove_liquidity_if_needed(_token_amount_needed: uint256):
    """
    @notice Remove liquidity from the Quickswap pool if needed
    @param _token_amount_needed Amount of token needed
    """
    lp_balance: uint256 = ERC20(self.lp_token).balanceOf(self)
    if lp_balance == 0 or _token_amount_needed == 0:
        return
    
    # Get the reserves from the LP token
    reserve0: uint112 = 0
    reserve1: uint112 = 0
    timestamp: uint32 = 0
    reserve0, reserve1, timestamp = IQuickswapPair(self.lp_token).getReserves()
    
    # Determine which reserve corresponds to our token
    total_lp_supply: uint256 = IQuickswapPair(self.lp_token).totalSupply()
    token0: address = IQuickswapPair(self.lp_token).token0()
    
    token_reserve: uint112 = 0
    usdc_reserve: uint112 = 0
    
    if token0 == self.token:
        token_reserve = reserve0
        usdc_reserve = reserve1
    else:
        token_reserve = reserve1
        usdc_reserve = reserve0
    
    # Calculate how much LP we need to burn to get the required token amount
    lp_to_burn: uint256 = (_token_amount_needed * total_lp_supply) / token_reserve
    lp_to_burn = min(lp_to_burn, lp_balance)  # Can't burn more than we have
    
    # Calculate expected token and USDC amounts
    expected_token: uint256 = (lp_to_burn * token_reserve) / total_lp_supply
    expected_usdc: uint256 = (lp_to_burn * usdc_reserve) / total_lp_supply
    
    # Calculate min amounts with slippage protection
    min_token_amount: uint256 = (expected_token * (BASIS_POINTS - self.max_slippage)) / BASIS_POINTS
    min_usdc_amount: uint256 = (expected_usdc * (BASIS_POINTS - self.max_slippage)) / BASIS_POINTS
    
    # Approve router to spend LP tokens
    assert ERC20(self.lp_token).approve(self.router, lp_to_burn), "LP token approval failed"
    
    # Remove liquidity
    token_amount: uint256 = 0
    usdc_amount: uint256 = 0
    token_amount, usdc_amount = IQuickswapRouter(self.router).removeLiquidity(
        self.token,
        self.usdc,
        lp_to_burn,
        min_token_amount,
        min_usdc_amount,
        self,
        block.timestamp + 1800  # 30 mins deadline
    )
    
    log LiquidityRemoved(lp_to_burn, token_amount, usdc_amount)

@internal
def _calculate_yield() -> uint256:
    """
    @notice Calculate yield
    @return Amount of yield available
    """
    # Simplified yield calculation for this example
    # In a real implementation, we'd track historical values and calculate actual yield
    
    # For this example, we'll simulate yield by using a percentage of the LP position
    lp_balance: uint256 = ERC20(self.lp_token).balanceOf(self)
    if lp_balance == 0:
        return 0
    
    # Calculate 0.1% of our token in LP as "yield"
    token_in_lp: uint256 = 0
    
    reserve0: uint112 = 0
    reserve1: uint112 = 0
    timestamp: uint32 = 0
    reserve0, reserve1, timestamp = IQuickswapPair(self.lp_token).getReserves()
    
    total_lp_supply: uint256 = IQuickswapPair(self.lp_token).totalSupply()
    token0: address = IQuickswapPair(self.lp_token).token0()
    
    if token0 == self.token:
        token_in_lp = (lp_balance * reserve0) / total_lp_supply
    else:
        token_in_lp = (lp_balance * reserve1) / total_lp_supply
    
    # Return 0.1% as simulated yield
    return token_in_lp / 1000 