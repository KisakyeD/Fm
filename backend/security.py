import secrets
import hmac
import hashlib

# 1. Programmatically generate a secure master gateway secret key
def generate_gateway_secret() -> str:
    """Generates a cryptographically secure 64-character hex secret key."""
    return secrets.token_hex(32)

# Example output: "4f8c2b9a... (64 random hex characters)"
MASTER_GATEWAY_KEY = generate_gateway_secret()


# 2. Code to sign outgoing or incoming gateway commands
def sign_gateway_payload(payload_bytes: bytes, secret_key: str) -> str:
    """Creates an HMAC-SHA256 cryptographic signature to verify command authenticity."""
    return hmac.new(
        secret_key.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()


# 3. Code to verify the signature on the gateway server
def verify_gateway_signature(payload_bytes: bytes, received_signature: str, secret_key: str) -> bool:
    """Validates that the request was genuinely signed by your application."""
    expected_signature = hmac.new(
        secret_key.encode('utf-8'),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, received_signature or "")
