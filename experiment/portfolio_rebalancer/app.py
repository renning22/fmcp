from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from web3 import Web3
import os
from dotenv import load_dotenv
import requests

app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(os.getenv('INFURA_URL', 'https://mainnet.infura.io/v3/YOUR_INFURA_KEY')))

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

def get_token_prices():
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

def get_token_price(token_address, amount_in=1):
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
        return w3.from_wei(amounts[1], 'ether')
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
            return jsonify({'error': 'Invalid address'}), 400
        
        # Convert to checksum address
        address = w3.to_checksum_address(address)
        
        # Get ETH balance
        eth_balance = w3.eth.get_balance(address)
        eth_balance_ether = w3.from_wei(eth_balance, 'ether')
        
        # Get token prices from CoinGecko
        token_prices = get_token_prices()
        if not token_prices:
            return jsonify({'error': 'Failed to fetch token prices'}), 500
        
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
        
        # Add total portfolio value
        portfolio['total_value'] = round(total_value, 2)
        
        return jsonify(portfolio)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/rebalance', methods=['POST'])
def rebalance_portfolio():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        address = data.get('address')
        target_allocations = data.get('allocations')
        
        if not address or not w3.is_address(address):
            return jsonify({'error': 'Invalid address'}), 400
        
        if not target_allocations:
            return jsonify({'error': 'No target allocations provided'}), 400
        
        # Here you would implement the actual rebalancing logic
        # This is a placeholder response
        return jsonify({
            'status': 'success',
            'message': 'Rebalancing transaction prepared',
            'target_allocations': target_allocations
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 