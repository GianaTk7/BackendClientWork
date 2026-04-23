#!/usr/bin/env python3
"""
Image Upload Script for MongoDB
Run this script to upload all images from the 'imgs' folder to MongoDB
"""

import os
import sys
import asyncio
import base64
from pathlib import Path
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "salon_db")

print("Using DB:", MONGODB_URL)  # 👈 keep this for debugging
async def upload_images_to_mongodb():
    """Upload all images from imgs folder to MongoDB"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    images_collection = db["gallery_images"]
    
    # Path to images folder
    images_folder = Path(__file__).parent.parent / "imgs"
    
    if not images_folder.exists():
        print(f"Images folder not found: {images_folder}")
        print("Creating images folder...")
        images_folder.mkdir(parents=True, exist_ok=True)
        print(f"Created folder: {images_folder}")
        print("Please add your images to this folder and run the script again.")
        return
    
    # Get all image files
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(images_folder.glob(f"*{ext}"))
        image_files.extend(images_folder.glob(f"*{ext.upper()}"))
    
    if not image_files:
        print(f"No image files found in {images_folder}")
        print(f"Supported formats: {', '.join(image_extensions)}")
        return
    
    print(f"Found {len(image_files)} images to upload")
    print("-" * 60)
    
    uploaded_count = 0
    failed_count = 0
    skipped_count = 0
    
    for idx, image_path in enumerate(image_files, 1):
        try:
            # Check if image already exists (by filename)
            existing = await images_collection.find_one({"filename": image_path.name})
            if existing:
                print(f"[{idx}/{len(image_files)}] Skipping {image_path.name} (already exists)")
                skipped_count += 1
                continue
            
            # Read image file
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Convert to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Get file extension and map to your exact image paths
            file_ext = image_path.suffix.lower()
            
            # Use YOUR exact image names as you specified
            image_path_mapping = {
                '.jpg': 'imgs/image.png',
                '.jpeg': 'imgs/newstyle.jpeg',
                '.png': 'imgs/Untitled-1.jpg',
                '.gif': 'imgs/Untitled.jpg',
            }
            
            # Get the mapped path or use the original filename
            stored_image_path = image_path_mapping.get(file_ext, f'imgs/{image_path.name}')
            
            # Get MIME type
            mime_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
            }.get(file_ext, 'image/jpeg')
            
            # Create image document - using YOUR original image names
            image_doc = {
                "title": image_path.stem.replace('_', ' ').replace('-', ' ').title(),
                "description": f"Beautiful {image_path.stem} style at Esther's Salon",
                "image_data": image_base64,
                "image_url": f"data:{mime_type};base64,{image_base64}",
                "category": "other",
                "filename": image_path.name,  # Keep original filename
                "original_path": stored_image_path,  # Store your custom path
                "filesize": len(image_data),
                "upload_date": datetime.now(),
                "ratings": [],
                "average_rating": 0,
                "views": 0
            }
            
            # Insert into MongoDB
            result = await images_collection.insert_one(image_doc)
            
            print(f"[{idx}/{len(image_files)}] Uploaded: {image_path.name}")
            print(f"  Title: {image_doc['title']}")
            print(f"  Stored as: {stored_image_path}")
            print(f"  Size: {len(image_data) / 1024:.2f} KB")
            print(f"  ID: {result.inserted_id}")
            print("-" * 60)
            uploaded_count += 1
            
        except Exception as e:
            print(f"[{idx}/{len(image_files)}] Failed to upload {image_path.name}: {str(e)}")
            print("-" * 60)
            failed_count += 1
    
    # Print summary
    print("\n" + "=" * 60)
    print("UPLOAD SUMMARY")
    print("=" * 60)
    print(f"Successfully uploaded: {uploaded_count}")
    print(f"Skipped (already exist): {skipped_count}")
    print(f"Failed: {failed_count}")
    print(f"Total images in folder: {len(image_files)}")
    print("=" * 60)
    
    # List all images in database
    total_in_db = await images_collection.count_documents({})
    print(f"\nTotal images in database: {total_in_db}")
    
    # Close connection
    client.close()

async def clear_all_images():
    """Clear all images from database"""
    confirm = input("This will delete ALL images from the database. Are you sure? (yes/no): ")
    if confirm.lower() == 'yes':
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client[DATABASE_NAME]
        images_collection = db["gallery_images"]
        result = await images_collection.delete_many({})
        print(f"Deleted {result.deleted_count} images from database")
        client.close()
    else:
        print("Operation cancelled")

async def list_images():
    """List all images in database"""
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    images_collection = db["gallery_images"]
    
    images = await images_collection.find().to_list(length=100)
    
    if not images:
        print("No images found in database")
        return
    
    print(f"\nImages in Database ({len(images)}):")
    print("=" * 80)
    for idx, img in enumerate(images, 1):
        print(f"{idx}. {img.get('title', 'Untitled')}")
        print(f"  ID: {img['_id']}")
        print(f"  File: {img.get('filename', 'N/A')}")
        print(f"  Original Path: {img.get('original_path', 'N/A')}")
        print(f"  Category: {img.get('category', 'N/A')}")
        print(f"  Rating: {img.get('average_rating', 0)}/5")
        print(f"  Size: {img.get('filesize', 0) / 1024:.2f} KB")
        print("-" * 80)
    
    client.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "upload":
            asyncio.run(upload_images_to_mongodb())
        elif command == "clear":
            asyncio.run(clear_all_images())
        elif command == "list":
            asyncio.run(list_images())
        else:
            print("Usage: python upload_images.py [upload|clear|list]")
            print("  upload - Upload images from imgs folder to MongoDB")
            print("  clear  - Delete all images from database")
            print("  list   - List all images in database")
    else:
        # Default: upload images
        asyncio.run(upload_images_to_mongodb())