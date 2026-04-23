from fastapi import FastAPI, HTTPException, status, Depends, Query, Body, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from typing import List, Optional
from bson import ObjectId
import bcrypt
from jose import JWTError, jwt
import os
from dotenv import load_dotenv
from database import (
    bookings_collection, 
    images_collection, 
    videos_collection,
    reviews_collection,
    users_collection,
    messages_collection,
    create_indexes
)
from model import (
    BookingModel, GalleryImageModel,  VideoModel,ReviewModel,  MessageModel,LoginRequest, TokenResponse,UpdateStatusRequest,ServiceListModel,BookingResponse,DailyStatsModel
)

load_dotenv()

app = FastAPI(
    title="Salon Management System API",
    description="API for managing salon bookings, gallery, and admin functions",
    version="1.0.0"
)
conf = ConnectionConfig(
    MAIL_USERNAME="esthermusam@gmail.com",
    MAIL_PASSWORD="qkoxymjitfmdxwat",
    MAIL_FROM="esthermusam@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# Startup event
@app.on_event("startup")
async def startup_event():
    await create_indexes()
    # Create default admin user if not exists
    await create_default_admin()

async def create_default_admin():
    """Create default admin user if it doesn't exist"""
    admin_username = os.getenv("ADMIN_USERNAME", "salonowner")
    admin_password = os.getenv("ADMIN_PASSWORD", "securepassword123")
    
    existing_admin = await users_collection.find_one({"username": admin_username})
    if not existing_admin:
        password_hash = get_password_hash(admin_password)
        admin_user = {
            "username": admin_username,
            "password_hash": password_hash,
            "role": "admin",
            "created_at": datetime.now()
        }
        await users_collection.insert_one(admin_user)
        print(f"Default admin user created: {admin_username}")

# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Query(...)):
    """Dependency to get current user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

# ============ AUTHENTICATION ENDPOINTS ============

@app.post("/api/auth/login")
async def admin_login(
    username: str = Form(...),
    password: str = Form(...)
):
    user = await users_collection.find_one({"username": username})
    
    # Step 1: Check credentials
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # ✅ Step 2: Check if user is admin
    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Not authorized as admin"
        )
    
    # Step 3: Continue if admin
    await users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.now()}}
    )
    
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@app.get("/api/auth/verify")
async def verify_token(token: str = Query(...)):
    """Verify if token is valid"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"valid": True, "username": payload.get("sub"), "role": payload.get("role")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============ BOOKING ENDPOINTS ============

@app.post("/api/bookings", response_model=dict)
async def create_booking(booking: BookingModel):
    """Create a new booking"""
    # Check if time slot is already booked
    existing_booking = await bookings_collection.find_one({
        "booking_date": booking.booking_date,
        "booking_time": booking.booking_time,
        "status": {"$in": ["pending", "confirmed"]}
    })
    
    if existing_booking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This time slot is already booked. Please choose another time."
        )
    
    booking_dict = booking.dict(by_alias=True)
    result = await bookings_collection.insert_one(booking_dict)
    
    return {
        "message": "Booking created successfully",
        "booking_id": str(result.inserted_id),
        "status": "pending"
    }
@app.get("/api/bookings/date/{date}", response_model=List[BookingResponse])
async def get_bookings_by_date(date: str):
    """Get all bookings for a specific date (public)"""
    bookings = await bookings_collection.find(
        {"booking_date": date, "status": {"$ne": "cancelled"}}
    ).to_list(length=100)
    
    return [
        BookingResponse(
            id=str(b["_id"]),
            client_name=b["client_name"],
            client_email=b["client_email"],
            client_phone=b["client_phone"],
            booking_date=b["booking_date"],
            booking_time=b["booking_time"],
            hairstyle_type=b["hairstyle_type"],
            special_requests=b.get("special_requests"),
            status=b["status"],
            created_at=b["created_at"]
        ) for b in bookings
    ]

@app.get("/api/bookings/admin/all", response_model=List[BookingResponse])
async def get_all_bookings(token: str = Query(...)):
    """Get all bookings (admin only)"""
    await get_current_user(token)
    
    bookings = await bookings_collection.find().sort("created_at", -1).to_list(length=1000)
    return [
        BookingResponse(
            id=str(b["_id"]),
            client_name=b["client_name"],
            client_email=b["client_email"],
            client_phone=b["client_phone"],
            booking_date=b["booking_date"],
            booking_time=b["booking_time"],
            hairstyle_type=b["hairstyle_type"],
            special_requests=b.get("special_requests"),
            status=b["status"],
            created_at=b["created_at"]
        ) for b in bookings
    ]

