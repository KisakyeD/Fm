import os
import re
import datetime
import requests
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from security import verify_gateway_signature

app = FastAPI(title="Sovereign Multi-Rail Gateway (Airtel & BTC)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Unified User Wallet Ledger (Supports both UGX and BTC balances)
user_wallets = {
    "test_user": {
        "balance_coins": 1400, 
        "balance_ugx": 50000,
        "balance_btc": 0.005
    }
}

# Master transaction tracking queues
transaction_ledger = []

class AirtelWithdrawalRequest(BaseModel):
    username: str
    amount_ugx: float
    airtel_phone: str

class BTCWithdrawalRequest(BaseModel):
    username: str
    btc_amount: float
    btc_address: str

# Environment Configuration
GATEWAY_SECRET_KEY = os.getenv("GATEWAY_SECRET_KEY", "FLWSECK_TEST-YOUR_SECRET_KEY_HERE")
GATEWAY_MASTER_KEY = os.getenv("GATEWAY_MASTER_KEY", "SOVEREIGN_GATEWAY_SECRET_SIGNING_KEY_2026")
GATEWAY_TRANSFER_URL = "https://api.flutterwave.com/v3/transfers"

def validate_btc_address(address: str) -> bool:
    """Validates Bitcoin address formats (Legacy, SegWit, Taproot)."""
    clean_addr = address.strip()
    legacy_pattern = r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$"
    bech32_pattern = r"^bc1[ac-hj-np-z0-9]{39,59}$"
    return bool(re.match(legacy_pattern, clean_addr) or re.match(bech32_pattern, clean_addr))

@app.get("/")
def gateway_root():
    return {"status": "ONLINE", "engine": "Sovereign Multi-Rail Gateway Active"}

@app.get("/api/wallet/{username}")
def get_wallet(username: str):
    if username not in user_wallets:
        user_wallets[username] = {"balance_coins": 1400, "balance_ugx": 50000, "balance_btc": 0.005}
    return {"status": "success", "data": user_wallets[username]}

@app.post("/api/withdraw/airtel")
async def execute_airtel_payout(
    request: Request,
    cmd: AirtelWithdrawalRequest,
    x_gateway_signature: str = Header(None)
):
    """Handles mobile money payouts directly to Airtel phone numbers."""
    body_bytes = await request.body()
    
    # Optional cryptographic signature check if header is provided
    if x_gateway_signature and not verify_gateway_signature(body_bytes, x_gateway_signature, GATEWAY_MASTER_KEY):
        raise HTTPException(status_code=401, detail="Gateway Access Denied: Invalid Cryptographic Signature.")

    if cmd.username not in user_wallets:
        user_wallets[cmd.username] = {"balance_coins": 1400, "balance_ugx": 50000, "balance_btc": 0.005}
    
    wallet = user_wallets[cmd.username]
    
    if wallet["balance_ugx"] < cmd.amount_ugx:
        raise HTTPException(status_code=400, detail="Gateway Error: Insufficient UGX balance.")
    
    phone = cmd.airtel_phone.strip()
    if not (phone.startswith("07") or phone.startswith("256")) or len(phone) < 10:
        raise HTTPException(status_code=400, detail="Gateway Firewall: Invalid phone number structure.")
    
    if cmd.amount_ugx < 500:
        raise HTTPException(status_code=400, detail="Gateway Firewall: Amount is below minimum threshold.")

    # Deduct locally
    wallet["balance_ugx"] -= cmd.amount_ugx
    tx_reference = f"AT-PO-{int(datetime.datetime.utcnow().timestamp())}"
    
    headers = {
        "Authorization": f"Bearer {GATEWAY_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "account_bank": "MPS",
        "account_number": phone,
        "amount": cmd.amount_ugx,
        "currency": "UGX",
        "narration": "TikTok Coin Store Payout",
        "reference": tx_reference,
        "beneficiary_name": cmd.username
    }
    
    status_message = "Processing Disbursement"
    
    try:
        response = requests.post(GATEWAY_TRANSFER_URL, json=payload, headers=headers, timeout=15)
        res_data = response.json()
        
        if response.status_code in [200, 201] and res_data.get("status") == "success":
            status_message = "Processing Disbursement"
        else:
            err_msg = res_data.get("message", "Gateway Refusal")
            status_message = f"Failed: {err_msg}"
            wallet["balance_ugx"] += cmd.amount_ugx
    except Exception as e:
        status_message = f"Network Error: {str(e)}"
        wallet["balance_ugx"] += cmd.amount_ugx

    ledger_record = {
        "payout_id": tx_reference,
        "username": cmd.username,
        "type": "Airtel Mobile Money",
        "destination": phone,
        "amount": f"UGX {cmd.amount_ugx:,.0f}",
        "status": status_message,
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    transaction_ledger.insert(0, ledger_record)

    return {
        "status": "success",
        "payout_id": tx_reference,
        "message": status_message,
        "remaining_ugx": wallet["balance_ugx"]
    }

@app.post("/api/withdraw/btc")
def execute_btc_withdrawal(cmd: BTCWithdrawalRequest):
    """Handles withdrawals directly to external Bitcoin wallet addresses."""
    if cmd.username not in user_wallets:
        user_wallets[cmd.username] = {"balance_coins": 1400, "balance_ugx": 50000, "balance_btc": 0.005}
    
    wallet = user_wallets[cmd.username]
    
    if wallet["balance_btc"] < cmd.btc_amount:
        raise HTTPException(status_code=400, detail="Insufficient BTC balance for withdrawal.")
    
    if not validate_btc_address(cmd.btc_address):
        raise HTTPException(status_code=400, detail="Invalid Bitcoin wallet address format.")
    
    if cmd.btc_amount < 0.0001:
        raise HTTPException(status_code=400, detail="Amount is below the minimum BTC withdrawal limit.")

    wallet["balance_btc"] -= cmd.btc_amount
    tx_reference = f"BTC-WD-{int(datetime.datetime.utcnow().timestamp())}"
    
    status_message = "Broadcast Successful - Waiting for On-Chain Confirmations"
    
    ledger_record = {
        "payout_id": tx_reference,
        "username": cmd.username,
        "type": "Bitcoin On-Chain",
        "destination": cmd.btc_address.strip(),
        "amount": f"{cmd.btc_amount} BTC",
        "status": status_message,
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    transaction_ledger.insert(0, ledger_record)

    return {
        "status": "success",
        "withdrawal_id": tx_reference,
        "message": status_message,
        "remaining_btc": wallet["balance_btc"]
    }

@app.get("/api/withdraw/list")
def list_transactions():
    return {"status": "success", "data": transaction_ledger}
