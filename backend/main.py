import os
import datetime
import requests
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from security import verify_gateway_signature, generate_gateway_secret

app = FastAPI(title="Sovereign Functional Gateway Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_wallets = {
    "test_user": {"balance_coins": 1400, "balance_ugx": 50000}
}
gateway_ledger = []

class WithdrawalCommand(BaseModel):
    username: str
    amount_ugx: float
    airtel_phone: str

GATEWAY_SECRET_KEY = os.getenv("GATEWAY_SECRET_KEY", "FLWSECK_TEST-YOUR_SECRET_KEY_HERE")
GATEWAY_MASTER_KEY = os.getenv("GATEWAY_MASTER_KEY", "SOVEREIGN_GATEWAY_SECRET_SIGNING_KEY_2026")
GATEWAY_TRANSFER_URL = "https://api.flutterwave.com/v3/transfers"

@app.get("/")
def gateway_root():
    return {"status": "ONLINE", "engine": "Custom Gateway Bridge Active"}

@app.get("/api/wallet/{username}")
def get_wallet(username: str):
    if username not in user_wallets:
        user_wallets[username] = {"balance_coins": 1400, "balance_ugx": 50000}
    return {"status": "success", "data": user_wallets[username]}

@app.post("/api/withdraw/airtel")
async def execute_gateway_payout(
    request: Request,
    cmd: WithdrawalCommand,
    x_gateway_signature: str = Header(None)
):
    body_bytes = await request.body()
    
    # Enforce Cryptographic Signature Verification
    if not verify_gateway_signature(body_bytes, x_gateway_signature, GATEWAY_MASTER_KEY):
        raise HTTPException(status_code=401, detail="Gateway Access Denied: Invalid Cryptographic Signature.")

    if cmd.username not in user_wallets:
        user_wallets[cmd.username] = {"balance_coins": 1400, "balance_ugx": 50000}
    
    wallet = user_wallets[cmd.username]
    
    if wallet["balance_ugx"] < cmd.amount_ugx:
        raise HTTPException(status_code=400, detail="Gateway Error: Insufficient UGX balance.")
    
    phone = cmd.airtel_phone.strip()
    if not (phone.startswith("07") or phone.startswith("256")) or len(phone) < 10:
        raise HTTPException(status_code=400, detail="Gateway Firewall: Invalid phone number structure.")
    
    if cmd.amount_ugx < 500:
        raise HTTPException(status_code=400, detail="Gateway Firewall: Amount is below minimum threshold.")

    wallet["balance_ugx"] -= cmd.amount_ugx
    tx_reference = f"GW-UGX-{int(datetime.datetime.utcnow().timestamp())}"
    
    headers = {
        "Authorization": f"Bearer {GATEWAY_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "account_bank": "MPS",
        "account_number": phone,
        "amount": cmd.amount_ugx,
        "currency": "UGX",
        "narration": "TikTok Coin Store Automated Payout",
        "reference": tx_reference,
        "beneficiary_name": cmd.username
    }
    
    gateway_response_status = "PROCESSING"
    
    try:
        response = requests.post(GATEWAY_TRANSFER_URL, json=payload, headers=headers, timeout=15)
        res_data = response.json()
        
        if response.status_code in [200, 201] and res_data.get("status") == "success":
            gateway_response_status = "Disbursement Initiated (Live Rails Connected)"
        else:
            err_msg = res_data.get("message", "Gateway Refusal")
            gateway_response_status = f"Failed: {err_msg}"
            wallet["balance_ugx"] += cmd.amount_ugx
            
    except Exception as network_err:
        gateway_response_status = f"Gateway Network Error: {str(network_err)}"
        wallet["balance_ugx"] += cmd.amount_ugx

    ledger_record = {
        "payout_id": tx_reference,
        "username": cmd.username,
        "amount_ugx": cmd.amount_ugx,
        "airtel_phone": phone,
        "status": gateway_response_status,
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    gateway_ledger.insert(0, ledger_record)

    return {
        "status": "success",
        "payout_id": tx_reference,
        "message": gateway_response_status,
        "remaining_balance": wallet["balance_ugx"]
    }

@app.get("/api/withdraw/list")
def get_gateway_ledger():
    return {"status": "success", "data": gateway_ledger}
