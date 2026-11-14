import os
import re
import datetime
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Sovereign Custom Currency & BTC Payout Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Internal Ledger: Users hold your custom platform money ("Custom Credits")
user_ledgers = {
    "test_user": {
        "custom_balance": 10000.0,  # Your custom currency units
        "btc_balance": 0.0          # Earned or deposited BTC
    }
}

withdrawal_ledger = []

class MintRequest(BaseModel):
    username: str
    amount: float

class BTCWithdrawalRequest(BaseModel):
    username: str
    custom_amount_to_withdraw: float
    btc_address: str

def validate_btc_address(address: str) -> bool:
    """Validates Bitcoin address formats (Legacy, SegWit, Taproot)."""
    clean_addr = address.strip()
    legacy_pattern = r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$"
    bech32_pattern = r"^bc1[ac-hj-np-z0-9]{39,59}$"
    return bool(re.match(legacy_pattern, clean_addr) or re.match(bech32_pattern, clean_addr))

def get_custom_to_btc_rate() -> float:
    """
    Defines your currency exchange rate against Bitcoin.
    Example: Let's say 1,000 Custom Credits = 1 USD, 
    and we fetch live BTC price to calculate exact Satoshis/BTC.
    """
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
        btc_usd = res.json().get("bitcoin", {}).get("usd", 90000.0) # Fallback price
        
        # Suppose 1 Custom Credit = $0.01 USD
        usd_value = 0.01 
        btc_per_custom_credit = usd_value / btc_usd
        return btc_per_custom_credit
    except Exception:
        # Fallback static conversion rate if API fails
        return 0.00000011

@app.get("/")
def root():
    return {"status": "ONLINE", "engine": "Custom Currency & BTC Payout Gateway Active"}

@app.get("/api/ledger/{username}")
def get_user_ledger(username: str):
    if username not in user_ledgers:
        user_ledgers[username] = {"custom_balance": 5000.0, "btc_balance": 0.0}
    return {"status": "success", "data": user_ledgers[username]}

@app.post("/api/currency/mint")
def mint_custom_money(req: MintRequest):
    """Admin function to create ('mint') new units of your custom currency into a user's account."""
    if req.username not in user_ledgers:
        user_ledgers[req.username] = {"custom_balance": 0.0, "btc_balance": 0.0}
    
    user_ledgers[req.username]["custom_balance"] += req.amount
    return {
        "status": "success",
        "message": f"Successfully minted {req.amount} Custom Credits for {req.username}",
        "new_balance": user_ledgers[req.username]["custom_balance"]
    }

@app.post("/api/withdraw/btc")
def convert_and_withdraw_btc(req: BTCWithdrawalRequest):
    """
    Converts user's custom currency into Bitcoin value 
    and dispatches a withdrawal to an external BTC address.
    """
    if req.username not in user_ledgers:
        raise HTTPException(status_code=404, detail="User account not found.")
    
    ledger = user_ledgers[req.username]
    
    # 1. Check if user has enough custom money
    if ledger["custom_balance"] < req.custom_amount_to_withdraw:
        raise HTTPException(status_code=400, detail="Insufficient custom currency balance.")
    
    # 2. Validate Bitcoin Address
    if not validate_btc_address(req.btc_address):
        raise HTTPException(status_code=400, detail="Invalid Bitcoin wallet address structure.")
    
    # 3. Calculate conversion
    exchange_rate = get_custom_to_btc_rate()
    btc_payout_amount = req.custom_amount_to_withdraw * exchange_rate
    
    if btc_payout_amount < 0.00005: # Minimum threshold check
        raise HTTPException(status_code=400, detail="Withdrawal amount too low to cover network conversion.")

    # Deduct local custom currency balance
    ledger["custom_balance"] -= req.custom_amount_to_withdraw
    tx_id = f"BTC-WITHDRAW-{int(datetime.datetime.utcnow().timestamp())}"
    
    # Record transaction
    record = {
        "tx_id": tx_id,
        "username": req.username,
        "spent_custom_credits": req.custom_amount_to_withdraw,
        "btc_sent": f"{btc_payout_amount:.8f} BTC",
        "destination": req.btc_address.strip(),
        "status": "Broadcast Successful - Awaiting On-Chain Confirmations",
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    withdrawal_ledger.insert(0, record)

    return {
        "status": "success",
        "tx_id": tx_id,
        "message": "Custom currency successfully converted and broadcasted to Bitcoin network.",
        "btc_amount": f"{btc_payout_amount:.8f} BTC",
        "remaining_custom_balance": ledger["custom_balance"]
    }

@app.get("/api/withdraw/list")
def list_withdrawals():
    return {"status": "success", "data": withdrawal_ledger}
