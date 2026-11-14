from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime
import requests

app = FastAPI(title="Algorithmic Payout Middleman Engine")

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
withdrawal_queue = []

class WithdrawalRequest(BaseModel):
    username: str
    amount_ugx: float
    airtel_phone: str

# Gateway configuration (e.g., Flutterwave or local Payer API)
GATEWAY_SECRET_KEY = "FLWSECK_TEST-YOUR_SECRET_KEY_HERE"
GATEWAY_BASE_URL = "https://api.flutterwave.com/v3"

def algorithmic_risk_assessment(username: str, amount: float, phone: str) -> dict:
    """
    Automated Middleman Algorithm:
    Evaluates risk metrics, account history, and thresholds to 
    automatically approve or flag payout requests.
    """
    # Rule 1: Check maximum single payout limit (e.g., 1,000,000 UGX max per transaction)
    if amount > 1000000:
        return {"approved": False, "reason": "Amount exceeds automated algorithmic threshold. Flagged for review."}
    
    # Rule 2: Validate Ugandan phone carrier formatting via algorithm
    clean_phone = phone.strip()
    if not (clean_phone.startswith("07") or clean_phone.startswith("256")) or len(clean_phone) < 10:
        return {"approved": False, "reason": "Invalid mobile money routing format."}

    # Rule 3: Velocity check (prevent rapid-fire spam requests)
    recent_user_txs = [tx for tx in withdrawal_queue if tx["username"] == username]
    if len(recent_user_txs) >= 5:
        return {"approved": False, "reason": "Velocity limit reached: Maximum daily automated payouts exceeded."}

    return {"approved": True, "reason": "Passed automated risk checks."}

@app.get("/")
def home():
    return {"status": "online", "system": "Algorithmic Middleman Payout Engine Active"}

@app.get("/api/wallet/{username}")
def get_wallet(username: str):
    if username not in user_wallets:
        user_wallets[username] = {"balance_coins": 1400, "balance_ugx": 50000}
    return {"status": "success", "data": user_wallets[username]}

@app.post("/api/withdraw/airtel")
def request_airtel_withdrawal(req: WithdrawalRequest):
    if req.username not in user_wallets:
        user_wallets[req.username] = {"balance_coins": 1400, "balance_ugx": 50000}
    
    wallet = user_wallets[req.username]
    if wallet["balance_ugx"] < req.amount_ugx:
        raise HTTPException(status_code=400, detail="Insufficient UGX balance for withdrawal.")
    
    # --- STEP 1: RUN THE ALGORITHMIC MIDDLEMAN DECISION ---
    decision = algorithmic_risk_assessment(req.username, req.amount_ugx, req.airtel_phone)
    
    if not decision["approved"]:
        raise HTTPException(status_code=403, detail=f"Automated Middleman Rejected: {decision['reason']}")

    # --- STEP 2: AUTO-DEDUCT & GENERATE REFERENCE ---
    wallet["balance_ugx"] -= req.amount_ugx
    reference = f"AUTO-PO-{int(datetime.datetime.utcnow().timestamp())}"
    
    headers = {
        "Authorization": f"Bearer {GATEWAY_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "account_bank": "MPS",
        "account_number": req.airtel_phone.strip(),
        "amount": req.amount_ugx,
        "currency": "UGX",
        "narration": "Automated TikTok Coin Payout",
        "reference": reference,
        "beneficiary_name": req.username
    }
    
    status_message = "Algorithm Approved: Disbursing via Gateway"
    
    try:
        # --- STEP 3: AUTOMATED DISBURSEMENT API CALL ---
        response = requests.post(f"{GATEWAY_BASE_URL}/transfers", json=payload, headers=headers)
        res_data = response.json()
        
        if response.status_code in [200, 201] and res_data.get("status") == "success":
            status_message = "Disbursement Initiated Successfully"
        else:
            err_msg = res_data.get("message", "Gateway Refusal")
            status_message = f"Gateway Error: {err_msg}"
            # Automated rollback: refund balance if gateway fails
            wallet["balance_ugx"] += req.amount_ugx
    except Exception as e:
        status_message = f"Network Disruption: {str(e)}"
        wallet["balance_ugx"] += req.amount_ugx

    payout_record = {
        "payout_id": reference,
        "username": req.username,
        "amount_ugx": req.amount_ugx,
        "airtel_phone": req.airtel_phone,
        "status": status_message,
        "time": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    
    withdrawal_queue.insert(0, payout_record)
    
    return {
        "status": "success",
        "payout_id": reference,
        "message": status_message
    }

@app.post("/api/webhook/gateway")
async def gateway_webhook(request: Request):
    """Automated listener that updates statuses when funds clear on Airtel."""
    body = await request.json()
    data = body.get("data", {})
    reference = data.get("reference")
    status = data.get("status")
    
    for item in withdrawal_queue:
        if item["payout_id"] == reference:
            if status == "SUCCESSFUL":
                item["status"] = "Confirmed on Airtel Line"
            elif status == "FAILED":
                item["status"] = "Disbursement Failed"
            break
            
    return {"status": "received"}

@app.get("/api/withdraw/list")
def list_withdrawals():
    return {"status": "success", "data": withdrawal_queue}
