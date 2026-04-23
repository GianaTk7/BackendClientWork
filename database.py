from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGODB_URI)
db = client.salon_db

# Collections
bookings_collection = db.get_collection("bookings")
images_collection = db.get_collection("gallery_images")
videos_collection = db.get_collection("gallery_videos")
reviews_collection = db.get_collection("reviews")
users_collection = db.get_collection("users")
messages_collection = db.get_collection("messages")

# Create indexes for better performance
async def create_indexes():
    # Bookings indexes
    await bookings_collection.create_index("booking_date")
    await bookings_collection.create_index("booking_time")
    await bookings_collection.create_index("status")
    await bookings_collection.create_index([("booking_date", 1), ("booking_time", 1)])
    
    # Images indexes
    await images_collection.create_index("category")
    await images_collection.create_index("upload_date")
    
    # Reviews indexes
    await reviews_collection.create_index("image_id")
    await reviews_collection.create_index("created_at")
    
    # Messages indexes
    await messages_collection.create_index("booking_id")
    await messages_collection.create_index("status")
    
    print("Database indexes created successfully")