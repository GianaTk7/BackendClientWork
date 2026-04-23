from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, List
from bson import ObjectId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler: GetCoreSchemaHandler):
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
        )

    @classmethod
    def validate(cls, value):
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid ObjectId")
        return ObjectId(value)
# ============ BOOKING MODEL ============
class BookingModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    client_name: str = Field(..., min_length=2, max_length=100)
    client_email: EmailStr
    client_phone: str = Field(..., pattern=r'^\+?1?\d{9,15}$')
    booking_date: str
    booking_time: str
    hairstyle_type: str
    special_requests: Optional[str] = ""
    status: str = Field(default="pending", pattern="^(pending|confirmed|cancelled|rescheduled)$")
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator('booking_date')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Invalid date format. Use YYYY-MM-DD')


# ============ GALLERY IMAGE ============
class GalleryImageModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., max_length=500)
    image_url: str
    category: str = Field(..., pattern="^(braids|wig|relax|wash|other)$")
    upload_date: datetime = Field(default_factory=datetime.now)
    ratings: List[int] = []
    average_rating: float = 0.0


# ============ VIDEO MODEL ============
class VideoModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., max_length=500)
    video_url: str
    thumbnail_url: Optional[str] = ""
    category: str = Field(..., pattern="^(tutorial|style|care|other)$")
    upload_date: datetime = Field(default_factory=datetime.now)
    views: int = 0


# ============ REVIEW MODEL ============
class ReviewModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    image_id: str
    client_name: str = Field(..., min_length=2, max_length=100)
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=3, max_length=500)
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator('image_id')
    def validate_image_id(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError('Invalid image_id format')
        return v


# ============ USER MODEL ============
class UserModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    username: str = Field(..., min_length=3, max_length=50)
    password_hash: str
    role: str = Field(default="admin", pattern="^(admin|staff)$")
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None


# ============ MESSAGE MODEL ============
class MessageModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    booking_id: str
    message: str = Field(..., min_length=1, max_length=1000)
    response: Optional[str] = ""
    status: str = Field(default="unread", pattern="^(unread|read|responded)$")
    created_at: datetime = Field(default_factory=datetime.now)
    responded_at: Optional[datetime] = None

    @field_validator('booking_id')
    def validate_booking_id(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError('Invalid booking_id format')
        return v


# ============ SIMPLE MODELS ============
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class BookingResponse(BaseModel):
    id: str
    client_name: str
    client_email: str
    client_phone: str
    booking_date: str
    booking_time: str
    hairstyle_type: str
    special_requests: Optional[str]
    status: str
    created_at: datetime


class DailyStatsModel(BaseModel):
    date: str
    total_bookings: int
    confirmed: int
    pending: int
    cancelled: int
    rescheduled: int


class ServiceModel(BaseModel):
    category: str
    services: List[str]
    description: str
    estimated_time: str


class ServiceListModel(BaseModel):
    braid_styles: List[str] = ["Box Braids", "Cornrows", "Goddess Braids"]
    wig_installation: List[str] = ["Lace Front", "Full Lace"]
    hair_wash: List[str] = ["Deep Conditioning", "Scalp Treatment"]
    relax_hair: List[str] = ["Virgin Relaxer", "Retouch"]


class AvailableSlotModel(BaseModel):
    date: str
    available_slots: List[str]
    booked_slots: List[str]


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|confirmed|cancelled|rescheduled)$")
    reason: Optional[str] = ""