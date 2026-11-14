import os
import hmac
import hashlib
import datetime
import requests
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Custom Sovereign Payment Gateway Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Immutable transaction ledger & secure gateway state
gateway_ledger = []
idempotency_cache = set()

class PayoutCommand(BaseModel):
    merchant_id: str
    amount_ugx: float
    destination_phone: str
    currency: str = "UGX"

# Sovereign Gateway Security Constants (Load securely via environment variables)
GATEWAY_MASTER_KEY = os.getenv("GATEWAY_MASTER_KEY", "SOVEREIGN_GATEWAY_SECRET_SIGNING_KEY_2026")
TELCO_DISBURSE_ENDPOINT = os.getenv("TELCO_DISBURSE_ENDPOINT", "https://openapi.airtel.africa/standard/v1/disbursements/")

def verify_cryptographic_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Cryptographically verifies incoming merchant command signatures to break authorization walls."""
    expected_signature = hmac.new(
        GATEWAY_MASTER_KEY.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature_header or "")

def algorithmic_gateway_risk_engine(amount: float, phone: str) -> dict:
    """The Middleman Algorithm acting as the autonomous gatekeeper."""
    if amount <= 0:
        return {"authorized": False, "reason": "Zero or negative asset transmission rejected."}
    if amount > 5000000:
        return {"authorized": False, "reason": "Transaction exceeds sovereign gateway daily single-cap limit."}
    
    clean_phone = phone.strip()
    if not (clean_phone.startswith("07") or clean_phone.startswith("256")) or len(clean_phone) < 10:
        return {"authorized": False, "reason": "Malformed destination node address (Invalid MSISDN)."}
        
    return {"authorized": True, "reason": "Gateway checks cleared successfully."}

@app.get("/")
def gateway_status():
    return {
        "gateway_status": "OPERATIONAL",
        "protocol": "REST/JSON",
        "ledger_entries": len(gateway_ledger)
    }

@app.post("/api/gateway/command/disburse")
async def execute_gateway_disbursement(
    request: Request,
    command: PayoutCommand,
    x_idempotency_key: str = Header(None),
    x_gateway_signature: str = Header(None)
):
    """
    Core Gateway Command: Intercepts raw request bytes, validates cryptographic signature,
    enforces idempotency, runs algorithmic risk checks, and fires direct payout commands.
    """
    body_bytes = await request.body()
    
    # 1. Cryptographic Security Check
    if not verify_cryptographic_signature(body_bytes, x_gateway_signature):
        raise HTTPException(status_code=401, detail="Gateway Access Denied: Invalid Cryptographic Signature.")

    # 2. Idempotency Wall (Prevent double payouts from network retries)
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail="Gateway Error: Missing X-Idempotency-Key header.")
    
    if x_idempotency_key in idempotency_cache:
        raise HTTPException(status_code=409, detail="Conflict: Duplicate transaction reference detected by gateway.")
    
    idempotency_cache.add(x_idempotency_key)

    # 3. Algorithmic Risk Evaluation
    risk_assessment = algorithmic_gateway_risk_engine(command.amount_ugx, command.destination_phone)
    if not risk_assessment["authorized"]:
        raise HTTPException(status_code=403, detail=f"Gateway Firewall Blocked: {risk_assessment['reason']}")

    # 4. Generate Unique Gateway Reference
    gateway_tx_id = f"GW-SVRV-{int(datetime.datetime.utcnow().timestamp())}"
    
    # 5. Build Direct Telco Payload (Acting as the bridge)
    telco_payload = {
        "payee": {
            "wallet_type": "MSISDN",
            "msisdn": command.destination_phone.strip()
        },
        "reference": gateway_tx_id,
        "transaction": {
            "amount": command.amount_ugx,
            "country": "UG",
            "currency": command.currency,
            "id": gateway_tx_id
        }
    }

    transmission_status = "PENDING_DISPATCH"
    
    try:
        # Fire direct API command to telco infrastructure
        telco_response = requests.post(
            TELCO_DISBURSE_ENDPOINT,
            json=telco_payload,
            headers={"Content-Type": "application/json", "X-Country": "UG", "X-Currency": "UGX"},
            timeout=10
        )
        
        if telco_response.status_code in [200, 201]:
            transmission_status = "DISBURSED_SUCCESSFULLY"
        else:
            transmission_status = f"TELCO_REJECTED: {telco_response.text}"
    except Exception as network_error:
        transmission_status = f"GATEWAY_SOCKET_ERROR: {str(network_error)}"

    # Record to Immutable Ledger
    ledger_record = {
        "gateway_tx_id": gateway_tx_id,
        "idempotency_key": x_idempotency_key,
        "merchant_id": command.merchant_id,
        "amount_ugx": command.amount_ugx,
        "destination": command.destination_phone.strip(),
        "status": transmission_status,
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    
    gateway_ledger.insert(0, ledger_record)

    return {
        "status": "success",
        "gateway_tx_id": gateway_tx_id,
        "transmission_status": transmission_status
    }

@app.get("/api/gateway/ledger")
def fetch_gateway_ledger():
    return {"status": "success", "ledger": gateway_ledger}
