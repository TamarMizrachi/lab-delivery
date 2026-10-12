from fastapi import FastAPI, Request, status, Query
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid request payload"}
    )

class DeliveryStatus(str, Enum):
    created = "created"
    in_transit = "in_transit"
    delivered = "delivered"
    canceled = "canceled"

class DeliveryCreate(BaseModel):
    recipient: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)

class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus

class Delivery(BaseModel):
    id: int
    recipient: str
    address: str
    status: DeliveryStatus

deliveries_db: dict[int, Delivery] = {}
next_id: int = 1

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/deliveries", response_model=Delivery, status_code=status.HTTP_201_CREATED)
def create_delivery(item: DeliveryCreate):
    global next_id
    if not item.recipient.strip() or not item.address.strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Recipient and address cannot be empty"}
        )
    new_delivery = Delivery(
        id=next_id,
        recipient=item.recipient,
        address=item.address,
        status=DeliveryStatus.created
    )
    deliveries_db[next_id] = new_delivery
    next_id += 1
    return new_delivery

@app.get("/deliveries", response_model=List[Delivery])
def get_deliveries(status: Optional[DeliveryStatus] = Query(None)):
    if status:
        return [d for d in deliveries_db.values() if d.status == status]
    return list(deliveries_db.values())

@app.get("/deliveries/{delivery_id}", response_model=Delivery)
def get_delivery(delivery_id: int):
    if delivery_id not in deliveries_db:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Delivery not found"}
        )
    return deliveries_db[delivery_id]

@app.patch("/deliveries/{delivery_id}/status", response_model=Delivery)
def update_delivery_status(delivery_id: int, update_data: DeliveryStatusUpdate):
    if delivery_id not in deliveries_db:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Delivery not found"}
        )
    
    delivery = deliveries_db[delivery_id]
    current_status = delivery.status
    new_status = update_data.status

    allowed_transitions = {
        DeliveryStatus.created: [DeliveryStatus.in_transit, DeliveryStatus.canceled],
        DeliveryStatus.in_transit: [DeliveryStatus.delivered, DeliveryStatus.canceled],
        DeliveryStatus.delivered: [],
        DeliveryStatus.canceled: []
    }

    if new_status not in allowed_transitions.get(current_status, []):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": f"Cannot transition from {current_status} to {new_status}"}
        )

    delivery.status = new_status
    deliveries_db[delivery_id] = delivery
    return delivery

@app.delete("/deliveries/{delivery_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_delivery(delivery_id: int):
    if delivery_id not in deliveries_db:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Delivery not found"}
        )
    
    if deliveries_db[delivery_id].status == DeliveryStatus.delivered:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "Delivered delivery cannot be deleted"}
        )

    del deliveries_db[delivery_id]
    return None