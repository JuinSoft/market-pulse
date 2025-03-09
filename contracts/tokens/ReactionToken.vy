# @version 0.3.10
"""
@title ReactionToken
@author MarketPulse Team
@license MIT
@notice ERC20 token for MarketPulse event-triggered yield farming
@dev Implementation of the ERC20 token standard using Snekmate
"""

from vyper.interfaces import ERC20
from snekmate.tokens.ERC20 import ERC20 as SnekERC20

implements: ERC20

# Events
event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256

# Storage variables
name: public(String[64])
symbol: public(String[32])
decimals: public(uint8)

balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])
totalSupply: public(uint256)

vault: public(address)  # The vault that manages this token

# Immutables
ZERO_ADDRESS: constant(address) = 0x0000000000000000000000000000000000000000

@external
def __init__(
    _name: String[64],
    _symbol: String[32],
    _decimals: uint8,
    _vault: address
):
    """
    @notice Constructor to create a ReactionToken
    @param _name Token name
    @param _symbol Token symbol
    @param _decimals Number of decimals
    @param _vault Address of the vault that manages this token
    """
    self.name = _name
    self.symbol = _symbol
    self.decimals = _decimals
    self.vault = _vault
    # Initial supply is 0, tokens are minted when users deposit into vault

@external
def transfer(_to: address, _value: uint256) -> bool:
    """
    @notice Transfer tokens to a specified address
    @param _to The address to transfer to
    @param _value The amount to be transferred
    @return Success boolean
    """
    assert _to != ZERO_ADDRESS, "ERC20: transfer to the zero address"
    assert _value <= self.balanceOf[msg.sender], "ERC20: transfer amount exceeds balance"
    
    self.balanceOf[msg.sender] -= _value
    self.balanceOf[_to] += _value
    
    log Transfer(msg.sender, _to, _value)
    return True

@external
def transferFrom(_from: address, _to: address, _value: uint256) -> bool:
    """
    @notice Transfer tokens from one address to another using allowance
    @param _from The address which you want to send tokens from
    @param _to The address which you want to transfer to
    @param _value The amount of tokens to be transferred
    @return Success boolean
    """
    assert _from != ZERO_ADDRESS, "ERC20: transfer from the zero address"
    assert _to != ZERO_ADDRESS, "ERC20: transfer to the zero address"
    assert _value <= self.balanceOf[_from], "ERC20: transfer amount exceeds balance"
    assert _value <= self.allowance[_from][msg.sender], "ERC20: transfer amount exceeds allowance"
    
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value
    self.allowance[_from][msg.sender] -= _value
    
    log Transfer(_from, _to, _value)
    return True

@external
def approve(_spender: address, _value: uint256) -> bool:
    """
    @notice Approve the passed address to spend the specified amount of tokens
    @param _spender The address which will spend the funds
    @param _value The amount of tokens to be spent
    @return Success boolean
    """
    assert _spender != ZERO_ADDRESS, "ERC20: approve to the zero address"
    
    self.allowance[msg.sender][_spender] = _value
    
    log Approval(msg.sender, _spender, _value)
    return True

@external
def mint(_to: address, _value: uint256) -> bool:
    """
    @notice Mint new tokens
    @dev Only callable by the vault contract
    @param _to Address to mint tokens to
    @param _value Amount of tokens to mint
    @return Success boolean
    """
    assert msg.sender == self.vault, "Only vault can mint"
    assert _to != ZERO_ADDRESS, "ERC20: mint to the zero address"
    
    self.totalSupply += _value
    self.balanceOf[_to] += _value
    
    log Transfer(ZERO_ADDRESS, _to, _value)
    return True

@external
def burn(_from: address, _value: uint256) -> bool:
    """
    @notice Burn tokens
    @dev Only callable by the vault contract
    @param _from Address to burn tokens from
    @param _value Amount of tokens to burn
    @return Success boolean
    """
    assert msg.sender == self.vault, "Only vault can burn"
    assert _from != ZERO_ADDRESS, "ERC20: burn from the zero address"
    assert _value <= self.balanceOf[_from], "ERC20: burn amount exceeds balance"
    
    self.balanceOf[_from] -= _value
    self.totalSupply -= _value
    
    log Transfer(_from, ZERO_ADDRESS, _value)
    return True 