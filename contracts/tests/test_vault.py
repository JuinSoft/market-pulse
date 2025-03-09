import pytest
from brownie import chain, Wei, reverts
from brownie import accounts
import brownie

@pytest.fixture
def deployer():
    return accounts[0]

@pytest.fixture
def treasury():
    return accounts[1]

@pytest.fixture
def user1():
    return accounts[2]

@pytest.fixture
def user2():
    return accounts[3]

@pytest.fixture
def usdc_token(deployer):
    # Deploy a mock USDC token for testing
    from brownie import MockERC20
    
    token = MockERC20.deploy("USD Coin", "USDC", 6, {"from": deployer})
    # Mint some tokens for testing
    token.mint(deployer, Wei("1000000 ether"), {"from": deployer})
    return token

@pytest.fixture
def event_token(deployer):
    # Deploy a mock token that represents an event-related token
    from brownie import MockERC20
    
    token = MockERC20.deploy("Event Token", "EVENT", 18, {"from": deployer})
    # Mint some tokens for testing
    token.mint(deployer, Wei("1000000 ether"), {"from": deployer})
    return token

@pytest.fixture
def quickswap_router(deployer):
    # Deploy a mock Quickswap router for testing
    from brownie import MockQuickswapRouter
    
    router = MockQuickswapRouter.deploy({"from": deployer})
    return router

@pytest.fixture
def quickswap_pair(deployer, event_token, usdc_token):
    # Deploy a mock Quickswap pair for testing
    from brownie import MockQuickswapPair
    
    pair = MockQuickswapPair.deploy(event_token, usdc_token, {"from": deployer})
    return pair

@pytest.fixture
def token_blueprint(deployer):
    from brownie import ReactionTokenBlueprint
    
    blueprint = ReactionTokenBlueprint.deploy({"from": deployer})
    return blueprint

@pytest.fixture
def vault_blueprint(deployer):
    from brownie import EventVaultBlueprint
    
    blueprint = EventVaultBlueprint.deploy({"from": deployer})
    return blueprint

@pytest.fixture
def factory(deployer, treasury, usdc_token, quickswap_router, token_blueprint, vault_blueprint):
    from brownie import VaultFactory
    
    treasury_fee = 50  # 0.5%
    
    factory = VaultFactory.deploy(
        treasury,
        treasury_fee,
        usdc_token,
        quickswap_router,
        vault_blueprint,
        token_blueprint,
        {"from": deployer}
    )
    return factory

def test_create_vault(factory, deployer, event_token):
    # Test creating a new vault
    event_id = 1
    name = "Test Event"
    symbol = "TEST"
    
    tx = factory.create_vault(
        event_token,
        event_id,
        name,
        symbol,
        {"from": deployer}
    )
    
    # Check the event was emitted correctly
    assert "VaultCreated" in tx.events
    vault_address = tx.events["VaultCreated"]["vault"]
    reaction_token = tx.events["VaultCreated"]["reaction_token"]
    
    # Verify the vault was registered in the factory
    assert factory.vault_count() == 1
    assert factory.vaults(1) == vault_address
    assert factory.is_vault(vault_address) is True
    
    # Get the vault contract and verify its properties
    from brownie import EventVault
    vault = EventVault.at(vault_address)
    
    assert vault.token() == event_token
    assert vault.reaction_token() == reaction_token
    assert vault.factory() == factory
    assert vault.is_active() is True

def test_deposit_withdraw(factory, deployer, event_token, user1, user2):
    # Create a new vault
    event_id = 1
    name = "Test Event"
    symbol = "TEST"
    
    tx = factory.create_vault(
        event_token,
        event_id,
        name,
        symbol,
        {"from": deployer}
    )
    
    vault_address = tx.events["VaultCreated"]["vault"]
    reaction_token = tx.events["VaultCreated"]["reaction_token"]
    
    from brownie import EventVault, ReactionToken
    vault = EventVault.at(vault_address)
    token = ReactionToken.at(reaction_token)
    
    # Transfer some event tokens to users for testing
    amount_user1 = Wei("1000 ether")
    amount_user2 = Wei("2000 ether")
    
    event_token.transfer(user1, amount_user1, {"from": deployer})
    event_token.transfer(user2, amount_user2, {"from": deployer})
    
    # User1 deposits
    event_token.approve(vault, amount_user1, {"from": user1})
    tx1 = vault.deposit(amount_user1, {"from": user1})
    
    # Check user1 received reaction tokens
    assert token.balanceOf(user1) > 0
    assert token.balanceOf(user1) == tx1.return_value
    user1_shares = token.balanceOf(user1)
    
    # User2 deposits
    event_token.approve(vault, amount_user2, {"from": user2})
    tx2 = vault.deposit(amount_user2, {"from": user2})
    
    # Check user2 received reaction tokens
    assert token.balanceOf(user2) > 0
    assert token.balanceOf(user2) == tx2.return_value
    user2_shares = token.balanceOf(user2)
    
    # Check proportions are roughly correct (user2 should have about 2x the shares of user1)
    assert pytest.approx(user2_shares / user1_shares, rel=0.05) == 2.0
    
    # User1 withdraws half
    withdraw_shares = user1_shares // 2
    token.approve(vault, withdraw_shares, {"from": user1})
    
    balance_before = event_token.balanceOf(user1)
    tx3 = vault.withdraw(withdraw_shares, {"from": user1})
    balance_after = event_token.balanceOf(user1)
    
    # Check user1 got tokens back
    assert balance_after > balance_before
    assert token.balanceOf(user1) == user1_shares - withdraw_shares
    
    # Check the withdrawal amount is proportional to the deposit
    expected_amount = amount_user1 // 2  # Simplified calculation, ignoring fees
    withdrawn_amount = balance_after - balance_before
    # Allow for some deviation due to fees and rounding
    assert pytest.approx(withdrawn_amount / expected_amount, rel=0.1) == 1.0

