from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from web3 import Web3
import os
from dotenv import load_dotenv

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

# Uniswap V2 Router address
UNISWAP_ROUTER = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'

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
        
        # Here you would implement the actual portfolio fetching logic
        # This is a placeholder response
        portfolio = {
            'BTC': {'amount': 0.5, 'value': 50000},
            'ETH': {'amount': 0.3, 'value': 30000},
            'SOL': {'amount': 0.2, 'value': 20000}
        }
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