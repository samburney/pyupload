import asyncio
import os
import shutil
import time
from datetime import datetime
from tortoise import Tortoise, run_async
from app.models.legacy import Upload, User, Image
from PIL import Image as PilImage, ImageDraw

# Configuration
FILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "files")
DB_URL = f"mysql://{os.getenv('DB_USER', 'simplegallery')}:{os.getenv('DB_PASSWORD', 'simplegallery')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME', 'simplegallery')}"

async def init_db():
    await Tortoise.init(
        db_url=DB_URL,
        modules={'models': ['app.models.legacy']}
    )
    # Note: We don't generate schemas here as we are mapping to an EXISTING schema
    # But for a fresh dev env, we might need it if the DB is empty.
    # await Tortoise.generate_schemas()

async def create_dummy_file(filename, color="blue"):
    if not os.path.exists(FILES_DIR):
        os.makedirs(FILES_DIR)
        
    filepath = os.path.join(FILES_DIR, filename)
    img = PilImage.new('RGB', (800, 600), color=color)
    d = ImageDraw.Draw(img)
    d.text((10,10), filename, fill=(255,255,0))
    img.save(filepath)
    print(f"Created file: {filepath}")
    return os.path.getsize(filepath)

async def seed():
    print("Seeding database and filesystem...")
    
    now = datetime.now()
    
    # Create User
    user, created = await User.get_or_create(
        username="dev_user",
        defaults={
            "email": "dev@example.com",
            "password": "hashed_password_placeholder",
            "remember_token": "dev_token",
            "created_at": now,
            "updated_at": now
        }
    )
    
    # Create Uploads
    uploads_data = [
        {"name": "test_image_1", "ext": "jpg", "color": "red"},
        {"name": "test_image_2", "ext": "jpg", "color": "green"},
        {"name": "test_image_3", "ext": "png", "color": "blue"},
    ]
    
    for item in uploads_data:
        filename = f"{item['name']}.{item['ext']}"
        size = await create_dummy_file(filename, item['color'])
        
        upload = await Upload.create(
            user_id=user.id,
            filegroup_id=0,
            description=f"Test upload {item['name']}",
            name=item['name'],
            cleanname=item['name'],
            originalname=filename,
            ext=item['ext'],
            size=size,
            type=f"image/{item['ext']}",
            extra="image",
            created_at=now,
            updated_at=now,
            viewed=0,
            private=0
        )
        
        await Image.create(
            upload_id=upload.id,
            type=item['ext'],
            width=800,
            height=600,
            bits=8,
            channels=3,
            created_at=now,
            updated_at=now
        )
        
    print("Seeding complete.")

if __name__ == "__main__":
    run_async(init_db())
    run_async(seed())
