import os
import re
import datetime
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Sovereign Multi-Rail Gateway Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# User ledger tracking balances
user_wallets = {
    "test_user": {
        "balance_coins": 1400, 
        "balance_ugx": 50000,
        "balance_btc": 0.005
    }
}

transaction_ledger = []

class AirtelWithdrawalRequest(BaseModel):
    username: str
    amount_ugx: float
    airtel_phone: str

class BTCWithdrawalRequest(BaseModel):
    username: str
    btc_amount: float
    btc_address: str

GATEWAY_SECRET_KEY = os.getenv("GATEWAY_SECRET_KEY", "FLWSECK_TEST-YOUR_SECRET_KEY_HERE")
GATEWAY_TRANSFER_URL = "https://api.flutterwave.com/v3/transfers"

def validate_btc_address(address: str) -> bool:
    clean_addr = address.strip()
    legacy_pattern = r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$"
    bech32_pattern = r"^bc1[ac-hj-np-z0-9]{39,59}$"
    return bool(re.match(legacy_pattern, clean_addr) or re.match(bech32_pattern, clean_addr))

@app.get("/")
def gateway_root():
    return {"status": "ONLINE", "engine": "Sovereign Gateway Active"}

@app.get("/api/wallet/{username}")
def get_wallet(username: str):
    if username not in user_wallets:
        user_wallets[username] = {"balance_coins": 1400, "balance_ugx": 50000, "balance_btc": 0.005}
    return {"status": "success", "data": user_wallets[username]}

@app.post("/api/withdraw/airtel")
def execute_airtel_payout(cmd: AirtelWithdrawalRequest):
    if cmd.username not in user_wallets:
        user_wallets[cmd.username] = {"balance_coins": 1400, "balance_ugx": 50000, "balance_btc": 0.005}
    
    wallet = user_wallets[cmd.username]
    
    if wallet["balance_ugx"] < cmd.amount_ugx:
        raise HTTPException(status_code=400, detail="Insufficient UGX balance for payout.")
    
    phone = cmd.airtel_phone.strip()
    if not (phone.startswith("07") or phone.startswith("256")) or len(phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid Ugandan mobile money phone format.")
    
    if cmd.amount_ugx < 500:
        raise HTTPException(status_code=400, detail="Amount is below the minimum UGX 500 limit.")

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
            status_message = "Disbursement Initiated Successfully"
        else:
            err_msg = res_data.get("message", "Gateway Refusal")
            status_message = f"Failed: {err_msg}"
            wallet["balance_ugx"] += cmd.amount_ugx
    except Exception as e:
        status_message = f"Network Connection Error: {str(e)}"
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
    if cmd.username not in user_wallets:
        user_wallets[cmd.username] = {"balance_coins": 1400, "balance_ugx": 50000, "balance_btc": 0.005}
    
    wallet = user_wallets[cmd.username]
    
    if wallet["balance_btc"] < cmd.btc_amount:
        raise HTTPException(status_code=400, detail="Insufficient BTC balance.")
    
    if not validate_btc_address(cmd.btc_address):
        raise HTTPException(status_code=400, detail="Invalid Bitcoin address structure.")
    
    if cmd.btc_amount < 0.0001:
        raise HTTPException(status_code=400, detail="Amount below minimum 0.0001 BTC limit.")

    wallet["balance_btc"] -= cmd.btc_amount
    tx_reference = f"BTC-WD-{int(datetime.datetime.utcnow().timestamp())}"
    
    status_message = "Broadcast Successful - Awaiting Confirmations"
    
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
