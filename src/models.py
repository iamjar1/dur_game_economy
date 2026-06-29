from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class CreditRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount to credit (must be positive)")
    reason: str = Field(..., min_length=1, max_length=255, description="Reason for credit")

class PurchaseRequest(BaseModel):
    itemId: str = Field(..., min_length=1, max_length=255, description="Item to purchase")
    price: int = Field(..., gt=0, description="Price (must be positive)")

class ClaimRequest(BaseModel):
    playerId: str = Field(..., min_length=1, max_length=255, description="Player claiming reward")

class WalletResponse(BaseModel):
    playerId: str
    balance: int
    inventory: List[str]
    claimedRewards: List[str]

class CreditResponse(BaseModel):
    success: bool
    balance: int
    transactionId: str

class PurchaseResponse(BaseModel):
    success: bool
    balance: int
    itemId: str
    transactionId: str

class ClaimResponse(BaseModel):
    success: bool
    rewardId: str
    claimedAt: str

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    message: str
    details: Optional[dict] = None