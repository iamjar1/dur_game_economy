from fastapi import FastAPI, HTTPException, Header
from typing import Optional
from . import services
from .models import (
    CreditRequest, PurchaseRequest, ClaimRequest,
    WalletResponse, CreditResponse, PurchaseResponse, ClaimResponse,
    ErrorResponse
)
from .database import init_db, cleanup_expired_keys

app = FastAPI(title="Game Economy Service", version="1.0.0")

@app.on_event("startup")
def startup():
    init_db()
    cleanup_expired_keys()

@app.on_event("startup")
def startup_periodic_cleanup():
    import asyncio
    async def cleanup_loop():
        while True:
            await asyncio.sleep(3600)
            cleanup_expired_keys()
    asyncio.create_task(cleanup_loop())

@app.post(
    "/v1/wallets/{player_id}/credit",
    response_model=CreditResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
)
def credit_wallet(player_id: str, request: CreditRequest, idempotency_key: Optional[str] = Header(None)):
    if not idempotency_key:
        idempotency_key = f"auto_{player_id}_credit_{request.amount}_{hash(request.reason)}"
    
    try:
        result = services.credit_wallet(player_id, request.amount, request.reason, idempotency_key)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": "CREDIT_FAILED", "message": str(e)})

@app.post(
    "/v1/wallets/{player_id}/purchase",
    response_model=PurchaseResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
)
def purchase_item(player_id: str, request: PurchaseRequest, idempotency_key: Optional[str] = Header(None)):
    if not idempotency_key:
        idempotency_key = f"auto_{player_id}_purchase_{request.itemId}_{request.price}"
    
    try:
        result = services.purchase_item(player_id, request.itemId, request.price, idempotency_key)
        return result
    except ValueError as e:
        error_type = "INSUFFICIENT_FUNDS" if "Insufficient" in str(e) else "PURCHASE_FAILED"
        raise HTTPException(status_code=400, detail={"success": False, "error": error_type, "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": "PURCHASE_FAILED", "message": str(e)})

@app.post(
    "/v1/rewards/{reward_id}/claim",
    response_model=ClaimResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
)
def claim_reward(reward_id: str, request: ClaimRequest, idempotency_key: Optional[str] = Header(None)):
    if not idempotency_key:
        idempotency_key = f"auto_{request.playerId}_claim_{reward_id}"
    
    try:
        result = services.claim_reward(request.playerId, reward_id, idempotency_key)
        return result
    except ValueError as e:
        error_type = "ALREADY_CLAIMED" if "already claimed" in str(e) else "CLAIM_FAILED"
        raise HTTPException(status_code=400, detail={"success": False, "error": error_type, "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": "CLAIM_FAILED", "message": str(e)})

@app.get("/v1/wallets/{player_id}", response_model=WalletResponse)
def get_wallet(player_id: str):
    return services.get_wallet(player_id)

@app.get("/health")
def health_check():
    return {"status": "healthy"}