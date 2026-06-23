from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, EmailStr
import jwt
import httpx
import os
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/payment", tags=["Payment"])

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
PHP_API_URL = os.getenv("PHP_API_URL", "https://example.com/api/create-payment")


class StaffPaymentRequest(BaseModel):
    name: str
    email: str
    phone: str
    licence_number: str
    licence_expiry: str


def generate_service_token() -> str:
    payload = {
        "iss": "autobook-chatbot",
        "aud": "booking-service",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/verify")
async def verify_user(data: StaffPaymentRequest):
    token = generate_service_token()

    payload = {
        "name":           data.name,
        "email":          data.email,
        "phone":          data.phone,
        "licence_number": data.licence_number,
        "licence_expiry": data.licence_expiry,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                PHP_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if not response.is_success:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text,  # surface PHP error body
            )

        return response.json()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


# ── Test endpoint ─────────────────────────────────────────────────────────────
 
@router.post("/test-url")
async def test_url(data: StaffPaymentRequest):
    """
    Dry-run test endpoint — does NOT hit the real PHP API.
    Returns:
      - the payload that would be sent
      - the generated JWT token (raw)
      - the decoded JWT claims (so you can verify correctness)
      - a dummy payment link simulating what PHP would return
    """
    token = generate_service_token()
 
    # Decode token for inspection (no verify so it works even with dummy secret)
    try:
        decoded = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience="booking-service",
        )
        # Make timestamps human-readable
        decoded["iat"] = datetime.fromtimestamp(decoded["iat"], tz=timezone.utc).isoformat()
        decoded["exp"] = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc).isoformat()
        token_status = "valid"
    except jwt.ExpiredSignatureError:
        decoded = {"error": "Token expired"}
        token_status = "expired"
    except jwt.InvalidTokenError as e:
        decoded = {"error": str(e)}
        token_status = "invalid"
 
    payload = {
        "name":           data.name,
        "email":          data.email,
        "phone":          data.phone,
        "licence_number": data.licence_number,
        "licence_expiry": data.licence_expiry,
    }
 
    # Simulate what PHP would return
    dummy_php_response = {
        "success":      True,
        "payment_link": f"https://a1.starr365.com/app/b/?b=52907164",
        "message":      "Staff verified and payment link generated (DUMMY)",
    }
 
    return {
        "status":        "dry_run",
        "php_api_url":   PHP_API_URL,
        "payload_sent":  payload,
        "token": {
            "raw":     token,
            "status":  token_status,
            "decoded": decoded,
        },
        "dummy_php_response": dummy_php_response,
        "payment_link": dummy_php_response["payment_link"],
    }
    

# ── Payment webhook ─────────────────────────────────────────────────────────────
 
@router.post("/create-new-payment")
async def create(data: StaffPaymentRequest):
    print('new payment created')
    # accNum , staffId ,clientId,carId,profileId,fromDate,toDate,