@app.put("/api/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: str, 
    status_data: UpdateStatusRequest,
    token: str = Query(...)
):
    await get_current_user(token)

    if not ObjectId.is_valid(booking_id):
        raise HTTPException(status_code=400, detail="Invalid booking ID")

    booking = await bookings_collection.find_one({"_id": ObjectId(booking_id)})

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    await bookings_collection.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {"status": status_data.status}}
    )

    # ✅ SEND EMAIL ONLY IF CONFIRMED
    if status_data.status == "confirmed":
        await send_confirmation_email(
            booking["client_email"],
            booking["client_name"],
            booking["booking_date"],
            booking["booking_time"]
        )

    return {"message": f"Booking status updated to {status_data.status}"}
@app.get("/api/bookings/stats/daily", response_model=List[DailyStatsModel])
async def get_daily_stats(token: str = Query(...)):
    """Get daily booking statistics (admin only)"""
    await get_current_user(token)
    
    pipeline = [
        {
            "$group": {
                "_id": "$booking_date",
                "total_bookings": {"$sum": 1},
                "confirmed": {"$sum": {"$cond": [{"$eq": ["$status", "confirmed"]}, 1, 0]}},
                "pending": {"$sum": {"$cond": [{"$eq": ["$status", "pending"]}, 1, 0]}},
                "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
                "rescheduled": {"$sum": {"$cond": [{"$eq": ["$status", "rescheduled"]}, 1, 0]}}
            }
        },
        {"$sort": {"_id": -1}},
        {"$limit": 30}
    ]
    
    stats = await bookings_collection.aggregate(pipeline).to_list(length=30)
    return [
        DailyStatsModel(
            date=stat["_id"],
            total_bookings=stat["total_bookings"],
            confirmed=stat["confirmed"],
            pending=stat["pending"],
            cancelled=stat["cancelled"],
            rescheduled=stat["rescheduled"]
        ) for stat in stats
    ]

@app.get("/api/available-slots/{date}")
async def get_available_slots(date: str):
    """Get available time slots for a specific date"""
    all_slots = [
        "09:00", "10:00", "11:00", "12:00", "13:00",
        "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"
    ]
    
    # Get booked slots for the date
    booked_slots_cursor = bookings_collection.find(
        {"booking_date": date, "status": {"$in": ["pending", "confirmed"]}}
    )
    booked_slots = await booked_slots_cursor.to_list(length=100)
    booked_times = [b["booking_time"] for b in booked_slots]
    
    available_slots = [slot for slot in all_slots if slot not in booked_times]
    
    return {
        "date": date,
        "available_slots": available_slots,
        "booked_slots": booked_times
    }

# ============ GALLERY IMAGE ENDPOINTS ============

@app.post("/api/gallery/images")
async def add_gallery_image(
    title: str,
    description: str,
    image_url: str,
    category: str,
    token: str = Query(...)
):
    """Add a new image to gallery (admin only)"""
    await get_current_user(token)
    
    image = GalleryImageModel(
        title=title,
        description=description,
        image_url=image_url,
        category=category
    )
    
    result = await images_collection.insert_one(image.dict(by_alias=True))
    return {"message": "Image added successfully", "image_id": str(result.inserted_id)}

@app.get("/api/gallery/images")
async def get_all_images():
    """Get all gallery images"""
    images = await images_collection.find().sort("upload_date", -1).to_list(length=100)
    return [
        {
            "id": str(img["_id"]),
            "title": img["title"],
            "description": img["description"],
            "image_url": img["image_url"],
            "category": img["category"],
            "average_rating": img.get("average_rating", 0),
            "ratings": img.get("ratings", []),
            "upload_date": img["upload_date"]
        }
        for img in images
    ]

