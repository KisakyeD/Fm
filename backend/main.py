from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import datetime
import requests

app = FastAPI(title="TikTok Coin & Wallet Payout Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock databases for demonstration (Replace with PostgreSQL/SQLite in production)
user_wallets = {
    "test_user": {"balance_coins": 1400, "balance_ugx": 50000}
}
withdrawal_queue = []

class WithdrawalRequest(BaseModel):
    username: str
    amount_ugx: float
    airtel_phone: str

class CoinOrder(BaseModel):
    tiktok_username: str
    coin_amount: int
    total_price_ugx: float

@app.get("/")
def home():
    return {"status": "online", "system": "TikTok Coin Store & Airtel Payout Engine"}

@app.get("/api/wallet/{username}")
def get_wallet(username: str):
    """Fetch user's current coin and cash balance."""
    if username not in user_wallets:
        user_wallets[username] = {"balance_coins": 0, "balance_ugx": 0}
    return {"status": "success", "data": user_wallets[username]}

@app.post("/api/withdraw/airtel")
def request_airtel_withdrawal(req: WithdrawalRequest):
    """
    Handles user withdrawal requests directly to an Airtel Mobile Money phone number.
    """
    if req.username not in user_wallets:
        raise HTTPException(status_code=404, detail="User account not found.")
    
    current_cash = user_wallets[req.username]["balance_ugx"]
    if current_cash < req.amount_ugx:
        raise HTTPException(status_code=400, detail="Insufficient UGX balance for withdrawal.")
    
    # Deduct balance immediately (Escrow/Pending State)
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
    
    # NOTE: In a live environment, you would trigger the Airtel Money Disburse API here 
    # using your credentials from the Airtel Developer Portal.
    
    return {
        "status": "success",
        "payout_id": payout_id,
        "message": f"Successfully initiated payout of UGX {req.amount_ugx} to Airtel line {req.airtel_phone}."
    }

@app.get("/api/withdraw/list")
def list_withdrawals():
    return {"status": "success", "data": withdrawal_queue}
