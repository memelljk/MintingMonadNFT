import time
import requests
from bs4 import BeautifulSoup
from web3 import Web3
import re
from dotenv import load_dotenv
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, filename="mint_bot.log", format="%(asctime)s - %(levelname)s - %(message)s")

# Load environment variables
load_dotenv()
RPC_URL = os.getenv("RPC_URL", "https://testnet-rpc.monad.xyz")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
MINT_TERMINAL_URL = os.getenv("MINT_TERMINAL_URL", "https://magiceden.io/mint-terminal/monad-testnet")

# ABI generik untuk fungsi mint
CONTRACT_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "quantity", "type": "uint256"}],
        "name": "mint",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]

# Inisialisasi Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Verifikasi koneksi
if not w3.is_connected():
    logging.error("Koneksi ke RPC gagal!")
    exit()
logging.info("Terhubung ke Monad Testnet")

# Fungsi untuk mengambil data dari Mint Terminal
def fetch_mint_terminal_data():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(MINT_TERMINAL_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logging.error(f"Gagal mengambil data: {e}")
        return None

# Fungsi untuk mendeteksi harga dan kontrak
def detect_mint_details(html_content):
    if not html_content:
        return None, None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Deteksi harga mint
    price = 0.0
    price_element = soup.find(text=re.compile(r"\d+\.?\d*\s*MON|FREE", re.I))
    if price_element:
        if "FREE" in price_element.upper():
            price = 0.0
        else:
            price_match = re.search(r"(\d+\.?\d*)\s*MON", price_element, re.I)
            price = float(price_match.group(1)) if price_match else 0.0
    
    # Deteksi alamat kontrak
    contract_address = None
    contract_link = soup.find("a", href=re.compile(r"monad\.xyz/explorer/address/0x[a-fA-F0-9]{40}"))
    if contract_link:
        contract_address = re.search(r"0x[a-fA-F0-9]{40}", contract_link['href']).group(0)
    
    return price, contract_address

# Fungsi untuk mint NFT
def mint_nft(contract_address, price, quantity=1):
    if not contract_address or not w3.is_address(contract_address):
        logging.error("Alamat kontrak tidak valid!")
        return

    contract = w3.eth.contract(address=contract_address, abi=CONTRACT_ABI)
    total_cost = w3.to_wei(price * quantity, 'ether')

    # Cek saldo
    balance = w3.eth.get_balance(WALLET_ADDRESS)
    if balance < total_cost:
        logging.warning(f"Saldo tidak cukup! Dibutuhkan: {w3.from_wei(total_cost, 'ether')} MON")
        return

    # Buat transaksi
    tx = {
        'nonce': w3.eth.get_transaction_count(WALLET_ADDRESS),
        'to': contract_address,
        'value': total_cost,
        'gas': 300000,
        'gasPrice': int(w3.eth.gas_price * 1.2),
        'chainId': 1312,
        'data': contract.encodeABI(fn_name="mint", args=[quantity])
    }

    try:
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logging.info(f"Minting... Hash: {w3.to_hex(tx_hash)}")
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt['status'] == 1:
            logging.info(f"NFT berhasil di-mint! ({quantity} NFT)")
        else:
            logging.warning("Minting gagal!")
    except Exception as e:
        logging.error(f"Error saat minting: {e}")

# Fungsi utama bot
def run_auto_mint_bot():
    logging.info("Bot Auto-Minting Magic Eden (Monad Testnet) dimulai...")
    
    while True:
        try:
            html_content = fetch_mint_terminal_data()
            price, contract_address = detect_mint_details(html_content)
            
            if price is not None and contract_address:
                logging.info(f"Deteksi: Harga = {price} MON, Kontrak = {contract_address}")
                mint_nft(contract_address, price, quantity=1)
            else:
                logging.warning("Gagal mendeteksi harga atau kontrak!")
            
            time.sleep(60)
        except Exception as e:
            logging.error(f"Error di bot: {e}")
            time.sleep(300)

if __name__ == "__main__":
    run_auto_mint_bot()
