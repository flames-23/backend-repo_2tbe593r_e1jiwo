import os
from datetime import datetime, date
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User, Like, Message, AdminAction, SearchQuery

import stripe

STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
stripe.api_key = STRIPE_API_KEY

app = FastAPI(title="MatchLife API", description="Serius, aman, dan jujur — tempat menemukan pasangan yang benar-benar siap menikah.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
class IdModel(BaseModel):
    id: str


def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")


def user_to_public(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc["id"] = str(doc.pop("_id"))
    return doc


@app.get("/")
def root():
    return {"message": "MatchLife Backend running"}


# Payment and access
class CheckoutSessionRequest(BaseModel):
    email: str


@app.post("/api/create-checkout-session")
def create_checkout_session(payload: CheckoutSessionRequest):
    if not STRIPE_API_KEY:
        # In preview, allow bypass for demo purposes
        return {"checkout_url": "/onboarding?email=" + payload.email}
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{
                "price_data": {
                    "currency": "idr",
                    "product_data": {"name": "MatchLife Subscription"},
                    "unit_amount": 99000,
                    "recurring": {"interval": "month"}
                },
                "quantity": 1
            }],
            success_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + "/onboarding?email=" + payload.email,
            cancel_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + "/",
            customer_email=payload.email
        )
        return {"checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Profile create/update (after payment)
@app.post("/api/profile")
def create_or_update_profile(user: User):
    # Upsert by email
    existing = db["user"].find_one({"email": user.email})
    data = user.model_dump()
    data["updated_at"] = datetime.utcnow()
    if existing:
        db["user"].update_one({"_id": existing["_id"]}, {"$set": data})
        doc = db["user"].find_one({"_id": existing["_id"]})
        return user_to_public(doc)
    else:
        new_id = create_document("user", data)
        doc = db["user"].find_one({"_id": ObjectId(new_id)})
        return user_to_public(doc)


@app.get("/api/profile/{user_id}")
def get_profile(user_id: str):
    doc = db["user"].find_one({"_id": oid(user_id)})
    if not doc:
        raise HTTPException(404, "User not found")
    return user_to_public(doc)


# Search
@app.post("/api/search")
def search_profiles(q: SearchQuery):
    filters: Dict[str, Any] = {"approved": True}
    today = date.today()
    if q.usia_min is not None or q.usia_max is not None:
        # Convert age to date range
        conditions = {}
        if q.usia_min is not None:
            # born on or before this date => older or equal
            max_birth = date(today.year - q.usia_min, today.month, today.day)
            conditions["$lte"] = max_birth.isoformat()
        if q.usia_max is not None:
            min_birth = date(today.year - q.usia_max - 1, today.month, today.day)
            conditions["$gte"] = min_birth.isoformat()
        filters["tanggal_lahir"] = conditions
    if q.lokasi:
        filters["kota"] = {"$regex": q.lokasi, "$options": "i"}
    if q.agama:
        filters["agama"] = q.agama
    if q.level_agama:
        filters["level_agama"] = q.level_agama
    if q.pekerjaan:
        filters["pekerjaan"] = {"$regex": q.pekerjaan, "$options": "i"}
    if q.pendapatan_min is not None:
        filters["pendapatan_per_bulan"] = {"$gte": q.pendapatan_min}
    if q.pendidikan:
        filters["pendidikan"] = {"$regex": q.pendidikan, "$options": "i"}
    # Lifestyle partial filter
    if q.lifestyle:
        for k, v in q.lifestyle.model_dump(exclude_none=True).items():
            filters[f"lifestyle.{k}"] = v

    docs = get_documents("user", filters)
    result = [user_to_public(d) for d in docs]
    return {"results": result}


# Likes and matches
@app.post("/api/like")
def like_user(payload: Like):
    if payload.from_user_id == payload.to_user_id:
        raise HTTPException(400, "Cannot like yourself")
    u_from = db["user"].find_one({"_id": oid(payload.from_user_id)})
    u_to = db["user"].find_one({"_id": oid(payload.to_user_id)})
    if not u_from or not u_to:
        raise HTTPException(404, "User not found")
    # Add like
    db["user"].update_one({"_id": u_from["_id"]}, {"$addToSet": {"liked_user_ids": payload.to_user_id}})
    # Check mutual
    is_mutual = payload.from_user_id in (u_to.get("liked_user_ids") or [])
    if is_mutual:
        # Update both matches
        db["user"].update_one({"_id": u_from["_id"]}, {"$addToSet": {"matches": payload.to_user_id}})
        db["user"].update_one({"_id": u_to["_id"]}, {"$addToSet": {"matches": payload.from_user_id}})
    return {"mutual": is_mutual}


# Messaging (text only)
@app.get("/api/chat/{user_id}")
def get_user_chats(user_id: str):
    # Return matched users and last message summary
    user = db["user"].find_one({"_id": oid(user_id)})
    if not user:
        raise HTTPException(404, "User not found")
    matches = user.get("matches", [])
    match_docs = list(db["user"].find({"_id": {"$in": [oid(mid) for mid in matches]}})) if matches else []
    chats = []
    for md in match_docs:
        match_id = "-".join(sorted([user_id, str(md["_id"]) ]))
        last_msg = db["message"].find_one({"match_id": match_id}, sort=[("created_at", -1)])
        chats.append({
            "match_user": user_to_public(md),
            "last_message": last_msg.get("text") if last_msg else None
        })
    return {"chats": chats}


class SendMessage(BaseModel):
    from_user_id: str
    to_user_id: str
    text: str


@app.post("/api/chat/send")
def send_message(payload: SendMessage):
    # Only if matched
    u_from = db["user"].find_one({"_id": oid(payload.from_user_id)})
    if not u_from:
        raise HTTPException(404, "Sender not found")
    if payload.to_user_id not in (u_from.get("matches") or []):
        raise HTTPException(403, "You can only message matched users")
    match_id = "-".join(sorted([payload.from_user_id, payload.to_user_id]))
    doc = {
        "match_id": match_id,
        "sender_id": payload.from_user_id,
        "text": payload.text,
        "created_at": datetime.utcnow()
    }
    db["message"].insert_one(doc)
    return {"ok": True}


# Admin endpoints
@app.get("/api/admin/users")
def admin_list_users():
    docs = get_documents("user")
    return {"users": [user_to_public(d) for d in docs]}


@app.post("/api/admin/action")
def admin_action(action: AdminAction):
    user = db["user"].find_one({"_id": oid(action.user_id)})
    if not user:
        raise HTTPException(404, "User not found")
    if action.action == "approve":
        db["user"].update_one({"_id": user["_id"]}, {"$set": {"approved": True}})
    elif action.action == "reject":
        db["user"].delete_one({"_id": user["_id"]})
    elif action.action == "verify":
        db["user"].update_one({"_id": user["_id"]}, {"$set": {"verified": True}})
    elif action.action == "unverify":
        db["user"].update_one({"_id": user["_id"]}, {"$set": {"verified": False}})
    else:
        raise HTTPException(400, "Unknown action")
    return {"ok": True}


@app.get("/api/admin/stats")
def admin_stats():
    total = db["user"].count_documents({})
    approved = db["user"].count_documents({"approved": True})
    verified = db["user"].count_documents({"verified": True})
    with_matches = db["user"].count_documents({"matches.0": {"$exists": True}})
    return {
        "total_users": total,
        "approved_users": approved,
        "verified_users": verified,
        "users_with_matches": with_matches,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