@app.get("/api/gallery/images/{image_id}")
async def get_single_image(image_id: str):
    """Get a single image by ID"""
    if not ObjectId.is_valid(image_id):
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    image = await images_collection.find_one({"_id": ObjectId(image_id)})
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return {
        "id": str(image["_id"]),
        "title": image["title"],
        "description": image["description"],
        "image_url": image["image_url"],
        "category": image["category"],
        "average_rating": image.get("average_rating", 0),
        "ratings": image.get("ratings", []),
        "upload_date": image["upload_date"]
    }

@app.put("/api/gallery/images/{image_id}")
async def update_image(image_id: str, image_data: dict, token: str = Query(...)):
    """Update image details (admin only)"""
    await get_current_user(token)
    if not ObjectId.is_valid(image_id):
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    result = await images_collection.update_one(
        {"_id": ObjectId(image_id)},
        {"$set": image_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return {"message": "Image updated successfully"}

@app.delete("/api/gallery/images/{image_id}")
async def delete_image(image_id: str, token: str = Query(...)):
    """Delete an image from gallery (admin only)"""
    await get_current_user(token)
    
    if not ObjectId.is_valid(image_id):
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    # Delete associated reviews
    await reviews_collection.delete_many({"image_id": image_id})
    
    result = await images_collection.delete_one({"_id": ObjectId(image_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return {"message": "Image deleted successfully"}

# ============ VIDEO ENDPOINTS ============

@app.post("/api/gallery/videos")
async def add_video(video: VideoModel, token: str = Query(...)):
    """Add a new video to gallery (admin only)"""
    await get_current_user(token)
    
    result = await videos_collection.insert_one(video.dict(by_alias=True))
    return {"message": "Video added successfully", "video_id": str(result.inserted_id)}

@app.get("/api/gallery/videos")
async def get_all_videos():
    """Get all gallery videos"""
    videos = await videos_collection.find().sort("upload_date", -1).to_list(length=100)
    return [
        {
            "id": str(vid["_id"]),
            "title": vid["title"],
            "description": vid["description"],
            "video_url": vid["video_url"],
            "thumbnail_url": vid.get("thumbnail_url", ""),
            "category": vid["category"],
            "views": vid.get("views", 0),
            "upload_date": vid["upload_date"]
        }
        for vid in videos
    ]

@app.put("/api/gallery/videos/{video_id}/view")
async def increment_video_views(video_id: str):
    """Increment video view count"""
    if not ObjectId.is_valid(video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID")
    
    await videos_collection.update_one(
        {"_id": ObjectId(video_id)},
        {"$inc": {"views": 1}}
    )
    return {"message": "View count updated"}

# ============ REVIEW ENDPOINTS ============

@app.post("/api/reviews")
async def add_review(review: ReviewModel):
    """Add a review for an image"""
    if not ObjectId.is_valid(review.image_id):
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    # Check if image exists
    image = await images_collection.find_one({"_id": ObjectId(review.image_id)})
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Add review
    review_dict = review.dict(by_alias=True)
    result = await reviews_collection.insert_one(review_dict)
    
    # Update image ratings
    all_reviews = await reviews_collection.find({"image_id": review.image_id}).to_list(length=1000)
    ratings = [r["rating"] for r in all_reviews]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    
    await images_collection.update_one(
        {"_id": ObjectId(review.image_id)},
        {
            "$push": {"ratings": review.rating},
            "$set": {"average_rating": round(avg_rating, 1)}
        }
    )
    
    return {
        "message": "Review added successfully",
        "review_id": str(result.inserted_id),
        "average_rating": round(avg_rating, 1)
    }

@app.get("/api/reviews/{image_id}")
async def get_image_reviews(image_id: str):
    """Get all reviews for an image"""
    if not ObjectId.is_valid(image_id):
        raise HTTPException(status_code=400, detail="Invalid image ID")
    
    reviews = await reviews_collection.find(
        {"image_id": image_id}
    ).sort("created_at", -1).to_list(length=100)
    
    return [
        {
            "id": str(r["_id"]),
            "client_name": r["client_name"],
            "rating": r["rating"],
            "comment": r["comment"],
            "created_at": r["created_at"]
        }
        for r in reviews
    ]

# ============ MESSAGE ENDPOINTS ============

@app.post("/api/messages")
async def send_message(message: MessageModel):
    """Send a message from admin to client"""
    if not ObjectId.is_valid(message.booking_id):
        raise HTTPException(status_code=400, detail="Invalid booking ID")
    
    result = await messages_collection.insert_one(message.dict(by_alias=True))
    return {"message": "Message sent successfully", "message_id": str(result.inserted_id)}

@app.get("/api/messages/unread")
async def get_unread_messages(token: str = Query(...)):
    """Get all unread messages (admin only)"""
    await get_current_user(token)
    
    messages = await messages_collection.find({"status": "unread"}).sort("created_at", -1).to_list(length=100)
    return [
        {
            "id": str(m["_id"]),
            "booking_id": m["booking_id"],
            "message": m["message"],
            "status": m["status"],
            "created_at": m["created_at"]
        }
        for m in messages
    ]

@app.put("/api/messages/{message_id}/respond")
async def respond_to_message(message_id: str, response: str = Body(...), token: str = Query(...)):
    """Respond to a client message (admin only)"""
    await get_current_user(token)
    
    if not ObjectId.is_valid(message_id):
        raise HTTPException(status_code=400, detail="Invalid message ID")
    
    result = await messages_collection.update_one(
        {"_id": ObjectId(message_id)},
        {
            "$set": {
                "response": response,
                "status": "responded",
                "responded_at": datetime.now()
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return {"message": "Response sent successfully"}

@app.get("/api/messages/booking/{booking_id}")
async def get_messages_for_booking(booking_id: str, token: str = Query(...)):
    """Get all messages for a specific booking (admin only)"""
    await get_current_user(token)
    
    if not ObjectId.is_valid(booking_id):
        raise HTTPException(status_code=400, detail="Invalid booking ID")
    
    messages = await messages_collection.find({"booking_id": booking_id}).sort("created_at", 1).to_list(length=100)
    return [
        {
            "id": str(m["_id"]),
            "message": m["message"],
            "response": m.get("response"),
            "status": m["status"],
            "created_at": m["created_at"],
            "responded_at": m.get("responded_at")
        }
        for m in messages
    ]

# ============ SERVICES INFO ENDPOINT ============

@app.get("/api/services", response_model=ServiceListModel)
async def get_services():
    """Get all available services"""
    return ServiceListModel()

@app.get("/api/services/{category}")
async def get_services_by_category(category: str):
    """Get services by category"""
    services = ServiceListModel()
    service_dict = services.dict()
    
    if category not in service_dict:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return {
        "category": category,
        "services": service_dict[category]
    }

# ============ DASHBOARD STATS ENDPOINT ============

@app.get("/api/admin/dashboard/stats")
async def get_dashboard_stats(token: str = Query(...)):
    """Get comprehensive dashboard statistics (admin only)"""
    await get_current_user(token)
    
    # Get various stats
    total_bookings = await bookings_collection.count_documents({})
    pending_bookings = await bookings_collection.count_documents({"status": "pending"})
    confirmed_bookings = await bookings_collection.count_documents({"status": "confirmed"})
    total_images = await images_collection.count_documents({})
    total_videos = await videos_collection.count_documents({})
    total_reviews = await reviews_collection.count_documents({})
    unread_messages = await messages_collection.count_documents({"status": "unread"})
    
    # Get today's bookings
    today = datetime.now().strftime("%Y-%m-%d")
    today_bookings = await bookings_collection.count_documents({"booking_date": today})
    
    # Get upcoming bookings (next 7 days)
    upcoming = []
    for i in range(1, 8):
        date = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        count = await bookings_collection.count_documents({"booking_date": date, "status": "confirmed"})
        upcoming.append({"date": date, "count": count})
    
    return {
        "total_bookings": total_bookings,
        "pending_bookings": pending_bookings,
        "confirmed_bookings": confirmed_bookings,
        "total_images": total_images,
        "total_videos": total_videos,
        "total_reviews": total_reviews,
        "unread_messages": unread_messages,
        "today_bookings": today_bookings,
        "upcoming_bookings": upcoming
    }

async def send_confirmation_email(to_email, client_name, date, time):
    message = MessageSchema(
        subject="Appointment Confirmed 💇‍♀️",
        recipients=[to_email],
        body=f"""
Hi {client_name},

Your appointment has been CONFIRMED 🎉

📅 Date: {date}
⏰ Time: {time}

We look forward to seeing you!

- GlamStudio
""",
        subtype="plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)

# ============ HEALTH CHECK ============

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )