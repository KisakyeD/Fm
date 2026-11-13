from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime

app = FastAPI(title="TikTok Coin & Wallet Payout Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent user wallet memory
user_wallets = {
    "test_user": {"balance_coins": 1400, "balance_ugx": 50000}
}
withdrawal_queue = []

class WithdrawalRequest(BaseModel):
    username: str
    amount_ugx: float
    airtel_phone: str

@app.get("/")
def home():
    return {"status": "online", "system": "TikTok Coin Store & Airtel Payout Engine"}

@app.get("/api/wallet/{username}")
def get_wallet(username: str):
    if username not in user_wallets:
        user_wallets[username] = {"balance_coins": 1400, "balance_ugx": 50000}
    return {"status": "success", "data": user_wallets[username]}

@app.post("/api/withdraw/airtel")
def request_airtel_withdrawal(req: WithdrawalRequest):
    if req.username not in user_wallets:
        user_wallets[req.username] = {"balance_coins": 1400, "balance_ugx": 50000}
    
    current_cash = user_wallets[req.username]["balance_ugx"]
    if current_cash < req.amount_ugx:
        raise HTTPException(status_code=400, detail="Insufficient UGX balance for withdrawal.")
    
    # Deduct balance
    user_wallets[req.username]["balance_ugx"] -= req.amount_ugx
    
    payout_id = f"AT-PO-{int(datetime.datetime.utcnow().timestamp())}"
    payout_record = {
        "payout_id": payout_id,
        "username": req.username,
        "amount_ugx": req.amount_ugx,
        "airtel_phone": req.airtel_phone,
        "status": "Processing Disbursement",
        "time": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    
    withdrawal_queue.insert(0, payout_record)
    return {
        "status": "success",
        "payout_id": payout_id,
        "message": f"Successfully initiated payout of UGX {req.amount_ugx} to Airtel line {req.airtel_phone}."
    }

@app.get("/api/withdraw/list")
def list_withdrawals():
    return {"status": "success", "data": withdrawal_queue}
