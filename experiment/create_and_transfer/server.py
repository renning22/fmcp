from flask import Flask, render_template, send_from_directory, jsonify
from web3 import Web3
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-wallet', methods=['POST'])
def generate_wallet():
    # Generate a new wallet
    account = Web3().eth.account.create()
    
    # Return the address and private key
    return jsonify({
        'address': account.address,
        'privateKey': account.key.hex()
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000) 