def test_liquidity_management(factory, deployer, event_token, usdc_token, quickswap_router, user1):
    # Create a new vault
    event_id = 1
    name = "Test Event"
    symbol = "TEST"
    
    tx = factory.create_vault(
        event_token,
        event_id,
        name,
        symbol,
        8000,  # 80% target liquidity
        100,   # 1% max slippage
        {"from": deployer}
    )
    
    vault_address = tx.events["VaultCreated"]["vault"]
    
    from brownie import EventVault
    vault = EventVault.at(vault_address)
    
    # Transfer some event tokens to user1
    amount = Wei("10000 ether")
    event_token.transfer(user1, amount, {"from": deployer})
    
    # Transfer some USDC to quickswap_router for the mock swap
    usdc_amount = Wei("5000 ether")
    usdc_token.transfer(quickswap_router, usdc_amount, {"from": deployer})
    
    # User1 deposits
    event_token.approve(vault, amount, {"from": user1})
    vault.deposit(amount, {"from": user1})
    
    # Check liquidity was added (simplified for mock testing)
    # In a real test with full mock implementation, we would check LP tokens were received
    # and correct amounts were transferred
    
    # For this test, we'll assume _rebalance_liquidity works and check the event was emitted
    tx_logs = vault.get_logs()
    
    has_liquidity_event = False
    for log in tx_logs:
        if log.event == "LiquidityAdded":
            has_liquidity_event = True
            break
    
    assert has_liquidity_event is True

def test_yield_distribution(factory, deployer, event_token, usdc_token, quickswap_router, user1, user2):
    # Create a new vault
    event_id = 1
    name = "Test Event"
    symbol = "TEST"
    
    tx = factory.create_vault(
        event_token,
        event_id,
        name,
        symbol,
        {"from": deployer}
    )
    
    vault_address = tx.events["VaultCreated"]["vault"]
    reaction_token = tx.events["VaultCreated"]["reaction_token"]
    
    from brownie import EventVault, ReactionToken
    vault = EventVault.at(vault_address)
    token = ReactionToken.at(reaction_token)
    
    # Transfer tokens to users
    amount1 = Wei("1000 ether")
    amount2 = Wei("3000 ether")
    
    event_token.transfer(user1, amount1, {"from": deployer})
    event_token.transfer(user2, amount2, {"from": deployer})
    
    # Users deposit
    event_token.approve(vault, amount1, {"from": user1})
    vault.deposit(amount1, {"from": user1})
    
    event_token.approve(vault, amount2, {"from": user2})
    vault.deposit(amount2, {"from": user2})
    
    # Mock some yield generation
    # In a real test, we would simulate trading fees, etc.
    # For this test, we'll just directly distribute yield
    
    # Only the owner (deployer/factory) can distribute yield
    with reverts("Only owner"):
        vault.distribute_yield({"from": user1})
    
    # Distributing yield should work from the owner
    tx = vault.distribute_yield({"from": deployer})
    
    # Check the YieldDistributed event was emitted
    assert "YieldDistributed" in tx.events
    yield_amount = tx.events["YieldDistributed"]["amount"]
    assert yield_amount > 0

def test_vault_lifecycle(factory, deployer, event_token, user1):
    # Create a new vault with a short expiry
    event_id = 1
    name = "Test Event"
    symbol = "TEST"
    expiry_duration = 86400  # 1 day
    
    tx = factory.create_vault(
        event_token,
        event_id,
        name,
        symbol,
        0,
        0,
        expiry_duration,
        {"from": deployer}
    )
    
    vault_address = tx.events["VaultCreated"]["vault"]
    
    from brownie import EventVault
    vault = EventVault.at(vault_address)
    
    # Transfer tokens to user
    amount = Wei("1000 ether")
    event_token.transfer(user1, amount, {"from": deployer})
    
    # User deposits
    event_token.approve(vault, amount, {"from": user1})
    vault.deposit(amount, {"from": user1})
    
    # Fast forward past expiry
    chain.mine(timedelta=expiry_duration + 100)
    
    # Deposit should fail after expiry
    with reverts("Vault has expired"):
        vault.deposit(amount, {"from": user1})
    
    # Owner can deactivate the vault
    assert vault.is_active() is True
    
    with reverts("Only owner"):
        vault.deactivate({"from": user1})
    
    vault.deactivate({"from": deployer})
    assert vault.is_active() is False
    
    # Deposit should fail after deactivation
    with reverts("Vault is not active"):
        vault.deposit(amount, {"from": user1}) 