from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from web3 import Web3
import os
from dotenv import load_dotenv
import requests
from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Union

app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(os.getenv('INFURA_URL', 'https://mainnet.infura.io/v3/YOUR_INFURA_KEY')))

# Check Web3 connection
if not w3.is_connected():
    print("Error: Failed to connect to Ethereum network")
    raise Exception("Failed to connect to Ethereum network")
else:
    print("Successfully connected to Ethereum network")
    print(f"Current block: {w3.eth.block_number}")

# Token addresses (mainnet)
TOKEN_ADDRESSES = {
    'BTC': '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',  # WBTC
    'ETH': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',  # WETH
    'SOL': '0xD31a59c85aE9D8edEFeC411D448f90841571b89c'   # Wrapped SOL
}

# CoinGecko API endpoints
COINGECKO_API = 'https://api.coingecko.com/api/v3'
COINGECKO_IDS = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'SOL': 'solana'
}

# Uniswap V2 Router address
UNISWAP_ROUTER = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'

# Uniswap V2 Router ABI (minimal for getAmountsOut)
UNISWAP_ROUTER_ABI = [
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "amountIn",
                "type": "uint256"
            },
            {
                "internalType": "address[]",
                "name": "path",
                "type": "address[]"
            }
        ],
        "name": "getAmountsOut",
        "outputs": [
            {
                "internalType": "uint256[]",
                "name": "amounts",
                "type": "uint256[]"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

def get_token_prices() -> Optional[Dict[str, float]]:
    """Get token prices from CoinGecko API"""
    try:
        # Get prices for all tokens in one request
        ids = ','.join(COINGECKO_IDS.values())
        response = requests.get(f'{COINGECKO_API}/simple/price?ids={ids}&vs_currencies=usd')
        response.raise_for_status()
        prices = response.json()
        
        # Map prices to our token symbols
        return {
            symbol: prices[coingecko_id]['usd']
            for symbol, coingecko_id in COINGECKO_IDS.items()
        }
    except Exception as e:
        print(f"Error fetching prices from CoinGecko: {str(e)}")
        return None

def calculate_rebalancing_plan(current_portfolio: Dict, target_allocations: Dict) -> List[Dict]:
    """
    Calculate the rebalancing plan based on current portfolio and target allocations
    
    Args:
        current_portfolio: Current portfolio with token amounts and values
        target_allocations: Target allocations in percentages
        
    Returns:
        List of rebalancing actions to take
    """
    total_value = Decimal(str(current_portfolio['total_value']))
    actions = []
    
    # Calculate target values for each token
    target_values = {
        token: (total_value * Decimal(str(alloc))) / Decimal('100')
        for token, alloc in target_allocations.items()
    }
    
    # Calculate current values
    current_values = {
        token: Decimal(str(data['value']))
        for token, data in current_portfolio.items()
        if token != 'total_value'
    }
    
    # Calculate differences and create actions
    for token in target_values.keys():
        current_value = current_values.get(token, Decimal('0'))
        target_value = target_values[token]
        difference = target_value - current_value
        
        if abs(difference) > Decimal('0.01'):  # Only create action if difference is significant
            action = {
                'token': token,
                'action': 'buy' if difference > 0 else 'sell',
                'amount_usd': float(abs(difference)),
                'current_value': float(current_value),
                'target_value': float(target_value)
            }
            actions.append(action)
    
    return actions

def get_token_price(token_address: str, amount_in: int = 1) -> Optional[float]:
    """Get token price in ETH using Uniswap V2"""
    try:
        # Convert amount to wei
        amount_in_wei = w3.to_wei(amount_in, 'ether')
        
        # Create router contract instance
        router = w3.eth.contract(
            address=w3.to_checksum_address(UNISWAP_ROUTER),
            abi=UNISWAP_ROUTER_ABI
        )
        
        # Create path: token -> WETH
        path = [
            w3.to_checksum_address(token_address),
            w3.to_checksum_address(TOKEN_ADDRESSES['ETH'])  # WETH address
        ]
        
        # Get amounts out
        amounts = router.functions.getAmountsOut(amount_in_wei, path).call()
        
        # Convert wei to ether
        return float(w3.from_wei(amounts[1], 'ether'))
    except Exception as e:
        print(f"Error getting price for token {token_address}: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/connect-wallet', methods=['POST'])
def connect_wallet():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        address = data.get('address')
        if not address or not w3.is_address(address):
            return jsonify({'error': 'Invalid Ethereum address'}), 400
            
        # Convert to checksum address
        address = w3.to_checksum_address(address)
            
        # Verify the address is a valid contract or EOA
        try:
            code = w3.eth.get_code(address)
            is_contract = len(code) > 0
        except Exception as e:
            return jsonify({'error': f'Failed to verify address: {str(e)}'}), 400
            
        # Get ETH balance
        try:
            balance = w3.eth.get_balance(address)
            eth_balance = w3.from_wei(balance, 'ether')
        except Exception as e:
            return jsonify({'error': f'Failed to get balance: {str(e)}'}), 400
            
        # Get token balances
        token_balances = {}
        for token_symbol, token_address in TOKEN_ADDRESSES.items():
            try:
                # Create token contract instance
                token_contract = w3.eth.contract(
                    address=w3.to_checksum_address(token_address),
                    abi=[{
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function"
                    }]
                )
                balance = token_contract.functions.balanceOf(address).call()
                token_balances[token_symbol] = w3.from_wei(balance, 'ether')
            except Exception as e:
                token_balances[token_symbol] = 0
                
        return jsonify({
            'status': 'connected',
            'address': address,
            'is_contract': is_contract,
            'eth_balance': float(eth_balance),
            'token_balances': token_balances
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    try:
        address = request.args.get('address')
        if not address or not w3.is_address(address):
            print(f"Invalid address: {address}")
            return jsonify({'error': 'Invalid address'}), 400
        
        # Convert to checksum address
        address = w3.to_checksum_address(address)
        print(f"Getting portfolio for address: {address}")
        
        # Get ETH balance
        try:
            eth_balance = w3.eth.get_balance(address)
            eth_balance_ether = w3.from_wei(eth_balance, 'ether')
            print(f"ETH balance: {eth_balance_ether}")
        except Exception as e:
            print(f"Error getting ETH balance: {str(e)}")
            return jsonify({'error': f'Failed to get ETH balance: {str(e)}'}), 500
        
        # Get token prices from CoinGecko
        token_prices = get_token_prices()
        if not token_prices:
            print("Failed to fetch token prices from CoinGecko")
            return jsonify({'error': 'Failed to fetch token prices'}), 500
        print(f"Token prices: {token_prices}")
        
        # Get token balances
        portfolio = {}
        total_value = 0
        
        # ERC20 token ABI for balanceOf
        token_abi = [{
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"
        }]
        
        # Get balances for each token
        for token_symbol, token_address in TOKEN_ADDRESSES.items():
            try:
                print(f"Getting balance for {token_symbol} at {token_address}")
                token_contract = w3.eth.contract(
                    address=w3.to_checksum_address(token_address),
                    abi=token_abi
                )
                balance = token_contract.functions.balanceOf(address).call()
                balance_ether = w3.from_wei(balance, 'ether')
                
                # Get token price from CoinGecko
                token_usd_price = token_prices[token_symbol]
                
                token_value = float(balance_ether) * float(token_usd_price)
                total_value += token_value
                
                portfolio[token_symbol] = {
                    'amount': float(balance_ether),
                    'value': round(token_value, 2),
                    'price': round(token_usd_price, 2)
                }
                print(f"{token_symbol} balance: {balance_ether}, value: {token_value}")
            except Exception as e:
                print(f"Error getting {token_symbol} balance: {str(e)}")
                portfolio[token_symbol] = {'amount': 0, 'value': 0, 'price': 0}
        
        # Add ETH to portfolio
        eth_value = float(eth_balance_ether) * float(token_prices['ETH'])
        total_value += eth_value
        portfolio['ETH'] = {
            'amount': float(eth_balance_ether),
            'value': round(eth_value, 2),
            'price': round(token_prices['ETH'], 2)
        }
        print(f"ETH value: {eth_value}")
        
        # Add total portfolio value
        portfolio['total_value'] = round(total_value, 2)
        print(f"Total portfolio value: {total_value}")
        
        return jsonify(portfolio)
    except Exception as e:
        print(f"Error in get_portfolio: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rebalance', methods=['POST'])
def rebalance_portfolio():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        address = data.get('address')
        target_allocations = data.get('allocations')
        action_index = data.get('action_index', -1)  # -1 means generate plan, >= 0 means execute action
        
        if not address or not w3.is_address(address):
            return jsonify({'error': 'Invalid address'}), 400
        
        if not target_allocations:
            return jsonify({'error': 'No target allocations provided'}), 400
        
        # Get current portfolio
        portfolio_response = app.test_client().get(f'/api/portfolio?address={address}')
        current_portfolio = portfolio_response.get_json()
        
        # Check if portfolio data is valid
        if not current_portfolio or 'error' in current_portfolio:
            return jsonify({'error': 'Failed to get portfolio data'}), 500
            
        if action_index == -1:
            # Generate rebalancing plan
            actions = calculate_rebalancing_plan(current_portfolio, target_allocations)
            
            return jsonify({
                'status': 'plan_ready',
                'actions': actions,
                'total_actions': len(actions)
            })
        else:
            # Execute specific action
            actions = calculate_rebalancing_plan(current_portfolio, target_allocations)
            if action_index >= len(actions):
                return jsonify({'error': 'Invalid action index'}), 400
                
            action = actions[action_index]
            token = action['token']
            amount_usd = action['amount_usd']
            
            # Get token price in ETH
            token_price_eth = get_token_price(TOKEN_ADDRESSES[token])
            if not token_price_eth:
                return jsonify({'error': f'Failed to get price for {token}'}), 500
                
            # Calculate amount in ETH
            amount_eth = amount_usd / token_price_eth
            
            # Prepare transaction data
            transaction = {
                'from': address,
                'to': TOKEN_ADDRESSES[token],
                'value': w3.to_wei(amount_eth, 'ether'),
                'gas': 200000,
                'gasPrice': w3.to_wei('50', 'gwei'),
                'nonce': w3.eth.get_transaction_count(address),
                'chainId': 1
            }
            
            return jsonify({
                'status': 'transaction_ready',
                'transaction': transaction,
                'action': action,
                'next_action_index': action_index + 1 if action_index + 1 < len(actions) else -1
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 