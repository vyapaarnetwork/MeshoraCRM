from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import shutil
import aiofiles
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client as TwilioClient
from enum import Enum
import csv
import io
import re

ROOT_DIR = Path(__file__).parent
UPLOAD_DIR = ROOT_DIR / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    raise ValueError("JWT_SECRET environment variable is required")
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# SendGrid Configuration
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@vyapaarnetwork.com')

# Twilio SMS Configuration
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')

# Create the main app
app = FastAPI(title="Vyapaar Network CRM API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== ENUMS ====================
class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    SELLING_PARTNER = "selling_partner"
    SALES_ASSOCIATE = "sales_associate"
    CUSTOMER = "customer"

# ==================== MODELS ====================

# User Models
class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole
    company_id: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole
    company_name: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Profile Update Models
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

# Bulk Import Models
class BulkImportResult(BaseModel):
    total_rows: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]]

# Enhanced Commission Model for locked deals
class LockedCommission(BaseModel):
    deal_value: float
    vyapaar_base_percentage: float
    commission_override_percentage: Optional[float] = None
    final_vyapaar_percentage: float
    selling_partner_revenue: float
    vyapaar_gross_commission: float
    sales_associate_percentage: Optional[float] = None
    sales_associate_commission: Optional[float] = None
    vyapaar_net_earnings: float
    locked_at: str
    locked_by: str

# Company Model
class CompanyCreate(BaseModel):
    name: str
    type: str  # selling_partner, customer
    vyapaar_commission_percentage: Optional[float] = 15.0
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    subcategory_ids: Optional[List[str]] = None  # For selling partners
    # Default user for customer companies
    default_user_name: Optional[str] = None
    default_user_email: Optional[EmailStr] = None
    default_user_phone: Optional[str] = None
    default_user_password: Optional[str] = None

class CompanyResponse(BaseModel):
    id: str
    name: str
    type: str
    vyapaar_commission_percentage: float
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    subcategory_ids: Optional[List[str]] = None
    subcategories: Optional[List[Dict[str, str]]] = None
    created_at: str
    is_active: bool

# Admin User Creation Model
class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole
    company_id: Optional[str] = None  # For existing company
    company_name: Optional[str] = None  # For new company
    phone: Optional[str] = None

# Admin User Update Model
class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None  # Optional - only update if provided
    role: Optional[UserRole] = None
    company_id: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

# Lead Referral Model (for Selling Partners)
class LeadReferralCreate(BaseModel):
    title: str
    description: Optional[str] = None
    customer_name: str
    customer_email: EmailStr
    customer_phone: Optional[str] = None
    customer_company: Optional[str] = None
    primary_category_id: str
    secondary_category_id: Optional[str] = None
    estimated_deal_value: Optional[float] = None
    referral_notes: Optional[str] = None
    is_internal_request: bool = False  # For Selling Partners requesting services

# Notification Models
class NotificationType(str, Enum):
    NEW_LEAD = "new_lead"
    LEAD_ASSIGNED = "lead_assigned"
    LEAD_UPDATED = "lead_updated"
    LEAD_STATUS_CHANGE = "lead_status_change"
    NEW_REFERRAL = "new_referral"
    FOLLOW_UP_REMINDER = "follow_up_reminder"

class NotificationCreate(BaseModel):
    type: NotificationType
    title: str
    message: str
    lead_id: Optional[str] = None
    user_id: str  # Recipient
    data: Optional[Dict[str, Any]] = None

class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    lead_id: Optional[str] = None
    is_read: bool
    created_at: str
    data: Optional[Dict[str, Any]] = None

# Document Models
class DocumentTag(str, Enum):
    PROPOSAL = "proposal"
    CONTRACT = "contract"
    INVOICE = "invoice"
    QUOTATION = "quotation"
    CORPORATE_PROFILE = "corporate_profile"
    PRODUCT_CATALOG = "product_catalog"
    BROCHURE = "brochure"
    CERTIFICATE = "certificate"
    OTHER = "other"

class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_size: int
    content_type: str
    tag: str
    description: Optional[str] = None
    uploaded_by: str
    uploaded_by_name: Optional[str] = None
    uploaded_at: str

# Master Data Models
class LeadStatusCreate(BaseModel):
    name: str
    color: str = "#4169E1"
    order: int = 0

class LeadStatusResponse(BaseModel):
    id: str
    name: str
    color: str
    order: int
    is_active: bool

class PrimaryCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None

class PrimaryCategoryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_active: bool

class SecondaryCategoryCreate(BaseModel):
    name: str
    primary_category_id: str
    description: Optional[str] = None

class SecondaryCategoryResponse(BaseModel):
    id: str
    name: str
    primary_category_id: str
    primary_category_name: Optional[str] = None
    description: Optional[str] = None
    is_active: bool

class CommissionTemplateCreate(BaseModel):
    name: str
    vyapaar_percentage: float
    description: Optional[str] = None

class CommissionTemplateResponse(BaseModel):
    id: str
    name: str
    vyapaar_percentage: float
    description: Optional[str] = None
    is_active: bool

# Lead Models
class FollowUpCreate(BaseModel):
    scheduled_date: str
    notes: Optional[str] = None
    pending_with: Optional[str] = None  # "selling_partner" or "customer"

class FollowUpResponse(BaseModel):
    id: str
    scheduled_date: str
    notes: Optional[str] = None
    pending_with: Optional[str] = None
    is_completed: bool
    completed_at: Optional[str] = None
    completion_notes: Optional[str] = None
    created_at: str

class CommentCreate(BaseModel):
    content: str

class CommentResponse(BaseModel):
    id: str
    content: str
    user_id: str
    user_name: str
    user_role: str
    created_at: str

class LeadCreate(BaseModel):
    title: str
    description: Optional[str] = None
    customer_name: str
    customer_email: EmailStr
    customer_phone: Optional[str] = None
    customer_company: Optional[str] = None
    selling_partner_id: Optional[str] = None
    sales_associate_id: Optional[str] = None
    primary_category_id: str
    secondary_category_id: Optional[str] = None
    deal_value: float = 0.0
    commission_override: Optional[float] = None
    sales_associate_commission: Optional[float] = None
    status_id: Optional[str] = None

class LeadUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    customer_company: Optional[str] = None
    selling_partner_id: Optional[str] = None
    sales_associate_id: Optional[str] = None
    primary_category_id: Optional[str] = None
    secondary_category_id: Optional[str] = None
    deal_value: Optional[float] = None
    commission_override: Optional[float] = None
    sales_associate_commission: Optional[float] = None
    status_id: Optional[str] = None

class CommissionBreakdown(BaseModel):
    total_deal_value: float
    vyapaar_percentage: float
    vyapaar_share: float
    selling_partner_share: float
    sales_associate_percentage: Optional[float] = None
    sales_associate_share: Optional[float] = None

# Partner Assignment History for leads
class PartnerAssignment(BaseModel):
    partner_id: str
    partner_name: Optional[str] = None
    assigned_at: str
    assigned_by: str
    assigned_by_name: Optional[str] = None
    status: str = "active"  # active, won, lost
    won_at: Optional[str] = None
    lost_at: Optional[str] = None
    notes: Optional[str] = None

# Model for assigning additional partner
class AssignPartnerRequest(BaseModel):
    partner_id: str
    notes: Optional[str] = None

# Model for marking partner as winner
class MarkPartnerWonRequest(BaseModel):
    partner_id: str
    notes: Optional[str] = None

class LeadResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None
    customer_company: Optional[str] = None
    selling_partner_id: Optional[str] = None  # The winning partner (for backward compatibility)
    selling_partner_name: Optional[str] = None
    sales_associate_id: Optional[str] = None
    sales_associate_name: Optional[str] = None
    referred_by_partner_id: Optional[str] = None
    referred_by_partner_name: Optional[str] = None
    referred_by_associate_id: Optional[str] = None
    referred_by_associate_name: Optional[str] = None
    is_internal_request: bool = False
    primary_category_id: str
    primary_category_name: Optional[str] = None
    secondary_category_id: Optional[str] = None
    secondary_category_name: Optional[str] = None
    deal_value: float
    commission_override: Optional[float] = None
    sales_associate_commission: Optional[float] = None
    commission_breakdown: Optional[CommissionBreakdown] = None
    status_id: Optional[str] = None
    status_name: Optional[str] = None
    status_color: Optional[str] = None
    follow_ups: List[FollowUpResponse] = []
    comments: List[CommentResponse] = []
    documents: List[DocumentResponse] = []
    assigned_partners: List[PartnerAssignment] = []  # All assigned partners (active, won, lost)
    active_partners_count: int = 0  # Count of currently active partners
    created_by: str
    created_by_name: Optional[str] = None
    created_at: str
    updated_at: str

# Customer User Management Models
class CustomerUserCreate(BaseModel):
    email: EmailStr
    name: str
    phone: Optional[str] = None
    password: str

class CustomerUserResponse(BaseModel):
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    role: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    is_active: bool
    created_at: str

# Report Models
class ReportFilter(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    selling_partner_id: Optional[str] = None
    sales_associate_id: Optional[str] = None
    status_id: Optional[str] = None
    primary_category_id: Optional[str] = None

class DashboardStats(BaseModel):
    total_leads: int
    won_deals: int
    lost_deals: int
    total_revenue: float
    total_commission: float
    conversion_rate: float
    leads_by_status: List[Dict[str, Any]]
    leads_by_category: List[Dict[str, Any]]
    revenue_trend: List[Dict[str, Any]]

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    user = await db.users.find_one({"id": payload['user_id']}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def calculate_commission(deal_value: float, vyapaar_percentage: float, sales_associate_percentage: Optional[float] = None) -> CommissionBreakdown:
    vyapaar_share = deal_value * (vyapaar_percentage / 100)
    selling_partner_share = deal_value - vyapaar_share
    
    sa_share = None
    if sales_associate_percentage:
        sa_share = vyapaar_share * (sales_associate_percentage / 100)
        vyapaar_share = vyapaar_share - sa_share
    
    return CommissionBreakdown(
        total_deal_value=deal_value,
        vyapaar_percentage=vyapaar_percentage,
        vyapaar_share=round(vyapaar_share, 2),
        selling_partner_share=round(selling_partner_share, 2),
        sales_associate_percentage=sales_associate_percentage,
        sales_associate_share=round(sa_share, 2) if sa_share else None
    )

async def send_followup_reminder(to_email: str, lead_title: str, followup_date: str, user_name: str):
    if not SENDGRID_API_KEY:
        logger.warning("SendGrid API key not configured, skipping email")
        return
    
    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=to_email,
        subject=f"Follow-up Reminder: {lead_title}",
        html_content=f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Follow-up Reminder</h2>
                <p>Hi {user_name},</p>
                <p>This is a reminder for your upcoming follow-up:</p>
                <div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>Lead:</strong> {lead_title}</p>
                    <p><strong>Scheduled Date:</strong> {followup_date}</p>
                </div>
                <p>Please ensure to complete this follow-up on time.</p>
                <p>Best regards,<br>Vyapaar Network CRM</p>
            </body>
        </html>
        """
    )
    
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        logger.info(f"Follow-up reminder sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    # Only allow customer self-registration; other roles must be created by admin
    if user_data.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, 
            detail="Only customers can self-register. Please contact admin for other account types."
        )
    
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    company_id = None
    company_name = None
    
    # Create company for customer if provided
    if user_data.company_name:
        company_id = str(uuid.uuid4())
        company_doc = {
            "id": company_id,
            "name": user_data.company_name,
            "type": "customer",
            "vyapaar_commission_percentage": 15.0,
            "address": None,
            "contact_email": user_data.email,
            "contact_phone": user_data.phone,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True
        }
        await db.companies.insert_one(company_doc)
        company_name = user_data.company_name
    
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "role": user_data.role.value,
        "company_id": company_id,
        "phone": user_data.phone,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    token = create_token(user_id, user_data.email, user_data.role.value)
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user_data.email,
            name=user_data.name,
            role=user_data.role,
            company_id=company_id,
            company_name=company_name,
            phone=user_data.phone,
            is_active=True,
            created_at=user_doc['created_at']
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.get('is_active', True):
        raise HTTPException(status_code=401, detail="Account is deactivated")
    
    company_name = None
    if user.get('company_id'):
        company = await db.companies.find_one({"id": user['company_id']}, {"_id": 0})
        if company:
            company_name = company['name']
    
    token = create_token(user['id'], user['email'], user['role'])
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            role=UserRole(user['role']),
            company_id=user.get('company_id'),
            company_name=company_name,
            phone=user.get('phone'),
            is_active=user.get('is_active', True),
            created_at=user['created_at']
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    company_name = None
    if current_user.get('company_id'):
        company = await db.companies.find_one({"id": current_user['company_id']}, {"_id": 0})
        if company:
            company_name = company['name']
    
    return UserResponse(
        id=current_user['id'],
        email=current_user['email'],
        name=current_user['name'],
        role=UserRole(current_user['role']),
        company_id=current_user.get('company_id'),
        company_name=company_name,
        phone=current_user.get('phone'),
        is_active=current_user.get('is_active', True),
        created_at=current_user['created_at']
    )

# ==================== PROFILE ROUTES ====================

@api_router.put("/profile", response_model=UserResponse)
async def update_profile(profile_data: ProfileUpdate, current_user: dict = Depends(get_current_user)):
    """Update user profile (name, phone)"""
    update_data = profile_data.model_dump(exclude_unset=True, exclude_none=True)
    
    if update_data:
        await db.users.update_one({"id": current_user['id']}, {"$set": update_data})
    
    updated_user = await db.users.find_one({"id": current_user['id']}, {"_id": 0, "password": 0})
    
    company_name = None
    if updated_user.get('company_id'):
        company = await db.companies.find_one({"id": updated_user['company_id']}, {"_id": 0})
        if company:
            company_name = company['name']
    
    return UserResponse(
        id=updated_user['id'],
        email=updated_user['email'],
        name=updated_user['name'],
        role=UserRole(updated_user['role']),
        company_id=updated_user.get('company_id'),
        company_name=company_name,
        phone=updated_user.get('phone'),
        is_active=updated_user.get('is_active', True),
        created_at=updated_user['created_at']
    )

@api_router.post("/profile/change-password")
async def change_password(password_data: PasswordChange, current_user: dict = Depends(get_current_user)):
    """Change user password"""
    # Get user with password
    user = await db.users.find_one({"id": current_user['id']}, {"_id": 0})
    
    # Verify current password
    if not verify_password(password_data.current_password, user['password']):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Validate new password
    if len(password_data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    # Update password
    new_hash = hash_password(password_data.new_password)
    await db.users.update_one({"id": current_user['id']}, {"$set": {"password": new_hash}})
    
    return {"message": "Password changed successfully"}

# ==================== NOTIFICATION HELPERS ====================

async def create_notification(user_id: str, notification_type: str, title: str, message: str, lead_id: str = None, data: dict = None):
    """Create a notification for a specific user"""
    notification_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    notification_doc = {
        "id": notification_id,
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "lead_id": lead_id,
        "data": data or {},
        "is_read": False,
        "created_at": now
    }
    
    await db.notifications.insert_one(notification_doc)
    return notification_doc

async def create_notification_for_admins(notification_type: str, title: str, message: str, lead_id: str = None, data: dict = None):
    """Create notifications for all super admins"""
    admins = await db.users.find({"role": "super_admin", "is_active": True}, {"_id": 0}).to_list(100)
    for admin in admins:
        await create_notification(admin['id'], notification_type, title, message, lead_id, data)

async def create_notification_for_user(user_id: str, notification_type: str, title: str, message: str, lead_id: str = None, data: dict = None):
    """Create a notification for a specific user"""
    await create_notification(user_id, notification_type, title, message, lead_id, data)

# ==================== SMS HELPERS ====================

def send_sms(to_phone: str, message: str) -> bool:
    """Send SMS using Twilio"""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
        logger.warning("Twilio credentials not configured, skipping SMS")
        return False
    
    if not to_phone:
        logger.warning("No phone number provided, skipping SMS")
        return False
    
    try:
        # Ensure phone number is in E.164 format
        phone = to_phone.strip()
        if not phone.startswith('+'):
            # Assume Indian number if no country code
            phone = '+91' + phone.replace(' ', '').replace('-', '')
        
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        sms = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=phone
        )
        logger.info(f"SMS sent successfully to {phone}: {sms.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS to {to_phone}: {str(e)}")
        return False

async def send_lead_assignment_sms(partner_id: str, lead_title: str, customer_name: str):
    """Send SMS notification when a lead is assigned to a partner"""
    partner = await db.users.find_one({"id": partner_id}, {"_id": 0})
    if partner and partner.get('phone'):
        message = f"Vyapaar Network: New lead assigned to you!\n\nLead: {lead_title}\nCustomer: {customer_name}\n\nLogin to view details."
        send_sms(partner['phone'], message)

async def send_lead_assignment_sms_to_admins(lead_title: str, partner_name: str, customer_name: str):
    """Send SMS notification to all admins when a lead is assigned"""
    admins = await db.users.find({"role": "super_admin", "is_active": True}, {"_id": 0}).to_list(100)
    for admin in admins:
        if admin.get('phone'):
            message = f"Vyapaar Network: Lead assigned!\n\nLead: {lead_title}\nAssigned to: {partner_name}\nCustomer: {customer_name}"
            send_sms(admin['phone'], message)

# ==================== NOTIFICATION ROUTES ====================

@api_router.get("/notifications", response_model=List[NotificationResponse])
async def get_notifications(unread_only: bool = False, limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get notifications for the current user"""
    query = {"user_id": current_user['id']}
    if unread_only:
        query["is_read"] = False
    
    notifications = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return [NotificationResponse(**n) for n in notifications]

@api_router.get("/notifications/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get count of unread notifications"""
    count = await db.notifications.count_documents({"user_id": current_user['id'], "is_read": False})
    return {"count": count}

@api_router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a notification as read"""
    result = await db.notifications.update_one(
        {"id": notification_id, "user_id": current_user['id']},
        {"$set": {"is_read": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}

@api_router.put("/notifications/mark-all-read")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read for current user"""
    await db.notifications.update_many(
        {"user_id": current_user['id'], "is_read": False},
        {"$set": {"is_read": True}}
    )
    return {"message": "All notifications marked as read"}

# ==================== USER ROUTES ====================

@api_router.post("/users", response_model=UserResponse)
async def create_user(user_data: AdminUserCreate, current_user: dict = Depends(get_current_user)):
    """Admin creates a new user of any type"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can create users")
    
    # Check if email exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    company_id = user_data.company_id
    company_name = None
    
    # Handle company assignment for all applicable roles
    if user_data.role in [UserRole.SELLING_PARTNER, UserRole.CUSTOMER, UserRole.SALES_ASSOCIATE]:
        if user_data.company_id:
            # Use existing company
            company = await db.companies.find_one({"id": user_data.company_id}, {"_id": 0})
            if company:
                company_name = company['name']
        elif user_data.company_name and user_data.role != UserRole.SALES_ASSOCIATE:
            # Create new company (only for selling partners and customers)
            company_id = str(uuid.uuid4())
            company_doc = {
                "id": company_id,
                "name": user_data.company_name,
                "type": "selling_partner" if user_data.role == UserRole.SELLING_PARTNER else "customer",
                "vyapaar_commission_percentage": 15.0,
                "address": None,
                "contact_email": user_data.email,
                "contact_phone": user_data.phone,
                "subcategory_ids": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_active": True
            }
            await db.companies.insert_one(company_doc)
            company_name = user_data.company_name
    
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "role": user_data.role.value,
        "company_id": company_id,
        "phone": user_data.phone,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    return UserResponse(
        id=user_id,
        email=user_data.email,
        name=user_data.name,
        role=user_data.role,
        company_id=company_id,
        company_name=company_name,
        phone=user_data.phone,
        is_active=True,
        created_at=user_doc['created_at']
    )

# NOTE: These specific routes must be defined BEFORE /users/{user_id} to avoid route conflicts
@api_router.get("/users/selling-partners", response_model=List[UserResponse])
async def list_selling_partners(current_user: dict = Depends(get_current_user)):
    users = await db.users.find({"role": UserRole.SELLING_PARTNER.value}, {"_id": 0, "password": 0}).to_list(1000)
    
    result = []
    for user in users:
        company_name = None
        if user.get('company_id'):
            company = await db.companies.find_one({"id": user['company_id']}, {"_id": 0})
            if company:
                company_name = company['name']
        
        result.append(UserResponse(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            role=UserRole(user['role']),
            company_id=user.get('company_id'),
            company_name=company_name,
            phone=user.get('phone'),
            is_active=user.get('is_active', True),
            created_at=user['created_at']
        ))
    
    return result

@api_router.get("/users/sales-associates", response_model=List[UserResponse])
async def list_sales_associates(current_user: dict = Depends(get_current_user)):
    users = await db.users.find({"role": UserRole.SALES_ASSOCIATE.value}, {"_id": 0, "password": 0}).to_list(1000)
    
    result = []
    for user in users:
        result.append(UserResponse(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            role=UserRole(user['role']),
            company_id=user.get('company_id'),
            company_name=None,
            phone=user.get('phone'),
            is_active=user.get('is_active', True),
            created_at=user['created_at']
        ))
    
    return result

@api_router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get single user details"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can view user details")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    company_name = None
    if user.get('company_id'):
        company = await db.companies.find_one({"id": user['company_id']}, {"_id": 0})
        if company:
            company_name = company['name']
    
    return UserResponse(
        id=user['id'],
        email=user['email'],
        name=user['name'],
        role=UserRole(user['role']),
        company_id=user.get('company_id'),
        company_name=company_name,
        phone=user.get('phone'),
        is_active=user.get('is_active', True),
        created_at=user['created_at']
    )

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user_data: AdminUserUpdate, current_user: dict = Depends(get_current_user)):
    """Admin updates a user"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can update users")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent editing the logged-in super admin's role
    if user_id == current_user['id'] and user_data.role and user_data.role.value != current_user['role']:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    
    # Check email uniqueness if changing
    if user_data.email and user_data.email != user['email']:
        existing = await db.users.find_one({"email": user_data.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
    
    update_data = user_data.model_dump(exclude_unset=True, exclude_none=True)
    
    # Handle password hashing
    if 'password' in update_data and update_data['password']:
        update_data['password'] = hash_password(update_data['password'])
    elif 'password' in update_data:
        del update_data['password']
    
    # Handle role conversion
    if 'role' in update_data:
        update_data['role'] = update_data['role'].value
    
    if update_data:
        await db.users.update_one({"id": user_id}, {"$set": update_data})
    
    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    
    company_name = None
    if updated_user.get('company_id'):
        company = await db.companies.find_one({"id": updated_user['company_id']}, {"_id": 0})
        if company:
            company_name = company['name']
    
    return UserResponse(
        id=updated_user['id'],
        email=updated_user['email'],
        name=updated_user['name'],
        role=UserRole(updated_user['role']),
        company_id=updated_user.get('company_id'),
        company_name=company_name,
        phone=updated_user.get('phone'),
        is_active=updated_user.get('is_active', True),
        created_at=updated_user['created_at']
    )

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Admin deletes a user"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can delete users")
    
    # Prevent self-deletion
    if user_id == current_user['id']:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Soft delete - set is_active to False
    await db.users.update_one({"id": user_id}, {"$set": {"is_active": False}})
    
    return {"message": "User deleted successfully"}

@api_router.get("/users", response_model=List[UserResponse])
async def list_users(role: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can list all users")
    
    query = {}
    if role:
        query['role'] = role
    
    users = await db.users.find(query, {"_id": 0, "password": 0}).to_list(1000)
    
    result = []
    for user in users:
        company_name = None
        if user.get('company_id'):
            company = await db.companies.find_one({"id": user['company_id']}, {"_id": 0})
            if company:
                company_name = company['name']
        
        result.append(UserResponse(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            role=UserRole(user['role']),
            company_id=user.get('company_id'),
            company_name=company_name,
            phone=user.get('phone'),
            is_active=user.get('is_active', True),
            created_at=user['created_at']
        ))
    
    return result

# ==================== CUSTOMER USER MANAGEMENT ====================

@api_router.get("/customers/company-users", response_model=List[CustomerUserResponse])
async def list_company_users(current_user: dict = Depends(get_current_user)):
    """Customer lists users from their company"""
    if current_user['role'] != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Only customers can access this endpoint")
    
    if not current_user.get('company_id'):
        raise HTTPException(status_code=400, detail="You are not associated with a company")
    
    users = await db.users.find(
        {"company_id": current_user['company_id'], "role": UserRole.CUSTOMER.value},
        {"_id": 0, "password": 0}
    ).to_list(100)
    
    company = await db.companies.find_one({"id": current_user['company_id']}, {"_id": 0})
    company_name = company['name'] if company else None
    
    result = []
    for user in users:
        result.append(CustomerUserResponse(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            phone=user.get('phone'),
            role=user['role'],
            company_id=user.get('company_id'),
            company_name=company_name,
            is_active=user.get('is_active', True),
            created_at=user['created_at']
        ))
    
    return result

@api_router.post("/customers/company-users", response_model=CustomerUserResponse)
async def create_company_user(user_data: CustomerUserCreate, current_user: dict = Depends(get_current_user)):
    """Customer creates a new user for their company"""
    if current_user['role'] != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Only customers can create company users")
    
    if not current_user.get('company_id'):
        raise HTTPException(status_code=400, detail="You are not associated with a company")
    
    # Check if email exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "role": UserRole.CUSTOMER.value,
        "company_id": current_user['company_id'],
        "phone": user_data.phone,
        "is_active": True,
        "created_by": current_user['id'],
        "created_at": now
    }
    
    await db.users.insert_one(user_doc)
    
    company = await db.companies.find_one({"id": current_user['company_id']}, {"_id": 0})
    company_name = company['name'] if company else None
    
    return CustomerUserResponse(
        id=user_id,
        email=user_data.email,
        name=user_data.name,
        phone=user_data.phone,
        role=UserRole.CUSTOMER.value,
        company_id=current_user['company_id'],
        company_name=company_name,
        is_active=True,
        created_at=now
    )

@api_router.put("/customers/company-users/{user_id}", response_model=CustomerUserResponse)
async def update_company_user(user_id: str, user_data: CustomerUserCreate, current_user: dict = Depends(get_current_user)):
    """Customer updates a user from their company"""
    if current_user['role'] != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Only customers can update company users")
    
    if not current_user.get('company_id'):
        raise HTTPException(status_code=400, detail="You are not associated with a company")
    
    user = await db.users.find_one({"id": user_id, "company_id": current_user['company_id']}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found in your company")
    
    # Check email uniqueness if changing
    if user_data.email != user['email']:
        existing = await db.users.find_one({"email": user_data.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
    
    update_data = {
        "email": user_data.email,
        "name": user_data.name,
        "phone": user_data.phone
    }
    
    if user_data.password:
        update_data['password'] = hash_password(user_data.password)
    
    await db.users.update_one({"id": user_id}, {"$set": update_data})
    
    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    company = await db.companies.find_one({"id": current_user['company_id']}, {"_id": 0})
    company_name = company['name'] if company else None
    
    return CustomerUserResponse(
        id=updated_user['id'],
        email=updated_user['email'],
        name=updated_user['name'],
        phone=updated_user.get('phone'),
        role=updated_user['role'],
        company_id=updated_user.get('company_id'),
        company_name=company_name,
        is_active=updated_user.get('is_active', True),
        created_at=updated_user['created_at']
    )

@api_router.delete("/customers/company-users/{user_id}")
async def delete_company_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Customer deactivates a user from their company"""
    if current_user['role'] != UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Only customers can delete company users")
    
    if not current_user.get('company_id'):
        raise HTTPException(status_code=400, detail="You are not associated with a company")
    
    # Prevent self-deletion
    if user_id == current_user['id']:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    user = await db.users.find_one({"id": user_id, "company_id": current_user['company_id']}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found in your company")
    
    await db.users.update_one({"id": user_id}, {"$set": {"is_active": False}})
    
    return {"message": "User deactivated successfully"}

# ==================== COMPANY ROUTES ====================

@api_router.post("/companies", response_model=CompanyResponse)
async def create_company(company_data: CompanyCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can create companies")
    
    company_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    company_doc = {
        "id": company_id,
        "name": company_data.name,
        "type": company_data.type,
        "vyapaar_commission_percentage": company_data.vyapaar_commission_percentage,
        "address": company_data.address,
        "contact_email": company_data.contact_email,
        "contact_phone": company_data.contact_phone,
        "subcategory_ids": company_data.subcategory_ids or [],
        "created_at": now,
        "is_active": True
    }
    
    await db.companies.insert_one(company_doc)
    
    # Create default user for customer companies
    if company_data.type == "customer" and company_data.default_user_email and company_data.default_user_name:
        # Check if email already exists
        existing_user = await db.users.find_one({"email": company_data.default_user_email})
        if existing_user:
            raise HTTPException(status_code=400, detail=f"User email {company_data.default_user_email} already exists")
        
        user_id = str(uuid.uuid4())
        user_doc = {
            "id": user_id,
            "email": company_data.default_user_email,
            "password": hash_password(company_data.default_user_password or "customer123"),
            "name": company_data.default_user_name,
            "role": UserRole.CUSTOMER.value,
            "company_id": company_id,
            "phone": company_data.default_user_phone,
            "is_active": True,
            "created_at": now
        }
        await db.users.insert_one(user_doc)
    
    # Get subcategory names
    subcategories = []
    if company_doc.get('subcategory_ids'):
        for sub_id in company_doc['subcategory_ids']:
            sub = await db.secondary_categories.find_one({"id": sub_id}, {"_id": 0})
            if sub:
                subcategories.append({"id": sub['id'], "name": sub['name']})
    
    return CompanyResponse(
        id=company_doc['id'],
        name=company_doc['name'],
        type=company_doc['type'],
        vyapaar_commission_percentage=company_doc['vyapaar_commission_percentage'],
        address=company_doc.get('address'),
        contact_email=company_doc.get('contact_email'),
        contact_phone=company_doc.get('contact_phone'),
        subcategory_ids=company_doc.get('subcategory_ids'),
        subcategories=subcategories if subcategories else None,
        created_at=company_doc['created_at'],
        is_active=company_doc['is_active']
    )

@api_router.get("/companies", response_model=List[CompanyResponse])
async def list_companies(type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {"is_active": True}
    if type:
        query['type'] = type
    
    companies = await db.companies.find(query, {"_id": 0}).to_list(1000)
    
    result = []
    for c in companies:
        subcategories = []
        if c.get('subcategory_ids'):
            for sub_id in c['subcategory_ids']:
                sub = await db.secondary_categories.find_one({"id": sub_id}, {"_id": 0})
                if sub:
                    subcategories.append({"id": sub['id'], "name": sub['name']})
        
        result.append(CompanyResponse(
            id=c['id'],
            name=c['name'],
            type=c['type'],
            vyapaar_commission_percentage=c.get('vyapaar_commission_percentage', 15.0),
            address=c.get('address'),
            contact_email=c.get('contact_email'),
            contact_phone=c.get('contact_phone'),
            subcategory_ids=c.get('subcategory_ids'),
            subcategories=subcategories if subcategories else None,
            created_at=c['created_at'],
            is_active=c.get('is_active', True)
        ))
    
    return result

@api_router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: str, current_user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    subcategories = []
    if company.get('subcategory_ids'):
        for sub_id in company['subcategory_ids']:
            sub = await db.secondary_categories.find_one({"id": sub_id}, {"_id": 0})
            if sub:
                subcategories.append({"id": sub['id'], "name": sub['name']})
    
    return CompanyResponse(
        id=company['id'],
        name=company['name'],
        type=company['type'],
        vyapaar_commission_percentage=company.get('vyapaar_commission_percentage', 15.0),
        address=company.get('address'),
        contact_email=company.get('contact_email'),
        contact_phone=company.get('contact_phone'),
        subcategory_ids=company.get('subcategory_ids'),
        subcategories=subcategories if subcategories else None,
        created_at=company['created_at'],
        is_active=company.get('is_active', True)
    )

@api_router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: str, company_data: CompanyCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can update companies")
    
    update_data = company_data.model_dump(exclude_unset=True)
    result = await db.companies.update_one({"id": company_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Company not found")
    
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    
    subcategories = []
    if company.get('subcategory_ids'):
        for sub_id in company['subcategory_ids']:
            sub = await db.secondary_categories.find_one({"id": sub_id}, {"_id": 0})
            if sub:
                subcategories.append({"id": sub['id'], "name": sub['name']})
    
    return CompanyResponse(
        id=company['id'],
        name=company['name'],
        type=company['type'],
        vyapaar_commission_percentage=company.get('vyapaar_commission_percentage', 15.0),
        address=company.get('address'),
        contact_email=company.get('contact_email'),
        contact_phone=company.get('contact_phone'),
        subcategory_ids=company.get('subcategory_ids'),
        subcategories=subcategories if subcategories else None,
        created_at=company['created_at'],
        is_active=company.get('is_active', True)
    )

# ==================== MASTER DATA ROUTES ====================

# Lead Status
@api_router.post("/master/lead-status", response_model=LeadStatusResponse)
async def create_lead_status(status_data: LeadStatusCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can create lead status")
    
    status_id = str(uuid.uuid4())
    status_doc = {
        "id": status_id,
        "name": status_data.name,
        "color": status_data.color,
        "order": status_data.order,
        "is_active": True
    }
    
    await db.lead_statuses.insert_one(status_doc)
    return LeadStatusResponse(**{k: v for k, v in status_doc.items() if k != '_id'})

@api_router.get("/master/lead-status", response_model=List[LeadStatusResponse])
async def list_lead_statuses(current_user: dict = Depends(get_current_user)):
    statuses = await db.lead_statuses.find({"is_active": True}, {"_id": 0}).sort("order", 1).to_list(100)
    return [LeadStatusResponse(**s) for s in statuses]

@api_router.put("/master/lead-status/{status_id}", response_model=LeadStatusResponse)
async def update_lead_status(status_id: str, status_data: LeadStatusCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can update lead status")
    
    update_data = status_data.model_dump(exclude_unset=True)
    result = await db.lead_statuses.update_one({"id": status_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead status not found")
    
    status = await db.lead_statuses.find_one({"id": status_id}, {"_id": 0})
    return LeadStatusResponse(**status)

@api_router.delete("/master/lead-status/{status_id}")
async def delete_lead_status(status_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can delete lead status")
    
    result = await db.lead_statuses.update_one({"id": status_id}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead status not found")
    
    return {"message": "Lead status deleted"}

# Primary Category
@api_router.post("/master/primary-categories", response_model=PrimaryCategoryResponse)
async def create_primary_category(category_data: PrimaryCategoryCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can create categories")
    
    category_id = str(uuid.uuid4())
    category_doc = {
        "id": category_id,
        "name": category_data.name,
        "description": category_data.description,
        "is_active": True
    }
    
    await db.primary_categories.insert_one(category_doc)
    return PrimaryCategoryResponse(**{k: v for k, v in category_doc.items() if k != '_id'})

@api_router.get("/master/primary-categories", response_model=List[PrimaryCategoryResponse])
async def list_primary_categories(current_user: dict = Depends(get_current_user)):
    categories = await db.primary_categories.find({"is_active": True}, {"_id": 0}).to_list(100)
    return [PrimaryCategoryResponse(**c) for c in categories]

@api_router.put("/master/primary-categories/{category_id}", response_model=PrimaryCategoryResponse)
async def update_primary_category(category_id: str, category_data: PrimaryCategoryCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can update categories")
    
    update_data = category_data.model_dump(exclude_unset=True)
    result = await db.primary_categories.update_one({"id": category_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    category = await db.primary_categories.find_one({"id": category_id}, {"_id": 0})
    return PrimaryCategoryResponse(**category)

@api_router.delete("/master/primary-categories/{category_id}")
async def delete_primary_category(category_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can delete categories")
    
    result = await db.primary_categories.update_one({"id": category_id}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return {"message": "Category deleted"}

# Secondary Category
@api_router.post("/master/secondary-categories", response_model=SecondaryCategoryResponse)
async def create_secondary_category(category_data: SecondaryCategoryCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can create categories")
    
    primary = await db.primary_categories.find_one({"id": category_data.primary_category_id}, {"_id": 0})
    if not primary:
        raise HTTPException(status_code=404, detail="Primary category not found")
    
    category_id = str(uuid.uuid4())
    category_doc = {
        "id": category_id,
        "name": category_data.name,
        "primary_category_id": category_data.primary_category_id,
        "description": category_data.description,
        "is_active": True
    }
    
    await db.secondary_categories.insert_one(category_doc)
    
    response = SecondaryCategoryResponse(**{k: v for k, v in category_doc.items() if k != '_id'})
    response.primary_category_name = primary['name']
    return response

@api_router.get("/master/secondary-categories", response_model=List[SecondaryCategoryResponse])
async def list_secondary_categories(primary_category_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {"is_active": True}
    if primary_category_id:
        query['primary_category_id'] = primary_category_id
    
    categories = await db.secondary_categories.find(query, {"_id": 0}).to_list(100)
    
    result = []
    for cat in categories:
        primary = await db.primary_categories.find_one({"id": cat['primary_category_id']}, {"_id": 0})
        resp = SecondaryCategoryResponse(**cat)
        resp.primary_category_name = primary['name'] if primary else None
        result.append(resp)
    
    return result

@api_router.put("/master/secondary-categories/{category_id}", response_model=SecondaryCategoryResponse)
async def update_secondary_category(category_id: str, category_data: SecondaryCategoryCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can update categories")
    
    update_data = category_data.model_dump(exclude_unset=True)
    result = await db.secondary_categories.update_one({"id": category_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    category = await db.secondary_categories.find_one({"id": category_id}, {"_id": 0})
    primary = await db.primary_categories.find_one({"id": category['primary_category_id']}, {"_id": 0})
    
    resp = SecondaryCategoryResponse(**category)
    resp.primary_category_name = primary['name'] if primary else None
    return resp

@api_router.delete("/master/secondary-categories/{category_id}")
async def delete_secondary_category(category_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can delete categories")
    
    result = await db.secondary_categories.update_one({"id": category_id}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return {"message": "Category deleted"}

# Commission Templates
@api_router.post("/master/commission-templates", response_model=CommissionTemplateResponse)
async def create_commission_template(template_data: CommissionTemplateCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can create commission templates")
    
    template_id = str(uuid.uuid4())
    template_doc = {
        "id": template_id,
        "name": template_data.name,
        "vyapaar_percentage": template_data.vyapaar_percentage,
        "description": template_data.description,
        "is_active": True
    }
    
    await db.commission_templates.insert_one(template_doc)
    return CommissionTemplateResponse(**{k: v for k, v in template_doc.items() if k != '_id'})

@api_router.get("/master/commission-templates", response_model=List[CommissionTemplateResponse])
async def list_commission_templates(current_user: dict = Depends(get_current_user)):
    templates = await db.commission_templates.find({"is_active": True}, {"_id": 0}).to_list(100)
    return [CommissionTemplateResponse(**t) for t in templates]

@api_router.put("/master/commission-templates/{template_id}", response_model=CommissionTemplateResponse)
async def update_commission_template(template_id: str, template_data: CommissionTemplateCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can update commission templates")
    
    update_data = template_data.model_dump(exclude_unset=True)
    result = await db.commission_templates.update_one({"id": template_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Commission template not found")
    
    template = await db.commission_templates.find_one({"id": template_id}, {"_id": 0})
    return CommissionTemplateResponse(**template)

@api_router.delete("/master/commission-templates/{template_id}")
async def delete_commission_template(template_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can delete commission templates")
    
    result = await db.commission_templates.update_one({"id": template_id}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Commission template not found")
    
    return {"message": "Commission template deleted"}

# Document Tag Master Data Models
class DocumentTagCreate(BaseModel):
    name: str
    tag_key: str
    entity_type: str  # "lead" or "company"
    color: Optional[str] = "#4169E1"

class DocumentTagResponse(BaseModel):
    id: str
    name: str
    tag_key: str
    entity_type: str
    color: str
    is_active: bool

# Document Tags Master Data
@api_router.post("/master/document-tags", response_model=DocumentTagResponse)
async def create_document_tag(tag_data: DocumentTagCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can create document tags")
    
    if tag_data.entity_type not in ["lead", "company"]:
        raise HTTPException(status_code=400, detail="entity_type must be 'lead' or 'company'")
    
    # Check for duplicate tag_key within entity_type
    existing = await db.document_tags.find_one({
        "tag_key": tag_data.tag_key, 
        "entity_type": tag_data.entity_type,
        "is_active": True
    })
    if existing:
        raise HTTPException(status_code=400, detail="Tag key already exists for this entity type")
    
    tag_id = str(uuid.uuid4())
    tag_doc = {
        "id": tag_id,
        "name": tag_data.name,
        "tag_key": tag_data.tag_key.lower().replace(' ', '_'),
        "entity_type": tag_data.entity_type,
        "color": tag_data.color,
        "is_active": True
    }
    
    await db.document_tags.insert_one(tag_doc)
    return DocumentTagResponse(**{k: v for k, v in tag_doc.items() if k != '_id'})

@api_router.get("/master/document-tags", response_model=List[DocumentTagResponse])
async def list_document_tags(entity_type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {"is_active": True}
    if entity_type:
        query["entity_type"] = entity_type
    
    tags = await db.document_tags.find(query, {"_id": 0}).to_list(100)
    return [DocumentTagResponse(**t) for t in tags]

@api_router.put("/master/document-tags/{tag_id}", response_model=DocumentTagResponse)
async def update_document_tag(tag_id: str, tag_data: DocumentTagCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can update document tags")
    
    update_data = tag_data.model_dump(exclude_unset=True)
    if 'tag_key' in update_data:
        update_data['tag_key'] = update_data['tag_key'].lower().replace(' ', '_')
    
    result = await db.document_tags.update_one({"id": tag_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document tag not found")
    
    tag = await db.document_tags.find_one({"id": tag_id}, {"_id": 0})
    return DocumentTagResponse(**tag)

@api_router.delete("/master/document-tags/{tag_id}")
async def delete_document_tag(tag_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can delete document tags")
    
    result = await db.document_tags.update_one({"id": tag_id}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document tag not found")
    
    return {"message": "Document tag deleted"}

# ==================== EMAIL TEMPLATES ====================

# Email Template Event Types
class EmailTemplateEvent(str, Enum):
    NEW_LEAD = "new_lead"
    LEAD_ASSIGNED = "lead_assigned"
    LEAD_STATUS_CHANGED = "lead_status_changed"
    LEAD_WON = "lead_won"
    LEAD_LOST = "lead_lost"
    FOLLOW_UP_REMINDER = "follow_up_reminder"

# Template Variables by Event
EMAIL_TEMPLATE_VARIABLES = {
    "new_lead": [
        {"key": "{{lead_title}}", "description": "Title of the lead"},
        {"key": "{{customer_name}}", "description": "Customer's full name"},
        {"key": "{{customer_email}}", "description": "Customer's email address"},
        {"key": "{{customer_phone}}", "description": "Customer's phone number"},
        {"key": "{{customer_company}}", "description": "Customer's company name"},
        {"key": "{{category_name}}", "description": "Lead category"},
        {"key": "{{deal_value}}", "description": "Deal value amount"},
        {"key": "{{created_by}}", "description": "Name of person who created the lead"},
        {"key": "{{created_date}}", "description": "Date when lead was created"},
    ],
    "lead_assigned": [
        {"key": "{{lead_title}}", "description": "Title of the lead"},
        {"key": "{{customer_name}}", "description": "Customer's full name"},
        {"key": "{{customer_email}}", "description": "Customer's email address"},
        {"key": "{{customer_phone}}", "description": "Customer's phone number"},
        {"key": "{{partner_name}}", "description": "Assigned partner's name"},
        {"key": "{{partner_email}}", "description": "Assigned partner's email"},
        {"key": "{{category_name}}", "description": "Lead category"},
        {"key": "{{deal_value}}", "description": "Deal value amount"},
    ],
    "lead_status_changed": [
        {"key": "{{lead_title}}", "description": "Title of the lead"},
        {"key": "{{customer_name}}", "description": "Customer's full name"},
        {"key": "{{old_status}}", "description": "Previous status name"},
        {"key": "{{new_status}}", "description": "New status name"},
        {"key": "{{partner_name}}", "description": "Assigned partner's name"},
        {"key": "{{deal_value}}", "description": "Deal value amount"},
        {"key": "{{changed_by}}", "description": "Name of person who changed the status"},
    ],
    "lead_won": [
        {"key": "{{lead_title}}", "description": "Title of the lead"},
        {"key": "{{customer_name}}", "description": "Customer's full name"},
        {"key": "{{customer_company}}", "description": "Customer's company name"},
        {"key": "{{partner_name}}", "description": "Partner's name"},
        {"key": "{{deal_value}}", "description": "Final deal value"},
        {"key": "{{commission_amount}}", "description": "Commission earned"},
        {"key": "{{category_name}}", "description": "Lead category"},
    ],
    "lead_lost": [
        {"key": "{{lead_title}}", "description": "Title of the lead"},
        {"key": "{{customer_name}}", "description": "Customer's full name"},
        {"key": "{{partner_name}}", "description": "Partner's name"},
        {"key": "{{deal_value}}", "description": "Deal value"},
        {"key": "{{category_name}}", "description": "Lead category"},
        {"key": "{{lost_reason}}", "description": "Reason for losing (if provided)"},
    ],
    "follow_up_reminder": [
        {"key": "{{lead_title}}", "description": "Title of the lead"},
        {"key": "{{customer_name}}", "description": "Customer's full name"},
        {"key": "{{customer_phone}}", "description": "Customer's phone number"},
        {"key": "{{follow_up_date}}", "description": "Scheduled follow-up date"},
        {"key": "{{follow_up_notes}}", "description": "Notes for the follow-up"},
        {"key": "{{pending_with}}", "description": "Who the follow-up is pending with"},
        {"key": "{{recipient_name}}", "description": "Name of the email recipient"},
    ],
}

# Default templates
DEFAULT_EMAIL_TEMPLATES = {
    "new_lead": {
        "subject": "New Lead Created: {{lead_title}}",
        "body": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #2563eb;">New Lead Created</h2>
    <p>A new lead has been created in Vyapaar Network CRM.</p>
    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Lead Title:</strong> {{lead_title}}</p>
        <p><strong>Customer:</strong> {{customer_name}}</p>
        <p><strong>Email:</strong> {{customer_email}}</p>
        <p><strong>Category:</strong> {{category_name}}</p>
        <p><strong>Deal Value:</strong> {{deal_value}}</p>
        <p><strong>Created By:</strong> {{created_by}}</p>
    </div>
    <p>Login to CRM to view more details.</p>
    <p>Best regards,<br>Vyapaar Network CRM</p>
</div>"""
    },
    "lead_assigned": {
        "subject": "Lead Assigned to You: {{lead_title}}",
        "body": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #2563eb;">Lead Assigned to You</h2>
    <p>Hi {{partner_name}},</p>
    <p>A new lead has been assigned to you.</p>
    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Lead Title:</strong> {{lead_title}}</p>
        <p><strong>Customer:</strong> {{customer_name}}</p>
        <p><strong>Email:</strong> {{customer_email}}</p>
        <p><strong>Phone:</strong> {{customer_phone}}</p>
        <p><strong>Category:</strong> {{category_name}}</p>
        <p><strong>Deal Value:</strong> {{deal_value}}</p>
    </div>
    <p>Please login to CRM and follow up with the customer.</p>
    <p>Best regards,<br>Vyapaar Network CRM</p>
</div>"""
    },
    "lead_status_changed": {
        "subject": "Lead Status Updated: {{lead_title}}",
        "body": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #2563eb;">Lead Status Changed</h2>
    <p>The status of a lead has been updated.</p>
    <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Lead:</strong> {{lead_title}}</p>
        <p><strong>Customer:</strong> {{customer_name}}</p>
        <p><strong>Previous Status:</strong> {{old_status}}</p>
        <p><strong>New Status:</strong> <span style="color: #16a34a; font-weight: bold;">{{new_status}}</span></p>
        <p><strong>Changed By:</strong> {{changed_by}}</p>
    </div>
    <p>Best regards,<br>Vyapaar Network CRM</p>
</div>"""
    },
    "lead_won": {
        "subject": "🎉 Congratulations! Deal Won: {{lead_title}}",
        "body": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #16a34a;">🎉 Deal Won!</h2>
    <p>Congratulations! A deal has been successfully closed.</p>
    <div style="background: #dcfce7; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Lead:</strong> {{lead_title}}</p>
        <p><strong>Customer:</strong> {{customer_name}}</p>
        <p><strong>Company:</strong> {{customer_company}}</p>
        <p><strong>Partner:</strong> {{partner_name}}</p>
        <p><strong>Deal Value:</strong> <span style="font-size: 1.2em; color: #16a34a;">{{deal_value}}</span></p>
        <p><strong>Commission:</strong> {{commission_amount}}</p>
    </div>
    <p>Great work! Keep it up!</p>
    <p>Best regards,<br>Vyapaar Network CRM</p>
</div>"""
    },
    "lead_lost": {
        "subject": "Lead Lost: {{lead_title}}",
        "body": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #dc2626;">Lead Lost</h2>
    <p>Unfortunately, a lead has been marked as lost.</p>
    <div style="background: #fef2f2; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Lead:</strong> {{lead_title}}</p>
        <p><strong>Customer:</strong> {{customer_name}}</p>
        <p><strong>Partner:</strong> {{partner_name}}</p>
        <p><strong>Deal Value:</strong> {{deal_value}}</p>
        <p><strong>Category:</strong> {{category_name}}</p>
    </div>
    <p>Review the lead details to understand what went wrong and improve future conversions.</p>
    <p>Best regards,<br>Vyapaar Network CRM</p>
</div>"""
    },
    "follow_up_reminder": {
        "subject": "Follow-up Reminder: {{lead_title}}",
        "body": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #f59e0b;">⏰ Follow-up Reminder</h2>
    <p>Hi {{recipient_name}},</p>
    <p>This is a reminder for your upcoming follow-up.</p>
    <div style="background: #fef3c7; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p><strong>Lead:</strong> {{lead_title}}</p>
        <p><strong>Customer:</strong> {{customer_name}}</p>
        <p><strong>Phone:</strong> {{customer_phone}}</p>
        <p><strong>Scheduled Date:</strong> {{follow_up_date}}</p>
        <p><strong>Notes:</strong> {{follow_up_notes}}</p>
    </div>
    <p>Please ensure to complete this follow-up on time.</p>
    <p>Best regards,<br>Vyapaar Network CRM</p>
</div>"""
    }
}

# Email Template Models
class EmailTemplateCreate(BaseModel):
    event_type: EmailTemplateEvent
    subject: str
    body: str
    is_enabled: bool = True

class EmailTemplateUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    is_enabled: Optional[bool] = None

class EmailTemplateResponse(BaseModel):
    id: str
    event_type: str
    event_label: str
    subject: str
    body: str
    is_enabled: bool
    variables: List[Dict[str, str]]
    updated_at: Optional[str] = None

# Event labels for display
EVENT_LABELS = {
    "new_lead": "New Lead Created",
    "lead_assigned": "Lead Assigned to Partner",
    "lead_status_changed": "Lead Status Changed",
    "lead_won": "Lead Won (Deal Closed)",
    "lead_lost": "Lead Lost",
    "follow_up_reminder": "Follow-up Reminder"
}

# Email Template Routes
@api_router.get("/email-templates", response_model=List[EmailTemplateResponse])
async def list_email_templates(current_user: dict = Depends(get_current_user)):
    """Get all email templates"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can access email templates")
    
    templates = await db.email_templates.find({"is_active": True}, {"_id": 0}).to_list(100)
    
    # Create response with existing templates or defaults
    result = []
    for event_type in EmailTemplateEvent:
        existing = next((t for t in templates if t['event_type'] == event_type.value), None)
        
        if existing:
            result.append(EmailTemplateResponse(
                id=existing['id'],
                event_type=existing['event_type'],
                event_label=EVENT_LABELS.get(existing['event_type'], existing['event_type']),
                subject=existing['subject'],
                body=existing['body'],
                is_enabled=existing.get('is_enabled', True),
                variables=EMAIL_TEMPLATE_VARIABLES.get(existing['event_type'], []),
                updated_at=existing.get('updated_at')
            ))
        else:
            # Return default template
            default = DEFAULT_EMAIL_TEMPLATES.get(event_type.value, {"subject": "", "body": ""})
            result.append(EmailTemplateResponse(
                id="",
                event_type=event_type.value,
                event_label=EVENT_LABELS.get(event_type.value, event_type.value),
                subject=default['subject'],
                body=default['body'],
                is_enabled=True,
                variables=EMAIL_TEMPLATE_VARIABLES.get(event_type.value, []),
                updated_at=None
            ))
    
    return result

@api_router.get("/email-templates/{event_type}", response_model=EmailTemplateResponse)
async def get_email_template(event_type: str, current_user: dict = Depends(get_current_user)):
    """Get a specific email template"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can access email templates")
    
    if event_type not in [e.value for e in EmailTemplateEvent]:
        raise HTTPException(status_code=400, detail="Invalid event type")
    
    template = await db.email_templates.find_one({"event_type": event_type, "is_active": True}, {"_id": 0})
    
    if template:
        return EmailTemplateResponse(
            id=template['id'],
            event_type=template['event_type'],
            event_label=EVENT_LABELS.get(template['event_type'], template['event_type']),
            subject=template['subject'],
            body=template['body'],
            is_enabled=template.get('is_enabled', True),
            variables=EMAIL_TEMPLATE_VARIABLES.get(template['event_type'], []),
            updated_at=template.get('updated_at')
        )
    else:
        # Return default
        default = DEFAULT_EMAIL_TEMPLATES.get(event_type, {"subject": "", "body": ""})
        return EmailTemplateResponse(
            id="",
            event_type=event_type,
            event_label=EVENT_LABELS.get(event_type, event_type),
            subject=default['subject'],
            body=default['body'],
            is_enabled=True,
            variables=EMAIL_TEMPLATE_VARIABLES.get(event_type, []),
            updated_at=None
        )

@api_router.put("/email-templates/{event_type}", response_model=EmailTemplateResponse)
async def update_email_template(event_type: str, template_data: EmailTemplateUpdate, current_user: dict = Depends(get_current_user)):
    """Update or create an email template"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can update email templates")
    
    if event_type not in [e.value for e in EmailTemplateEvent]:
        raise HTTPException(status_code=400, detail="Invalid event type")
    
    existing = await db.email_templates.find_one({"event_type": event_type, "is_active": True}, {"_id": 0})
    now = datetime.now(timezone.utc).isoformat()
    
    if existing:
        # Update existing
        update_data = template_data.model_dump(exclude_unset=True, exclude_none=True)
        update_data['updated_at'] = now
        await db.email_templates.update_one({"id": existing['id']}, {"$set": update_data})
        template = await db.email_templates.find_one({"id": existing['id']}, {"_id": 0})
    else:
        # Create new
        default = DEFAULT_EMAIL_TEMPLATES.get(event_type, {"subject": "", "body": ""})
        template_id = str(uuid.uuid4())
        template = {
            "id": template_id,
            "event_type": event_type,
            "subject": template_data.subject or default['subject'],
            "body": template_data.body or default['body'],
            "is_enabled": template_data.is_enabled if template_data.is_enabled is not None else True,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }
        await db.email_templates.insert_one(template)
    
    return EmailTemplateResponse(
        id=template['id'],
        event_type=template['event_type'],
        event_label=EVENT_LABELS.get(template['event_type'], template['event_type']),
        subject=template['subject'],
        body=template['body'],
        is_enabled=template.get('is_enabled', True),
        variables=EMAIL_TEMPLATE_VARIABLES.get(template['event_type'], []),
        updated_at=template.get('updated_at')
    )

@api_router.post("/email-templates/{event_type}/reset")
async def reset_email_template(event_type: str, current_user: dict = Depends(get_current_user)):
    """Reset an email template to default"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can reset email templates")
    
    if event_type not in [e.value for e in EmailTemplateEvent]:
        raise HTTPException(status_code=400, detail="Invalid event type")
    
    # Soft delete existing
    await db.email_templates.update_many(
        {"event_type": event_type, "is_active": True},
        {"$set": {"is_active": False}}
    )
    
    return {"message": "Template reset to default"}

@api_router.post("/email-templates/{event_type}/preview")
async def preview_email_template(event_type: str, template_data: EmailTemplateUpdate, current_user: dict = Depends(get_current_user)):
    """Preview an email template with sample data"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can preview email templates")
    
    # Sample data for preview
    sample_data = {
        "{{lead_title}}": "Website Development Project",
        "{{customer_name}}": "John Smith",
        "{{customer_email}}": "john@example.com",
        "{{customer_phone}}": "+91 98765 43210",
        "{{customer_company}}": "Tech Solutions Ltd",
        "{{partner_name}}": "ABC Digital Services",
        "{{partner_email}}": "partner@abcdigital.com",
        "{{category_name}}": "IT Services",
        "{{deal_value}}": "₹1,50,000",
        "{{commission_amount}}": "₹22,500",
        "{{created_by}}": "Super Admin",
        "{{created_date}}": "11 Feb 2025",
        "{{old_status}}": "In Progress",
        "{{new_status}}": "Won",
        "{{changed_by}}": "Super Admin",
        "{{follow_up_date}}": "15 Feb 2025",
        "{{follow_up_notes}}": "Discuss project timeline and deliverables",
        "{{pending_with}}": "Customer",
        "{{recipient_name}}": "Sales Partner",
        "{{lost_reason}}": "Budget constraints"
    }
    
    subject = template_data.subject or ""
    body = template_data.body or ""
    
    # Replace variables with sample data
    for key, value in sample_data.items():
        subject = subject.replace(key, value)
        body = body.replace(key, value)
    
    return {
        "subject": subject,
        "body": body
    }

@api_router.get("/email-templates/variables/{event_type}")
async def get_template_variables(event_type: str, current_user: dict = Depends(get_current_user)):
    """Get available variables for an event type"""
    if event_type not in [e.value for e in EmailTemplateEvent]:
        raise HTTPException(status_code=400, detail="Invalid event type")
    
    return {
        "event_type": event_type,
        "event_label": EVENT_LABELS.get(event_type, event_type),
        "variables": EMAIL_TEMPLATE_VARIABLES.get(event_type, [])
    }

# Email Sending Helper with Template Support
async def render_and_send_email(event_type: str, to_email: str, variables: Dict[str, str]):
    """Render email template and send via SendGrid"""
    if not SENDGRID_API_KEY:
        logger.warning("SendGrid API key not configured, skipping email")
        return False
    
    # Get template
    template = await db.email_templates.find_one({"event_type": event_type, "is_active": True}, {"_id": 0})
    
    if template:
        if not template.get('is_enabled', True):
            logger.info(f"Email template {event_type} is disabled, skipping")
            return False
        subject = template['subject']
        body = template['body']
    else:
        # Use default
        default = DEFAULT_EMAIL_TEMPLATES.get(event_type)
        if not default:
            logger.warning(f"No template found for event {event_type}")
            return False
        subject = default['subject']
        body = default['body']
    
    # Replace variables
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        subject = subject.replace(placeholder, str(value) if value else "")
        body = body.replace(placeholder, str(value) if value else "")
    
    # Send email
    try:
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=body
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        logger.info(f"Email sent to {to_email} for event {event_type}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False

# ==================== DOCUMENT UPLOAD ROUTES ====================

@api_router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    entity_type: str = Form(...),  # "lead" or "company"
    entity_id: str = Form(...),
    tag: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """Upload a document for a lead or company"""
    # Validate entity type
    if entity_type not in ["lead", "company"]:
        raise HTTPException(status_code=400, detail="entity_type must be 'lead' or 'company'")
    
    # Validate entity exists
    if entity_type == "lead":
        entity = await db.leads.find_one({"id": entity_id}, {"_id": 0})
        if not entity:
            raise HTTPException(status_code=404, detail="Lead not found")
    else:
        entity = await db.companies.find_one({"id": entity_id}, {"_id": 0})
        if not entity:
            raise HTTPException(status_code=404, detail="Company not found")
    
    # Validate file size (max 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
    
    # Generate unique filename
    doc_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix if file.filename else ''
    filename = f"{doc_id}{ext}"
    filepath = UPLOAD_DIR / filename
    
    # Save file
    async with aiofiles.open(filepath, 'wb') as f:
        await f.write(content)
    
    # Save document metadata
    doc_record = {
        "id": doc_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "filename": filename,
        "original_filename": file.filename or "unknown",
        "file_size": len(content),
        "content_type": file.content_type or "application/octet-stream",
        "tag": tag,
        "description": description,
        "uploaded_by": current_user['id'],
        "uploaded_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.documents.insert_one(doc_record)
    
    uploader = await db.users.find_one({"id": current_user['id']}, {"_id": 0})
    
    return DocumentResponse(
        id=doc_id,
        filename=filename,
        original_filename=doc_record['original_filename'],
        file_size=doc_record['file_size'],
        content_type=doc_record['content_type'],
        tag=tag,
        description=description,
        uploaded_by=current_user['id'],
        uploaded_by_name=uploader['name'] if uploader else None,
        uploaded_at=doc_record['uploaded_at']
    )

@api_router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    """Download a document"""
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    filepath = UPLOAD_DIR / doc['filename']
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found on server")
    
    return FileResponse(
        path=str(filepath),
        filename=doc['original_filename'],
        media_type=doc['content_type']
    )

@api_router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a document (admin only)"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can delete documents")
    
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file
    filepath = UPLOAD_DIR / doc['filename']
    if filepath.exists():
        filepath.unlink()
    
    # Delete record
    await db.documents.delete_one({"id": doc_id})
    
    return {"message": "Document deleted successfully"}

@api_router.get("/documents/entity/{entity_type}/{entity_id}", response_model=List[DocumentResponse])
async def get_entity_documents(entity_type: str, entity_id: str, current_user: dict = Depends(get_current_user)):
    """Get all documents for an entity"""
    if entity_type not in ["lead", "company"]:
        raise HTTPException(status_code=400, detail="entity_type must be 'lead' or 'company'")
    
    documents = await db.documents.find({"entity_type": entity_type, "entity_id": entity_id}, {"_id": 0}).to_list(100)
    
    result = []
    for doc in documents:
        uploader = await db.users.find_one({"id": doc['uploaded_by']}, {"_id": 0})
        result.append(DocumentResponse(
            id=doc['id'],
            filename=doc['filename'],
            original_filename=doc['original_filename'],
            file_size=doc['file_size'],
            content_type=doc['content_type'],
            tag=doc['tag'],
            description=doc.get('description'),
            uploaded_by=doc['uploaded_by'],
            uploaded_by_name=uploader['name'] if uploader else None,
            uploaded_at=doc['uploaded_at']
        ))
    
    return result

# ==================== LEAD ROUTES ====================

async def enrich_lead(lead: dict) -> LeadResponse:
    """Enrich a single lead with related data - used for single lead fetch"""
    # Get related data
    selling_partner = None
    if lead.get('selling_partner_id'):
        selling_partner = await db.users.find_one({"id": lead['selling_partner_id']}, {"_id": 0})
    
    sales_associate = None
    if lead.get('sales_associate_id'):
        sales_associate = await db.users.find_one({"id": lead['sales_associate_id']}, {"_id": 0})
    
    referred_by_partner = None
    if lead.get('referred_by_partner_id'):
        referred_by_partner = await db.users.find_one({"id": lead['referred_by_partner_id']}, {"_id": 0})
    
    referred_by_associate = None
    if lead.get('referred_by_associate_id'):
        referred_by_associate = await db.users.find_one({"id": lead['referred_by_associate_id']}, {"_id": 0})
    
    primary_category = await db.primary_categories.find_one({"id": lead['primary_category_id']}, {"_id": 0})
    
    secondary_category = None
    if lead.get('secondary_category_id'):
        secondary_category = await db.secondary_categories.find_one({"id": lead['secondary_category_id']}, {"_id": 0})
    
    status = None
    if lead.get('status_id'):
        status = await db.lead_statuses.find_one({"id": lead['status_id']}, {"_id": 0})
    
    created_by_user = await db.users.find_one({"id": lead['created_by']}, {"_id": 0})
    
    # Get documents for this lead
    documents = await db.documents.find({"entity_type": "lead", "entity_id": lead['id']}, {"_id": 0}).to_list(100)
    doc_responses = []
    for doc in documents:
        uploader = await db.users.find_one({"id": doc['uploaded_by']}, {"_id": 0})
        doc_responses.append(DocumentResponse(
            id=doc['id'],
            filename=doc['filename'],
            original_filename=doc['original_filename'],
            file_size=doc['file_size'],
            content_type=doc['content_type'],
            tag=doc['tag'],
            description=doc.get('description'),
            uploaded_by=doc['uploaded_by'],
            uploaded_by_name=uploader['name'] if uploader else None,
            uploaded_at=doc['uploaded_at']
        ))
    
    # Calculate commission
    vyapaar_percentage = lead.get('commission_override')
    if not vyapaar_percentage:
        if selling_partner and selling_partner.get('company_id'):
            company = await db.companies.find_one({"id": selling_partner['company_id']}, {"_id": 0})
            if company:
                vyapaar_percentage = company.get('vyapaar_commission_percentage', 15.0)
            else:
                vyapaar_percentage = 15.0
        else:
            vyapaar_percentage = 15.0
    
    commission_breakdown = None
    if lead.get('deal_value', 0) > 0:
        commission_breakdown = calculate_commission(
            lead['deal_value'],
            vyapaar_percentage,
            lead.get('sales_associate_commission')
        )
    
    return LeadResponse(
        id=lead['id'],
        title=lead['title'],
        description=lead.get('description'),
        customer_name=lead['customer_name'],
        customer_email=lead['customer_email'],
        customer_phone=lead.get('customer_phone'),
        customer_company=lead.get('customer_company'),
        selling_partner_id=lead.get('selling_partner_id'),
        selling_partner_name=selling_partner['name'] if selling_partner else None,
        sales_associate_id=lead.get('sales_associate_id'),
        sales_associate_name=sales_associate['name'] if sales_associate else None,
        referred_by_partner_id=lead.get('referred_by_partner_id'),
        referred_by_partner_name=referred_by_partner['name'] if referred_by_partner else None,
        referred_by_associate_id=lead.get('referred_by_associate_id'),
        referred_by_associate_name=referred_by_associate['name'] if referred_by_associate else None,
        is_internal_request=lead.get('is_internal_request', False),
        primary_category_id=lead['primary_category_id'],
        primary_category_name=primary_category['name'] if primary_category else None,
        secondary_category_id=lead.get('secondary_category_id'),
        secondary_category_name=secondary_category['name'] if secondary_category else None,
        deal_value=lead.get('deal_value', 0),
        commission_override=lead.get('commission_override'),
        sales_associate_commission=lead.get('sales_associate_commission'),
        commission_breakdown=commission_breakdown,
        status_id=lead.get('status_id'),
        status_name=status['name'] if status else None,
        status_color=status['color'] if status else None,
        follow_ups=[FollowUpResponse(**f) for f in lead.get('follow_ups', [])],
        comments=[CommentResponse(**c) for c in lead.get('comments', [])],
        documents=doc_responses,
        assigned_partners=[PartnerAssignment(**p) for p in lead.get('assigned_partners', [])],
        active_partners_count=len([p for p in lead.get('assigned_partners', []) if p.get('status') == 'active']),
        created_by=lead['created_by'],
        created_by_name=created_by_user['name'] if created_by_user else None,
        created_at=lead['created_at'],
        updated_at=lead['updated_at']
    )

async def enrich_leads_bulk(leads: List[dict]) -> List[LeadResponse]:
    """Bulk enrich leads with related data - optimized for list queries"""
    if not leads:
        return []
    
    # Collect all unique IDs
    user_ids = set()
    category_ids = set()
    secondary_category_ids = set()
    status_ids = set()
    lead_ids = set()
    company_ids = set()
    
    for lead in leads:
        lead_ids.add(lead['id'])
        if lead.get('selling_partner_id'):
            user_ids.add(lead['selling_partner_id'])
        if lead.get('sales_associate_id'):
            user_ids.add(lead['sales_associate_id'])
        if lead.get('referred_by_partner_id'):
            user_ids.add(lead['referred_by_partner_id'])
        if lead.get('referred_by_associate_id'):
            user_ids.add(lead['referred_by_associate_id'])
        if lead.get('created_by'):
            user_ids.add(lead['created_by'])
        if lead.get('primary_category_id'):
            category_ids.add(lead['primary_category_id'])
        if lead.get('secondary_category_id'):
            secondary_category_ids.add(lead['secondary_category_id'])
        if lead.get('status_id'):
            status_ids.add(lead['status_id'])
    
    # Helper to return empty list as async
    async def empty_list():
        return []
    
    # Bulk fetch all related data in parallel
    users_list, categories_list, secondary_categories_list, statuses_list, documents_list = await asyncio.gather(
        db.users.find({"id": {"$in": list(user_ids)}}, {"_id": 0}).to_list(1000) if user_ids else empty_list(),
        db.primary_categories.find({"id": {"$in": list(category_ids)}}, {"_id": 0}).to_list(100) if category_ids else empty_list(),
        db.secondary_categories.find({"id": {"$in": list(secondary_category_ids)}}, {"_id": 0}).to_list(100) if secondary_category_ids else empty_list(),
        db.lead_statuses.find({"id": {"$in": list(status_ids)}}, {"_id": 0}).to_list(100) if status_ids else empty_list(),
        db.documents.find({"entity_type": "lead", "entity_id": {"$in": list(lead_ids)}}, {"_id": 0}).to_list(1000)
    )
    
    # Build lookup dictionaries
    users_map = {u['id']: u for u in users_list}
    categories_map = {c['id']: c for c in categories_list}
    secondary_categories_map = {c['id']: c for c in secondary_categories_list}
    statuses_map = {s['id']: s for s in statuses_list}
    
    # Group documents by lead_id
    docs_by_lead = {}
    doc_uploader_ids = set()
    for doc in documents_list:
        lead_id = doc['entity_id']
        if lead_id not in docs_by_lead:
            docs_by_lead[lead_id] = []
        docs_by_lead[lead_id].append(doc)
        if doc.get('uploaded_by'):
            doc_uploader_ids.add(doc['uploaded_by'])
    
    # Fetch document uploaders if not already in users_map
    missing_uploader_ids = doc_uploader_ids - set(users_map.keys())
    if missing_uploader_ids:
        uploaders = await db.users.find({"id": {"$in": list(missing_uploader_ids)}}, {"_id": 0}).to_list(100)
        for u in uploaders:
            users_map[u['id']] = u
    
    # Get company IDs for commission calculation
    for user in users_list:
        if user.get('company_id'):
            company_ids.add(user['company_id'])
    
    # Fetch companies for commission calculation
    companies_list = await db.companies.find({"id": {"$in": list(company_ids)}}, {"_id": 0}).to_list(100) if company_ids else []
    companies_map = {c['id']: c for c in companies_list}
    
    # Enrich each lead
    result = []
    for lead in leads:
        selling_partner = users_map.get(lead.get('selling_partner_id'))
        sales_associate = users_map.get(lead.get('sales_associate_id'))
        referred_by_partner = users_map.get(lead.get('referred_by_partner_id'))
        referred_by_associate = users_map.get(lead.get('referred_by_associate_id'))
        created_by_user = users_map.get(lead.get('created_by'))
        primary_category = categories_map.get(lead.get('primary_category_id'))
        secondary_category = secondary_categories_map.get(lead.get('secondary_category_id'))
        status = statuses_map.get(lead.get('status_id'))
        
        # Build document responses
        doc_responses = []
        for doc in docs_by_lead.get(lead['id'], []):
            uploader = users_map.get(doc.get('uploaded_by'))
            doc_responses.append(DocumentResponse(
                id=doc['id'],
                filename=doc['filename'],
                original_filename=doc['original_filename'],
                file_size=doc['file_size'],
                content_type=doc['content_type'],
                tag=doc['tag'],
                description=doc.get('description'),
                uploaded_by=doc['uploaded_by'],
                uploaded_by_name=uploader['name'] if uploader else None,
                uploaded_at=doc['uploaded_at']
            ))
        
        # Calculate commission
        vyapaar_percentage = lead.get('commission_override')
        if not vyapaar_percentage:
            if selling_partner and selling_partner.get('company_id'):
                company = companies_map.get(selling_partner['company_id'])
                if company:
                    vyapaar_percentage = company.get('vyapaar_commission_percentage', 15.0)
                else:
                    vyapaar_percentage = 15.0
            else:
                vyapaar_percentage = 15.0
        
        commission_breakdown = None
        if lead.get('deal_value', 0) > 0:
            commission_breakdown = calculate_commission(
                lead['deal_value'],
                vyapaar_percentage,
                lead.get('sales_associate_commission')
            )
        
        result.append(LeadResponse(
            id=lead['id'],
            title=lead['title'],
            description=lead.get('description'),
            customer_name=lead['customer_name'],
            customer_email=lead['customer_email'],
            customer_phone=lead.get('customer_phone'),
            customer_company=lead.get('customer_company'),
            selling_partner_id=lead.get('selling_partner_id'),
            selling_partner_name=selling_partner['name'] if selling_partner else None,
            sales_associate_id=lead.get('sales_associate_id'),
            sales_associate_name=sales_associate['name'] if sales_associate else None,
            referred_by_partner_id=lead.get('referred_by_partner_id'),
            referred_by_partner_name=referred_by_partner['name'] if referred_by_partner else None,
            referred_by_associate_id=lead.get('referred_by_associate_id'),
            referred_by_associate_name=referred_by_associate['name'] if referred_by_associate else None,
            is_internal_request=lead.get('is_internal_request', False),
            primary_category_id=lead['primary_category_id'],
            primary_category_name=primary_category['name'] if primary_category else None,
            secondary_category_id=lead.get('secondary_category_id'),
            secondary_category_name=secondary_category['name'] if secondary_category else None,
            deal_value=lead.get('deal_value', 0),
            commission_override=lead.get('commission_override'),
            sales_associate_commission=lead.get('sales_associate_commission'),
            commission_breakdown=commission_breakdown,
            status_id=lead.get('status_id'),
            status_name=status['name'] if status else None,
            status_color=status['color'] if status else None,
            follow_ups=[FollowUpResponse(**f) for f in lead.get('follow_ups', [])],
            comments=[CommentResponse(**c) for c in lead.get('comments', [])],
            documents=doc_responses,
            partner_history=[PartnerAssignment(**p) for p in lead.get('partner_history', [])],
            created_by=lead['created_by'],
            created_by_name=created_by_user['name'] if created_by_user else None,
            created_at=lead['created_at'],
            updated_at=lead['updated_at']
        ))
    
    return result

@api_router.post("/leads", response_model=LeadResponse)
async def create_lead(lead_data: LeadCreate, current_user: dict = Depends(get_current_user)):
    # Validate primary category
    primary = await db.primary_categories.find_one({"id": lead_data.primary_category_id}, {"_id": 0})
    if not primary:
        raise HTTPException(status_code=404, detail="Primary category not found")
    
    # Get status based on selling partner assignment
    status_id = lead_data.status_id
    if not status_id:
        # If no selling partner, set to Draft; otherwise set to New
        if not lead_data.selling_partner_id and current_user['role'] == UserRole.SUPER_ADMIN.value:
            draft_status = await db.lead_statuses.find_one({"name": "Draft", "is_active": True}, {"_id": 0})
            if draft_status:
                status_id = draft_status['id']
            else:
                # Fallback to first status
                default_status = await db.lead_statuses.find_one({"is_active": True}, {"_id": 0}, sort=[("order", 1)])
                if default_status:
                    status_id = default_status['id']
        else:
            new_status = await db.lead_statuses.find_one({"name": "New", "is_active": True}, {"_id": 0})
            if new_status:
                status_id = new_status['id']
            else:
                default_status = await db.lead_statuses.find_one({"is_active": True}, {"_id": 0}, sort=[("order", 1)])
                if default_status:
                    status_id = default_status['id']
    
    lead_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    lead_doc = {
        "id": lead_id,
        "title": lead_data.title,
        "description": lead_data.description,
        "customer_name": lead_data.customer_name,
        "customer_email": lead_data.customer_email,
        "customer_phone": lead_data.customer_phone,
        "customer_company": lead_data.customer_company,
        "selling_partner_id": lead_data.selling_partner_id,
        "sales_associate_id": lead_data.sales_associate_id,
        "primary_category_id": lead_data.primary_category_id,
        "secondary_category_id": lead_data.secondary_category_id,
        "deal_value": lead_data.deal_value,
        "commission_override": lead_data.commission_override,
        "sales_associate_commission": lead_data.sales_associate_commission,
        "status_id": status_id,
        "follow_ups": [],
        "comments": [],
        "created_by": current_user['id'],
        "created_at": now,
        "updated_at": now
    }
    
    await db.leads.insert_one(lead_doc)
    
    # Create notifications for new lead
    await create_notification_for_admins(
        notification_type="new_lead",
        title="New Lead Created",
        message=f"New lead '{lead_data.title}' created by {current_user['name']}",
        lead_id=lead_id
    )
    
    # Notify assigned selling partner
    if lead_data.selling_partner_id:
        await create_notification_for_user(
            lead_data.selling_partner_id,
            notification_type="lead_assigned",
            title="New Lead Assigned",
            message=f"You have been assigned a new lead: {lead_data.title}",
            lead_id=lead_id
        )
    
    return await enrich_lead(lead_doc)

@api_router.post("/leads/referral", response_model=LeadResponse)
async def create_lead_referral(referral_data: LeadReferralCreate, current_user: dict = Depends(get_current_user)):
    """Selling Partner or Sales Associate creates a lead referral - always in Draft status"""
    allowed_roles = [UserRole.SELLING_PARTNER.value, UserRole.SALES_ASSOCIATE.value]
    if current_user['role'] not in allowed_roles:
        raise HTTPException(status_code=403, detail="Only selling partners and sales associates can create lead referrals")
    
    # Validate primary category
    primary = await db.primary_categories.find_one({"id": referral_data.primary_category_id}, {"_id": 0})
    if not primary:
        raise HTTPException(status_code=404, detail="Primary category not found")
    
    # Get Draft status
    draft_status = await db.lead_statuses.find_one({"name": "Draft", "is_active": True}, {"_id": 0})
    if not draft_status:
        raise HTTPException(status_code=500, detail="Draft status not found")
    
    lead_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Build description with referral notes
    description = referral_data.description or ""
    if referral_data.referral_notes:
        description = f"{description}\n\n**Referral Notes:** {referral_data.referral_notes}".strip()
    
    # Determine referral source
    referred_by_partner_id = None
    referred_by_associate_id = None
    is_internal_request = referral_data.is_internal_request
    
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        referred_by_partner_id = current_user['id']
    else:
        referred_by_associate_id = current_user['id']
    
    lead_doc = {
        "id": lead_id,
        "title": referral_data.title,
        "description": description if description else None,
        "customer_name": referral_data.customer_name,
        "customer_email": referral_data.customer_email,
        "customer_phone": referral_data.customer_phone,
        "customer_company": referral_data.customer_company,
        "selling_partner_id": None,  # No partner assigned yet - will be assigned by admin
        "sales_associate_id": None,
        "referred_by_partner_id": referred_by_partner_id,
        "referred_by_associate_id": referred_by_associate_id,
        "is_internal_request": is_internal_request,  # Selling Partner requesting services
        "primary_category_id": referral_data.primary_category_id,
        "secondary_category_id": referral_data.secondary_category_id,
        "deal_value": referral_data.estimated_deal_value or 0,
        "commission_override": None,
        "sales_associate_commission": None,
        "status_id": draft_status['id'],
        "follow_ups": [],
        "comments": [],
        "created_by": current_user['id'],
        "created_at": now,
        "updated_at": now
    }
    
    await db.leads.insert_one(lead_doc)
    
    # Create notification for admins about new referral
    await create_notification_for_admins(
        notification_type="new_referral",
        title="New Lead Referral",
        message=f"{current_user['name']} submitted a new lead referral: {referral_data.title}",
        lead_id=lead_id
    )
    
    return await enrich_lead(lead_doc)

@api_router.get("/leads/my-referrals", response_model=List[LeadResponse])
async def list_my_referrals(current_user: dict = Depends(get_current_user)):
    """Selling Partner or Sales Associate lists their referred leads"""
    allowed_roles = [UserRole.SELLING_PARTNER.value, UserRole.SALES_ASSOCIATE.value]
    if current_user['role'] not in allowed_roles:
        raise HTTPException(status_code=403, detail="Only selling partners and sales associates can view their referrals")
    
    # Build query based on role
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        query = {"referred_by_partner_id": current_user['id']}
    else:
        query = {"referred_by_associate_id": current_user['id']}
    
    leads = await db.leads.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    return await enrich_leads_bulk(leads)

@api_router.get("/leads/internal-requests", response_model=List[LeadResponse])
async def list_internal_requests(current_user: dict = Depends(get_current_user)):
    """Selling Partner lists their internal service requests"""
    if current_user['role'] != UserRole.SELLING_PARTNER.value:
        raise HTTPException(status_code=403, detail="Only selling partners can view internal requests")
    
    # Get internal requests where the current partner is the requester
    query = {
        "referred_by_partner_id": current_user['id'],
        "is_internal_request": True
    }
    
    leads = await db.leads.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    return await enrich_leads_bulk(leads)

@api_router.get("/leads", response_model=List[LeadResponse])
async def list_leads(
    status_id: Optional[str] = None,
    primary_category_id: Optional[str] = None,
    selling_partner_id: Optional[str] = None,
    sales_associate_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    
    # Role-based filtering
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        query['selling_partner_id'] = current_user['id']
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        query['sales_associate_id'] = current_user['id']
    elif current_user['role'] == UserRole.CUSTOMER.value:
        query['created_by'] = current_user['id']
    
    # Additional filters
    if status_id:
        query['status_id'] = status_id
    if primary_category_id:
        query['primary_category_id'] = primary_category_id
    if selling_partner_id and current_user['role'] == UserRole.SUPER_ADMIN.value:
        query['selling_partner_id'] = selling_partner_id
    if sales_associate_id and current_user['role'] == UserRole.SUPER_ADMIN.value:
        query['sales_associate_id'] = sales_associate_id
    
    leads = await db.leads.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    return await enrich_leads_bulk(leads)

@api_router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Access control
    if current_user['role'] == UserRole.SELLING_PARTNER.value and lead.get('selling_partner_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value and lead.get('sales_associate_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user['role'] == UserRole.CUSTOMER.value and lead.get('created_by') != current_user['id']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return await enrich_lead(lead)

@api_router.put("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: str, lead_data: LeadUpdate, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Access control
    if current_user['role'] == UserRole.SELLING_PARTNER.value and lead.get('selling_partner_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        raise HTTPException(status_code=403, detail="Sales associates cannot update leads")
    elif current_user['role'] == UserRole.CUSTOMER.value and lead.get('created_by') != current_user['id']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    update_data = lead_data.model_dump(exclude_unset=True, exclude_none=True)
    update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if selling partner is being assigned to a Draft lead
    old_partner_id = lead.get('selling_partner_id')
    new_partner_id = update_data.get('selling_partner_id')
    status_changed = False
    
    # Track partner history when partner changes
    if 'selling_partner_id' in update_data and new_partner_id != old_partner_id:
        partner_history = lead.get('partner_history', [])
        
        # If there was an old partner, mark them as removed in history
        if old_partner_id:
            # Find the current assignment in history and mark it as removed
            for assignment in partner_history:
                if assignment.get('partner_id') == old_partner_id and not assignment.get('removed_at'):
                    assignment['removed_at'] = now
                    assignment['removed_by'] = current_user['id']
        
        # Add new partner to history
        if new_partner_id:
            new_partner = await db.users.find_one({"id": new_partner_id}, {"_id": 0})
            partner_history.append({
                "partner_id": new_partner_id,
                "partner_name": new_partner['name'] if new_partner else None,
                "assigned_at": now,
                "assigned_by": current_user['id'],
                "assigned_by_name": current_user['name'],
                "removed_at": None,
                "removed_by": None,
                "notes": f"Assigned by {current_user['name']}"
            })
        
        update_data['partner_history'] = partner_history
    
    if 'selling_partner_id' in update_data and update_data['selling_partner_id']:
        current_status = await db.lead_statuses.find_one({"id": lead.get('status_id')}, {"_id": 0})
        if current_status and current_status.get('name', '').lower() == 'draft':
            # Auto-change status from Draft to New when partner is assigned
            new_status = await db.lead_statuses.find_one({"name": "New", "is_active": True}, {"_id": 0})
            if new_status:
                update_data['status_id'] = new_status['id']
                status_changed = True
    
    await db.leads.update_one({"id": lead_id}, {"$set": update_data})
    
    updated_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    
    # Create notifications for lead assignment
    if new_partner_id and new_partner_id != old_partner_id:
        # Get partner details for SMS
        partner = await db.users.find_one({"id": new_partner_id}, {"_id": 0})
        partner_name = partner['name'] if partner else 'Unknown'
        
        await create_notification_for_user(
            new_partner_id,
            notification_type="lead_assigned",
            title="New Lead Assigned",
            message=f"You have been assigned a new lead: {updated_lead['title']}",
            lead_id=lead_id
        )
        # Notify admins about the assignment
        await create_notification_for_admins(
            notification_type="lead_assigned",
            title="Lead Assigned",
            message=f"Lead '{updated_lead['title']}' assigned to partner",
            lead_id=lead_id
        )
        
        # Send SMS notifications
        await send_lead_assignment_sms(new_partner_id, updated_lead['title'], updated_lead['customer_name'])
        await send_lead_assignment_sms_to_admins(updated_lead['title'], partner_name, updated_lead['customer_name'])
    
    # Create notification for status change
    if 'status_id' in update_data and update_data['status_id'] != lead.get('status_id'):
        new_status_doc = await db.lead_statuses.find_one({"id": update_data['status_id']}, {"_id": 0})
        status_name = new_status_doc['name'] if new_status_doc else 'Unknown'
        await create_notification_for_admins(
            notification_type="lead_status_change",
            title="Lead Status Updated",
            message=f"Lead '{updated_lead['title']}' status changed to {status_name}",
            lead_id=lead_id
        )
    
    return await enrich_lead(updated_lead)

@api_router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can delete leads")
    
    result = await db.leads.delete_one({"id": lead_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {"message": "Lead deleted"}

# Follow-ups
@api_router.post("/leads/{lead_id}/follow-ups", response_model=LeadResponse)
async def add_follow_up(lead_id: str, followup_data: FollowUpCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    followup = {
        "id": str(uuid.uuid4()),
        "scheduled_date": followup_data.scheduled_date,
        "notes": followup_data.notes,
        "pending_with": followup_data.pending_with,  # "selling_partner" or "customer"
        "is_completed": False,
        "completed_at": None,
        "completion_notes": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.leads.update_one(
        {"id": lead_id},
        {
            "$push": {"follow_ups": followup},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    # Schedule email reminder
    background_tasks.add_task(
        send_followup_reminder,
        current_user['email'],
        lead['title'],
        followup_data.scheduled_date,
        current_user['name']
    )
    
    updated_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return await enrich_lead(updated_lead)

@api_router.put("/leads/{lead_id}/follow-ups/{followup_id}/complete", response_model=LeadResponse)
async def complete_follow_up(lead_id: str, followup_id: str, completion_notes: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    follow_ups = lead.get('follow_ups', [])
    for fu in follow_ups:
        if fu['id'] == followup_id:
            fu['is_completed'] = True
            fu['completed_at'] = datetime.now(timezone.utc).isoformat()
            fu['completion_notes'] = completion_notes
            break
    
    await db.leads.update_one(
        {"id": lead_id},
        {
            "$set": {
                "follow_ups": follow_ups,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    updated_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return await enrich_lead(updated_lead)

# Comments
@api_router.post("/leads/{lead_id}/comments", response_model=LeadResponse)
async def add_comment(lead_id: str, comment_data: CommentCreate, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    comment = {
        "id": str(uuid.uuid4()),
        "content": comment_data.content,
        "user_id": current_user['id'],
        "user_name": current_user['name'],
        "user_role": current_user['role'],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.leads.update_one(
        {"id": lead_id},
        {
            "$push": {"comments": comment},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    updated_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return await enrich_lead(updated_lead)

# ==================== BULK IMPORT ====================

@api_router.get("/leads/import/template")
async def get_import_template(current_user: dict = Depends(get_current_user)):
    """Get CSV template for bulk lead import"""
    # Get categories and statuses for template reference
    categories = await db.primary_categories.find({"is_active": True}, {"_id": 0}).to_list(100)
    statuses = await db.lead_statuses.find({"is_active": True}, {"_id": 0}).to_list(100)
    
    category_names = ", ".join([c['name'] for c in categories])
    status_names = ", ".join([s['name'] for s in statuses])
    
    return {
        "columns": [
            {"name": "title", "required": True, "description": "Lead title", "example": "Website Development Project"},
            {"name": "description", "required": False, "description": "Lead description", "example": "Need a new corporate website"},
            {"name": "customer_name", "required": True, "description": "Customer contact name", "example": "John Doe"},
            {"name": "customer_email", "required": True, "description": "Customer email", "example": "john@company.com"},
            {"name": "customer_phone", "required": False, "description": "Customer phone", "example": "+91 98765 43210"},
            {"name": "customer_company", "required": False, "description": "Customer company name", "example": "ABC Corp"},
            {"name": "primary_category", "required": True, "description": f"Category name. Options: {category_names}", "example": "IT"},
            {"name": "deal_value", "required": False, "description": "Deal value in INR", "example": "100000"},
            {"name": "status", "required": False, "description": f"Lead status. Options: {status_names}. Default: New", "example": "New"}
        ],
        "sample_data": [
            {
                "title": "ERP Implementation",
                "description": "Complete ERP solution for manufacturing",
                "customer_name": "Rajesh Kumar",
                "customer_email": "rajesh@techcorp.in",
                "customer_phone": "+91 98765 43210",
                "customer_company": "TechCorp Industries",
                "primary_category": "IT",
                "deal_value": "500000",
                "status": "New"
            },
            {
                "title": "HR Consulting",
                "description": "Recruitment and training services",
                "customer_name": "Priya Sharma",
                "customer_email": "priya@startupxyz.com",
                "customer_phone": "+91 87654 32109",
                "customer_company": "StartupXYZ",
                "primary_category": "HR",
                "deal_value": "150000",
                "status": "Qualified"
            },
            {
                "title": "Digital Marketing Campaign",
                "description": "Social media and SEO services",
                "customer_name": "Amit Patel",
                "customer_email": "amit@retailbrand.com",
                "customer_phone": "",
                "customer_company": "RetailBrand Pvt Ltd",
                "primary_category": "Marketing",
                "deal_value": "75000",
                "status": "New"
            }
        ],
        "available_categories": [c['name'] for c in categories],
        "available_statuses": [s['name'] for s in statuses]
    }

@api_router.get("/leads/import/download-sample")
async def download_sample_csv(current_user: dict = Depends(get_current_user)):
    """Download sample CSV file for bulk import"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        'title', 'description', 'customer_name', 'customer_email', 
        'customer_phone', 'customer_company', 'primary_category', 
        'deal_value', 'status'
    ])
    
    # Sample data rows
    writer.writerow([
        'ERP Implementation', 'Complete ERP solution for manufacturing',
        'Rajesh Kumar', 'rajesh@techcorp.in', '+91 98765 43210',
        'TechCorp Industries', 'IT', '500000', 'New'
    ])
    writer.writerow([
        'HR Consulting', 'Recruitment and training services',
        'Priya Sharma', 'priya@startupxyz.com', '+91 87654 32109',
        'StartupXYZ', 'HR', '150000', 'Qualified'
    ])
    writer.writerow([
        'Digital Marketing Campaign', 'Social media and SEO services',
        'Amit Patel', 'amit@retailbrand.com', '',
        'RetailBrand Pvt Ltd', 'Marketing', '75000', 'New'
    ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lead_import_template.csv"}
    )

@api_router.post("/leads/import", response_model=BulkImportResult)
async def bulk_import_leads(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Bulk import leads from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
    
    # Read file content
    content = await file.read()
    content = content.decode('utf-8')
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(content))
    
    # Get categories and statuses for mapping
    categories = await db.primary_categories.find({"is_active": True}, {"_id": 0}).to_list(100)
    category_map = {c['name'].lower(): c['id'] for c in categories}
    
    statuses = await db.lead_statuses.find({"is_active": True}, {"_id": 0}).to_list(100)
    status_map = {s['name'].lower(): s['id'] for s in statuses}
    default_status = next((s['id'] for s in statuses if s['name'].lower() == 'new'), None)
    
    total_rows = 0
    successful = 0
    failed = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):  # Start from 2 (1 is header)
        total_rows += 1
        row_errors = []
        
        # Validate required fields
        title = row.get('title', '').strip()
        customer_name = row.get('customer_name', '').strip()
        customer_email = row.get('customer_email', '').strip()
        primary_category = row.get('primary_category', '').strip()
        
        if not title:
            row_errors.append("Title is required")
        if not customer_name:
            row_errors.append("Customer name is required")
        if not customer_email:
            row_errors.append("Customer email is required")
        elif not re.match(r'^[^@]+@[^@]+\.[^@]+$', customer_email):
            row_errors.append("Invalid email format")
        
        # Validate category
        category_id = category_map.get(primary_category.lower()) if primary_category else None
        if not category_id:
            row_errors.append(f"Invalid category: {primary_category}. Available: {', '.join(category_map.keys())}")
        
        # Get status
        status_name = row.get('status', 'New').strip()
        status_id = status_map.get(status_name.lower(), default_status)
        
        # Parse deal value
        deal_value = 0
        try:
            deal_value_str = row.get('deal_value', '0').strip()
            if deal_value_str:
                deal_value = float(deal_value_str.replace(',', ''))
        except ValueError:
            row_errors.append(f"Invalid deal value: {row.get('deal_value')}")
        
        if row_errors:
            failed += 1
            errors.append({"row": row_num, "errors": row_errors, "data": dict(row)})
            continue
        
        # Create lead
        lead_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        lead_doc = {
            "id": lead_id,
            "title": title,
            "description": row.get('description', '').strip() or None,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "customer_phone": row.get('customer_phone', '').strip() or None,
            "customer_company": row.get('customer_company', '').strip() or None,
            "selling_partner_id": None,
            "sales_associate_id": None,
            "primary_category_id": category_id,
            "secondary_category_id": None,
            "deal_value": deal_value,
            "commission_override": None,
            "sales_associate_commission": None,
            "status_id": status_id,
            "follow_ups": [],
            "comments": [],
            "created_by": current_user['id'],
            "created_at": now,
            "updated_at": now
        }
        
        try:
            await db.leads.insert_one(lead_doc)
            successful += 1
        except Exception as e:
            failed += 1
            errors.append({"row": row_num, "errors": [str(e)], "data": dict(row)})
    
    return BulkImportResult(
        total_rows=total_rows,
        successful=successful,
        failed=failed,
        errors=errors
    )

# ==================== DASHBOARD & REPORTS ====================

@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    
    # Role-based filtering
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        query['selling_partner_id'] = current_user['id']
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        query['sales_associate_id'] = current_user['id']
    elif current_user['role'] == UserRole.CUSTOMER.value:
        query['created_by'] = current_user['id']
    
    # Date filtering
    if start_date or end_date:
        query['created_at'] = {}
        if start_date:
            query['created_at']['$gte'] = start_date
        if end_date:
            query['created_at']['$lte'] = end_date
    
    # Get all leads matching query
    leads = await db.leads.find(query, {"_id": 0}).to_list(10000)
    
    # Get statuses for won/lost identification
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(100)
    status_map = {s['id']: s['name'].lower() for s in statuses}
    
    total_leads = len(leads)
    won_deals = 0
    lost_deals = 0
    total_revenue = 0
    total_commission = 0
    
    leads_by_status = {}
    leads_by_category = {}
    revenue_by_month = {}
    
    for lead in leads:
        status_name = status_map.get(lead.get('status_id', ''), '').lower()
        
        if 'won' in status_name:
            won_deals += 1
            deal_value = lead.get('deal_value', 0)
            total_revenue += deal_value
            
            # Calculate commission
            vyapaar_pct = lead.get('commission_override', 15.0)
            commission = deal_value * (vyapaar_pct / 100)
            if lead.get('sales_associate_commission'):
                sa_commission = commission * (lead['sales_associate_commission'] / 100)
                commission -= sa_commission
            total_commission += commission
        elif 'lost' in status_name:
            lost_deals += 1
        
        # Count by status
        status_id = lead.get('status_id', 'unknown')
        if status_id not in leads_by_status:
            status_info = next((s for s in statuses if s['id'] == status_id), None)
            leads_by_status[status_id] = {
                "name": status_info['name'] if status_info else "Unknown",
                "color": status_info['color'] if status_info else "#gray",
                "count": 0
            }
        leads_by_status[status_id]['count'] += 1
        
        # Count by category
        cat_id = lead.get('primary_category_id', 'unknown')
        if cat_id not in leads_by_category:
            leads_by_category[cat_id] = {"name": "Unknown", "count": 0}
        leads_by_category[cat_id]['count'] += 1
        
        # Revenue by month
        if 'won' in status_name and lead.get('deal_value', 0) > 0:
            month = lead['created_at'][:7]  # YYYY-MM
            if month not in revenue_by_month:
                revenue_by_month[month] = 0
            revenue_by_month[month] += lead['deal_value']
    
    # Get category names
    categories = await db.primary_categories.find({}, {"_id": 0}).to_list(100)
    cat_map = {c['id']: c['name'] for c in categories}
    for cat_id in leads_by_category:
        if cat_id in cat_map:
            leads_by_category[cat_id]['name'] = cat_map[cat_id]
    
    conversion_rate = (won_deals / total_leads * 100) if total_leads > 0 else 0
    
    return DashboardStats(
        total_leads=total_leads,
        won_deals=won_deals,
        lost_deals=lost_deals,
        total_revenue=round(total_revenue, 2),
        total_commission=round(total_commission, 2),
        conversion_rate=round(conversion_rate, 2),
        leads_by_status=[{"id": k, **v} for k, v in leads_by_status.items()],
        leads_by_category=[{"id": k, **v} for k, v in leads_by_category.items()],
        revenue_trend=[{"month": k, "revenue": v} for k, v in sorted(revenue_by_month.items())]
    )

@api_router.get("/reports/selling-partner/{partner_id}")
async def get_selling_partner_report(
    partner_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    if current_user['role'] not in [UserRole.SUPER_ADMIN.value, UserRole.SELLING_PARTNER.value]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user['role'] == UserRole.SELLING_PARTNER.value and current_user['id'] != partner_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = {"selling_partner_id": partner_id}
    if start_date:
        query['created_at'] = {"$gte": start_date}
    if end_date:
        if 'created_at' not in query:
            query['created_at'] = {}
        query['created_at']['$lte'] = end_date
    
    leads = await db.leads.find(query, {"_id": 0}).to_list(10000)
    
    # Get statuses
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(100)
    status_map = {s['id']: s['name'].lower() for s in statuses}
    
    total_deals = 0
    won_deals = 0
    total_revenue = 0
    total_commission_earned = 0
    
    for lead in leads:
        total_deals += 1
        status_name = status_map.get(lead.get('status_id', ''), '').lower()
        
        if 'won' in status_name:
            won_deals += 1
            deal_value = lead.get('deal_value', 0)
            total_revenue += deal_value
            
            vyapaar_pct = lead.get('commission_override', 15.0)
            partner_share = deal_value * (1 - vyapaar_pct / 100)
            total_commission_earned += partner_share
    
    partner = await db.users.find_one({"id": partner_id}, {"_id": 0, "password": 0})
    
    return {
        "partner_id": partner_id,
        "partner_name": partner['name'] if partner else "Unknown",
        "total_deals": total_deals,
        "won_deals": won_deals,
        "conversion_rate": round(won_deals / total_deals * 100, 2) if total_deals > 0 else 0,
        "total_revenue": round(total_revenue, 2),
        "total_commission_earned": round(total_commission_earned, 2)
    }

@api_router.get("/reports/sales-associate/{associate_id}")
async def get_sales_associate_report(
    associate_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    if current_user['role'] not in [UserRole.SUPER_ADMIN.value, UserRole.SALES_ASSOCIATE.value]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user['role'] == UserRole.SALES_ASSOCIATE.value and current_user['id'] != associate_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = {"sales_associate_id": associate_id}
    if start_date:
        query['created_at'] = {"$gte": start_date}
    if end_date:
        if 'created_at' not in query:
            query['created_at'] = {}
        query['created_at']['$lte'] = end_date
    
    leads = await db.leads.find(query, {"_id": 0}).to_list(10000)
    
    # Get statuses
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(100)
    status_map = {s['id']: s['name'].lower() for s in statuses}
    
    total_referrals = 0
    converted_deals = 0
    total_earnings = 0
    
    for lead in leads:
        total_referrals += 1
        status_name = status_map.get(lead.get('status_id', ''), '').lower()
        
        if 'won' in status_name:
            converted_deals += 1
            deal_value = lead.get('deal_value', 0)
            vyapaar_pct = lead.get('commission_override', 15.0)
            vyapaar_share = deal_value * (vyapaar_pct / 100)
            
            sa_pct = lead.get('sales_associate_commission', 0)
            if sa_pct:
                total_earnings += vyapaar_share * (sa_pct / 100)
    
    associate = await db.users.find_one({"id": associate_id}, {"_id": 0, "password": 0})
    
    return {
        "associate_id": associate_id,
        "associate_name": associate['name'] if associate else "Unknown",
        "total_referrals": total_referrals,
        "converted_deals": converted_deals,
        "conversion_rate": round(converted_deals / total_referrals * 100, 2) if total_referrals > 0 else 0,
        "total_earnings": round(total_earnings, 2)
    }

@api_router.get("/reports/export")
async def export_leads(
    format: str = "csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    
    # Role-based filtering
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        query['selling_partner_id'] = current_user['id']
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        query['sales_associate_id'] = current_user['id']
    elif current_user['role'] == UserRole.CUSTOMER.value:
        query['created_by'] = current_user['id']
    
    if start_date:
        query['created_at'] = {"$gte": start_date}
    if end_date:
        if 'created_at' not in query:
            query['created_at'] = {}
        query['created_at']['$lte'] = end_date
    
    leads = await db.leads.find(query, {"_id": 0}).to_list(10000)
    
    # Get all related data
    statuses = {s['id']: s['name'] for s in await db.lead_statuses.find({}, {"_id": 0}).to_list(100)}
    categories = {c['id']: c['name'] for c in await db.primary_categories.find({}, {"_id": 0}).to_list(100)}
    users = {u['id']: u['name'] for u in await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)}
    
    export_data = []
    for lead in leads:
        export_data.append({
            "Title": lead['title'],
            "Customer Name": lead['customer_name'],
            "Customer Email": lead['customer_email'],
            "Customer Company": lead.get('customer_company', ''),
            "Status": statuses.get(lead.get('status_id', ''), 'Unknown'),
            "Category": categories.get(lead.get('primary_category_id', ''), 'Unknown'),
            "Deal Value": lead.get('deal_value', 0),
            "Selling Partner": users.get(lead.get('selling_partner_id', ''), ''),
            "Sales Associate": users.get(lead.get('sales_associate_id', ''), ''),
            "Created At": lead['created_at']
        })
    
    return {"data": export_data, "format": format}

# ==================== ENHANCED REPORTS ====================

@api_router.get("/reports/vyapaar-revenue")
async def get_vyapaar_revenue_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,  # monthly, quarterly, yearly
    current_user: dict = Depends(get_current_user)
):
    """Vyapaar Internal Revenue Report - Admin only"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can access this report")
    
    query = {}
    if start_date:
        query['created_at'] = {"$gte": start_date}
    if end_date:
        if 'created_at' not in query:
            query['created_at'] = {}
        query['created_at']['$lte'] = end_date
    
    leads = await db.leads.find(query, {"_id": 0}).to_list(10000)
    
    # Get statuses
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(100)
    status_map = {s['id']: s['name'].lower() for s in statuses}
    
    # Get categories
    categories = await db.primary_categories.find({}, {"_id": 0}).to_list(100)
    category_map = {c['id']: c['name'] for c in categories}
    
    # Get users
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)
    user_map = {u['id']: u['name'] for u in users}
    
    total_gross_commission = 0
    total_sa_payouts = 0
    total_net_revenue = 0
    partner_wise = {}
    category_wise = {}
    period_wise = {}
    won_deals = []
    
    for lead in leads:
        status_name = status_map.get(lead.get('status_id', ''), '').lower()
        
        if 'won' in status_name:
            deal_value = lead.get('deal_value', 0)
            vyapaar_pct = lead.get('commission_override') or 15.0
            vyapaar_gross = deal_value * (vyapaar_pct / 100)
            
            sa_pct = lead.get('sales_associate_commission', 0) or 0
            sa_payout = vyapaar_gross * (sa_pct / 100) if sa_pct else 0
            vyapaar_net = vyapaar_gross - sa_payout
            
            total_gross_commission += vyapaar_gross
            total_sa_payouts += sa_payout
            total_net_revenue += vyapaar_net
            
            # Partner-wise
            partner_id = lead.get('selling_partner_id')
            if partner_id:
                if partner_id not in partner_wise:
                    partner_wise[partner_id] = {
                        "name": user_map.get(partner_id, "Unknown"),
                        "deals": 0,
                        "revenue": 0,
                        "vyapaar_commission": 0
                    }
                partner_wise[partner_id]['deals'] += 1
                partner_wise[partner_id]['revenue'] += deal_value
                partner_wise[partner_id]['vyapaar_commission'] += vyapaar_gross
            
            # Category-wise
            cat_id = lead.get('primary_category_id')
            if cat_id:
                if cat_id not in category_wise:
                    category_wise[cat_id] = {
                        "name": category_map.get(cat_id, "Unknown"),
                        "deals": 0,
                        "revenue": 0,
                        "commission": 0
                    }
                category_wise[cat_id]['deals'] += 1
                category_wise[cat_id]['revenue'] += deal_value
                category_wise[cat_id]['commission'] += vyapaar_gross
            
            # Period-wise
            created_at = lead.get('created_at', '')[:10]
            if period == 'monthly':
                period_key = created_at[:7]
            elif period == 'quarterly':
                month = int(created_at[5:7])
                quarter = (month - 1) // 3 + 1
                period_key = f"{created_at[:4]}-Q{quarter}"
            elif period == 'yearly':
                period_key = created_at[:4]
            else:
                period_key = created_at[:7]  # default to monthly
            
            if period_key not in period_wise:
                period_wise[period_key] = {
                    "period": period_key,
                    "deals": 0,
                    "revenue": 0,
                    "gross_commission": 0,
                    "sa_payouts": 0,
                    "net_revenue": 0
                }
            period_wise[period_key]['deals'] += 1
            period_wise[period_key]['revenue'] += deal_value
            period_wise[period_key]['gross_commission'] += vyapaar_gross
            period_wise[period_key]['sa_payouts'] += sa_payout
            period_wise[period_key]['net_revenue'] += vyapaar_net
            
            # Add to won deals list
            won_deals.append({
                "id": lead['id'],
                "title": lead['title'],
                "deal_value": deal_value,
                "vyapaar_commission": round(vyapaar_gross, 2),
                "sa_payout": round(sa_payout, 2),
                "net_revenue": round(vyapaar_net, 2),
                "partner": user_map.get(partner_id, "Unassigned"),
                "category": category_map.get(cat_id, "Unknown"),
                "date": lead.get('created_at', '')[:10]
            })
    
    return {
        "summary": {
            "total_won_deals": len(won_deals),
            "total_deal_value": round(sum(d['deal_value'] for d in won_deals), 2),
            "gross_commission": round(total_gross_commission, 2),
            "sa_payouts": round(total_sa_payouts, 2),
            "net_revenue": round(total_net_revenue, 2)
        },
        "partner_profitability": sorted(partner_wise.values(), key=lambda x: x['vyapaar_commission'], reverse=True),
        "category_contribution": sorted(category_wise.values(), key=lambda x: x['commission'], reverse=True),
        "period_breakdown": sorted(period_wise.values(), key=lambda x: x['period']),
        "deals": won_deals
    }

@api_router.get("/reports/deal/{lead_id}/commission-statement")
async def get_deal_commission_statement(
    lead_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deal-Level Commission Statement with full breakdown"""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Access control
    if current_user['role'] == UserRole.SELLING_PARTNER.value and lead.get('selling_partner_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value and lead.get('sales_associate_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user['role'] == UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get related data
    selling_partner = None
    partner_company = None
    if lead.get('selling_partner_id'):
        selling_partner = await db.users.find_one({"id": lead['selling_partner_id']}, {"_id": 0, "password": 0})
        if selling_partner and selling_partner.get('company_id'):
            partner_company = await db.companies.find_one({"id": selling_partner['company_id']}, {"_id": 0})
    
    sales_associate = None
    if lead.get('sales_associate_id'):
        sales_associate = await db.users.find_one({"id": lead['sales_associate_id']}, {"_id": 0, "password": 0})
    
    status = await db.lead_statuses.find_one({"id": lead.get('status_id')}, {"_id": 0})
    category = await db.primary_categories.find_one({"id": lead.get('primary_category_id')}, {"_id": 0})
    
    # Calculate commission breakdown
    deal_value = lead.get('deal_value', 0)
    
    # Get base commission from partner company
    base_commission_pct = partner_company.get('vyapaar_commission_percentage', 15.0) if partner_company else 15.0
    
    # Check for override
    override_pct = lead.get('commission_override')
    final_vyapaar_pct = override_pct if override_pct is not None else base_commission_pct
    
    # Calculate amounts
    vyapaar_gross = deal_value * (final_vyapaar_pct / 100)
    selling_partner_revenue = deal_value - vyapaar_gross
    
    sa_pct = lead.get('sales_associate_commission', 0) or 0
    sa_commission = vyapaar_gross * (sa_pct / 100) if sa_pct else 0
    vyapaar_net = vyapaar_gross - sa_commission
    
    # Check if locked
    locked_commission = lead.get('locked_commission')
    is_locked = locked_commission is not None
    
    return {
        "deal_info": {
            "id": lead['id'],
            "title": lead['title'],
            "customer_name": lead['customer_name'],
            "customer_company": lead.get('customer_company'),
            "category": category['name'] if category else "Unknown",
            "status": status['name'] if status else "Unknown",
            "created_at": lead['created_at'],
            "updated_at": lead['updated_at']
        },
        "participants": {
            "selling_partner": {
                "id": selling_partner['id'] if selling_partner else None,
                "name": selling_partner['name'] if selling_partner else "Unassigned",
                "company": partner_company['name'] if partner_company else None
            } if selling_partner else None,
            "sales_associate": {
                "id": sales_associate['id'],
                "name": sales_associate['name']
            } if sales_associate else None
        },
        "commission_calculation": {
            "deal_value": deal_value,
            "base_commission_percentage": base_commission_pct,
            "override_percentage": override_pct,
            "final_vyapaar_percentage": final_vyapaar_pct,
            "vyapaar_gross_commission": round(vyapaar_gross, 2),
            "selling_partner_revenue": round(selling_partner_revenue, 2),
            "sales_associate_percentage": sa_pct if sa_pct else None,
            "sales_associate_commission": round(sa_commission, 2) if sa_commission else None,
            "vyapaar_net_earnings": round(vyapaar_net, 2)
        },
        "is_locked": is_locked,
        "locked_commission": locked_commission,
        "calculation_timestamp": datetime.now(timezone.utc).isoformat()
    }

@api_router.get("/reports/selling-partner/{partner_id}/detailed")
async def get_detailed_partner_report(
    partner_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Detailed Selling Partner Performance Report"""
    if current_user['role'] not in [UserRole.SUPER_ADMIN.value, UserRole.SELLING_PARTNER.value]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user['role'] == UserRole.SELLING_PARTNER.value and current_user['id'] != partner_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = {"selling_partner_id": partner_id}
    if start_date:
        query['created_at'] = {"$gte": start_date}
    if end_date:
        if 'created_at' not in query:
            query['created_at'] = {}
        query['created_at']['$lte'] = end_date
    
    leads = await db.leads.find(query, {"_id": 0}).to_list(10000)
    
    # Get partner info
    partner = await db.users.find_one({"id": partner_id}, {"_id": 0, "password": 0})
    partner_company = None
    if partner and partner.get('company_id'):
        partner_company = await db.companies.find_one({"id": partner['company_id']}, {"_id": 0})
    
    # Get statuses and categories
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(100)
    status_map = {s['id']: s['name'].lower() for s in statuses}
    
    categories = await db.primary_categories.find({}, {"_id": 0}).to_list(100)
    category_map = {c['id']: c['name'] for c in categories}
    
    # Aggregate data
    total_deals = len(leads)
    won_deals = 0
    lost_deals = 0
    total_deal_value = 0
    total_revenue_generated = 0
    total_commission_to_vyapaar = 0
    category_breakdown = {}
    period_breakdown = {}
    deals_list = []
    
    for lead in leads:
        status_name = status_map.get(lead.get('status_id', ''), '').lower()
        deal_value = lead.get('deal_value', 0)
        total_deal_value += deal_value
        
        # Category breakdown
        cat_id = lead.get('primary_category_id')
        cat_name = category_map.get(cat_id, "Unknown")
        if cat_name not in category_breakdown:
            category_breakdown[cat_name] = {"deals": 0, "value": 0, "won": 0}
        category_breakdown[cat_name]['deals'] += 1
        category_breakdown[cat_name]['value'] += deal_value
        
        # Period breakdown
        created_at = lead.get('created_at', '')[:10]
        if period == 'monthly':
            period_key = created_at[:7]
        elif period == 'quarterly':
            month = int(created_at[5:7]) if len(created_at) >= 7 else 1
            quarter = (month - 1) // 3 + 1
            period_key = f"{created_at[:4]}-Q{quarter}"
        elif period == 'yearly':
            period_key = created_at[:4]
        else:
            period_key = created_at[:7]
        
        if period_key not in period_breakdown:
            period_breakdown[period_key] = {"deals": 0, "won": 0, "value": 0, "revenue": 0}
        period_breakdown[period_key]['deals'] += 1
        period_breakdown[period_key]['value'] += deal_value
        
        if 'won' in status_name:
            won_deals += 1
            category_breakdown[cat_name]['won'] += 1
            period_breakdown[period_key]['won'] += 1
            
            vyapaar_pct = lead.get('commission_override') or 15.0
            partner_revenue = deal_value * (1 - vyapaar_pct / 100)
            total_revenue_generated += partner_revenue
            total_commission_to_vyapaar += deal_value * (vyapaar_pct / 100)
            period_breakdown[period_key]['revenue'] += partner_revenue
            
            deals_list.append({
                "id": lead['id'],
                "title": lead['title'],
                "deal_value": deal_value,
                "partner_revenue": round(partner_revenue, 2),
                "vyapaar_commission": round(deal_value * (vyapaar_pct / 100), 2),
                "category": cat_name,
                "date": created_at
            })
        elif 'lost' in status_name:
            lost_deals += 1
    
    return {
        "partner_info": {
            "id": partner_id,
            "name": partner['name'] if partner else "Unknown",
            "company": partner_company['name'] if partner_company else None,
            "base_commission_rate": partner_company.get('vyapaar_commission_percentage', 15.0) if partner_company else 15.0
        },
        "summary": {
            "total_deals": total_deals,
            "won_deals": won_deals,
            "lost_deals": lost_deals,
            "conversion_rate": round(won_deals / total_deals * 100, 2) if total_deals > 0 else 0,
            "total_deal_value": round(total_deal_value, 2),
            "total_revenue_generated": round(total_revenue_generated, 2),
            "commission_paid_to_vyapaar": round(total_commission_to_vyapaar, 2)
        },
        "category_breakdown": [{"category": k, **v} for k, v in sorted(category_breakdown.items(), key=lambda x: x[1]['value'], reverse=True)],
        "period_breakdown": sorted([{"period": k, **v} for k, v in period_breakdown.items()], key=lambda x: x['period']),
        "won_deals": deals_list
    }

@api_router.get("/reports/grid-performance")
async def get_grid_performance_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    partner_id: Optional[str] = None,
    category_id: Optional[str] = None,
    status_id: Optional[str] = None,
    sort_by: Optional[str] = "deal_value",  # deal_value, created_at, vyapaar_commission, partner_revenue
    sort_order: Optional[str] = "desc",  # asc, desc
    current_user: dict = Depends(get_current_user)
):
    """Grid Performance Report - Detailed performance data for all partners (Admin only)"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can access this report")
    
    # Build query
    query = {}
    if start_date:
        query['created_at'] = {"$gte": start_date}
    if end_date:
        if 'created_at' not in query:
            query['created_at'] = {}
        query['created_at']['$lte'] = end_date
    if partner_id:
        query['selling_partner_id'] = partner_id
    if category_id:
        query['primary_category_id'] = category_id
    if status_id:
        query['status_id'] = status_id
    
    leads = await db.leads.find(query, {"_id": 0}).to_list(10000)
    
    # Get reference data
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(100)
    status_map = {s['id']: s for s in statuses}
    
    categories = await db.primary_categories.find({}, {"_id": 0}).to_list(100)
    category_map = {c['id']: c['name'] for c in categories}
    
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)
    user_map = {u['id']: u for u in users}
    
    companies = await db.companies.find({}, {"_id": 0}).to_list(1000)
    company_map = {c['id']: c for c in companies}
    
    # Build grid data
    grid_data = []
    summary = {
        "total_leads": 0,
        "total_deal_value": 0,
        "total_vyapaar_commission": 0,
        "total_partner_revenue": 0,
        "won_deals": 0,
        "lost_deals": 0,
        "pending_deals": 0
    }
    
    partner_summary = {}
    
    for lead in leads:
        status = status_map.get(lead.get('status_id', ''), {})
        status_name = status.get('name', 'Unknown').lower()
        
        partner = user_map.get(lead.get('selling_partner_id'), {})
        partner_company = company_map.get(partner.get('company_id', ''), {}) if partner else {}
        
        deal_value = lead.get('deal_value', 0)
        vyapaar_pct = lead.get('commission_override') or partner_company.get('vyapaar_commission_percentage', 15.0)
        vyapaar_commission = deal_value * (vyapaar_pct / 100)
        partner_revenue = deal_value - vyapaar_commission
        
        # Update summary
        summary['total_leads'] += 1
        summary['total_deal_value'] += deal_value
        
        if 'won' in status_name:
            summary['won_deals'] += 1
            summary['total_vyapaar_commission'] += vyapaar_commission
            summary['total_partner_revenue'] += partner_revenue
        elif 'lost' in status_name:
            summary['lost_deals'] += 1
        else:
            summary['pending_deals'] += 1
        
        # Partner summary
        partner_id_key = lead.get('selling_partner_id', 'unassigned')
        if partner_id_key not in partner_summary:
            partner_summary[partner_id_key] = {
                "partner_id": partner_id_key,
                "partner_name": partner.get('name', 'Unassigned'),
                "company_name": partner_company.get('name', '-'),
                "total_leads": 0,
                "won_deals": 0,
                "total_deal_value": 0,
                "vyapaar_commission": 0,
                "partner_revenue": 0,
                "conversion_rate": 0
            }
        
        partner_summary[partner_id_key]['total_leads'] += 1
        partner_summary[partner_id_key]['total_deal_value'] += deal_value
        
        if 'won' in status_name:
            partner_summary[partner_id_key]['won_deals'] += 1
            partner_summary[partner_id_key]['vyapaar_commission'] += vyapaar_commission
            partner_summary[partner_id_key]['partner_revenue'] += partner_revenue
        
        # Grid row
        grid_data.append({
            "id": lead['id'],
            "title": lead['title'],
            "customer_name": lead['customer_name'],
            "customer_email": lead['customer_email'],
            "customer_company": lead.get('customer_company', '-'),
            "partner_id": lead.get('selling_partner_id'),
            "partner_name": partner.get('name', 'Unassigned'),
            "company_name": partner_company.get('name', '-'),
            "category": category_map.get(lead.get('primary_category_id'), 'Unknown'),
            "status": status.get('name', 'Unknown'),
            "status_color": status.get('color', '#94A3B8'),
            "deal_value": deal_value,
            "vyapaar_commission_pct": vyapaar_pct,
            "vyapaar_commission": round(vyapaar_commission, 2),
            "partner_revenue": round(partner_revenue, 2),
            "created_at": lead['created_at'],
            "updated_at": lead['updated_at'],
            "is_won": 'won' in status_name
        })
    
    # Calculate conversion rates
    for ps in partner_summary.values():
        if ps['total_leads'] > 0:
            ps['conversion_rate'] = round(ps['won_deals'] / ps['total_leads'] * 100, 2)
        ps['vyapaar_commission'] = round(ps['vyapaar_commission'], 2)
        ps['partner_revenue'] = round(ps['partner_revenue'], 2)
    
    # Sort grid data
    reverse = sort_order == 'desc'
    if sort_by in ['deal_value', 'vyapaar_commission', 'partner_revenue']:
        grid_data.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
    elif sort_by == 'created_at':
        grid_data.sort(key=lambda x: x.get('created_at', ''), reverse=reverse)
    elif sort_by == 'partner_name':
        grid_data.sort(key=lambda x: x.get('partner_name', '').lower(), reverse=reverse)
    elif sort_by == 'status':
        grid_data.sort(key=lambda x: x.get('status', '').lower(), reverse=reverse)
    
    # Sort partner summary by won deals
    partner_list = sorted(partner_summary.values(), key=lambda x: x['won_deals'], reverse=True)
    
    # Round summary values
    summary['total_deal_value'] = round(summary['total_deal_value'], 2)
    summary['total_vyapaar_commission'] = round(summary['total_vyapaar_commission'], 2)
    summary['total_partner_revenue'] = round(summary['total_partner_revenue'], 2)
    
    return {
        "summary": summary,
        "partner_summary": partner_list,
        "grid_data": grid_data,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "partner_id": partner_id,
            "category_id": category_id,
            "status_id": status_id
        },
        "sort": {
            "by": sort_by,
            "order": sort_order
        }
    }

@api_router.get("/reports/sales-associate/{associate_id}/detailed")
async def get_detailed_associate_report(
    associate_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Detailed Sales Associate Earnings Report with lifetime view"""
    if current_user['role'] not in [UserRole.SUPER_ADMIN.value, UserRole.SALES_ASSOCIATE.value]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user['role'] == UserRole.SALES_ASSOCIATE.value and current_user['id'] != associate_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    query = {"sales_associate_id": associate_id}
    if start_date:
        query['created_at'] = {"$gte": start_date}
    if end_date:
        if 'created_at' not in query:
            query['created_at'] = {}
        query['created_at']['$lte'] = end_date
    
    leads = await db.leads.find(query, {"_id": 0}).to_list(10000)
    
    # Get associate info
    associate = await db.users.find_one({"id": associate_id}, {"_id": 0, "password": 0})
    
    # Get statuses
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(100)
    status_map = {s['id']: s['name'].lower() for s in statuses}
    
    # Get users for partner names
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)
    user_map = {u['id']: u['name'] for u in users}
    
    # Aggregate data
    total_referrals = len(leads)
    converted = 0
    pending = 0
    lost = 0
    total_deal_value_influenced = 0
    total_vyapaar_revenue_influenced = 0
    total_earnings = 0
    period_breakdown = {}
    deals_list = []
    
    for lead in leads:
        status_name = status_map.get(lead.get('status_id', ''), '').lower()
        deal_value = lead.get('deal_value', 0)
        total_deal_value_influenced += deal_value
        
        # Period breakdown
        created_at = lead.get('created_at', '')[:10]
        if period == 'monthly':
            period_key = created_at[:7]
        elif period == 'quarterly':
            month = int(created_at[5:7]) if len(created_at) >= 7 else 1
            quarter = (month - 1) // 3 + 1
            period_key = f"{created_at[:4]}-Q{quarter}"
        elif period == 'yearly':
            period_key = created_at[:4]
        else:
            period_key = created_at[:7]
        
        if period_key not in period_breakdown:
            period_breakdown[period_key] = {"referrals": 0, "converted": 0, "earnings": 0}
        period_breakdown[period_key]['referrals'] += 1
        
        if 'won' in status_name:
            converted += 1
            period_breakdown[period_key]['converted'] += 1
            
            vyapaar_pct = lead.get('commission_override') or 15.0
            vyapaar_share = deal_value * (vyapaar_pct / 100)
            total_vyapaar_revenue_influenced += vyapaar_share
            
            sa_pct = lead.get('sales_associate_commission', 0) or 0
            earnings = vyapaar_share * (sa_pct / 100) if sa_pct else 0
            total_earnings += earnings
            period_breakdown[period_key]['earnings'] += earnings
            
            deals_list.append({
                "id": lead['id'],
                "title": lead['title'],
                "deal_value": deal_value,
                "vyapaar_share": round(vyapaar_share, 2),
                "commission_percentage": sa_pct,
                "earnings": round(earnings, 2),
                "partner": user_map.get(lead.get('selling_partner_id'), "Unknown"),
                "date": created_at,
                "status": "Won"
            })
        elif 'lost' in status_name:
            lost += 1
        else:
            pending += 1
            # Forecast earnings for pending deals
            vyapaar_pct = lead.get('commission_override') or 15.0
            vyapaar_share = deal_value * (vyapaar_pct / 100)
            sa_pct = lead.get('sales_associate_commission', 0) or 0
            potential_earnings = vyapaar_share * (sa_pct / 100) if sa_pct else 0
            
            if potential_earnings > 0:
                deals_list.append({
                    "id": lead['id'],
                    "title": lead['title'],
                    "deal_value": deal_value,
                    "vyapaar_share": round(vyapaar_share, 2),
                    "commission_percentage": sa_pct,
                    "earnings": round(potential_earnings, 2),
                    "partner": user_map.get(lead.get('selling_partner_id'), "Unknown"),
                    "date": created_at,
                    "status": "Pending (Forecasted)"
                })
    
    # Calculate forecasted earnings from open deals
    forecasted_earnings = sum(d['earnings'] for d in deals_list if d['status'] == "Pending (Forecasted)")
    
    return {
        "associate_info": {
            "id": associate_id,
            "name": associate['name'] if associate else "Unknown",
            "email": associate['email'] if associate else None
        },
        "summary": {
            "total_referrals": total_referrals,
            "converted_deals": converted,
            "pending_deals": pending,
            "lost_deals": lost,
            "conversion_rate": round(converted / total_referrals * 100, 2) if total_referrals > 0 else 0,
            "total_deal_value_influenced": round(total_deal_value_influenced, 2),
            "vyapaar_revenue_influenced": round(total_vyapaar_revenue_influenced, 2),
            "total_earnings": round(total_earnings, 2),
            "forecasted_earnings": round(forecasted_earnings, 2)
        },
        "lifetime_earnings": round(total_earnings, 2),
        "period_breakdown": sorted([{"period": k, **v} for k, v in period_breakdown.items()], key=lambda x: x['period']),
        "deals": deals_list
    }

@api_router.post("/leads/{lead_id}/lock-commission")
async def lock_deal_commission(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Lock commission values when deal is marked as Won"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can lock commissions")
    
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check if deal is won
    status = await db.lead_statuses.find_one({"id": lead.get('status_id')}, {"_id": 0})
    if not status or 'won' not in status['name'].lower():
        raise HTTPException(status_code=400, detail="Can only lock commission for Won deals")
    
    # Check if already locked
    if lead.get('locked_commission'):
        raise HTTPException(status_code=400, detail="Commission already locked for this deal")
    
    # Get partner company for base rate
    base_commission_pct = 15.0
    if lead.get('selling_partner_id'):
        partner = await db.users.find_one({"id": lead['selling_partner_id']}, {"_id": 0})
        if partner and partner.get('company_id'):
            company = await db.companies.find_one({"id": partner['company_id']}, {"_id": 0})
            if company:
                base_commission_pct = company.get('vyapaar_commission_percentage', 15.0)
    
    # Calculate locked values
    deal_value = lead.get('deal_value', 0)
    override_pct = lead.get('commission_override')
    final_pct = override_pct if override_pct is not None else base_commission_pct
    
    vyapaar_gross = deal_value * (final_pct / 100)
    selling_partner_revenue = deal_value - vyapaar_gross
    
    sa_pct = lead.get('sales_associate_commission', 0) or 0
    sa_commission = vyapaar_gross * (sa_pct / 100) if sa_pct else 0
    vyapaar_net = vyapaar_gross - sa_commission
    
    locked_commission = {
        "deal_value": deal_value,
        "vyapaar_base_percentage": base_commission_pct,
        "commission_override_percentage": override_pct,
        "final_vyapaar_percentage": final_pct,
        "selling_partner_revenue": round(selling_partner_revenue, 2),
        "vyapaar_gross_commission": round(vyapaar_gross, 2),
        "sales_associate_percentage": sa_pct if sa_pct else None,
        "sales_associate_commission": round(sa_commission, 2) if sa_commission else None,
        "vyapaar_net_earnings": round(vyapaar_net, 2),
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "locked_by": current_user['id']
    }
    
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {"locked_commission": locked_commission, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Commission locked successfully", "locked_commission": locked_commission}

# ==================== SEED DATA ====================

@api_router.post("/seed")
async def seed_data():
    """Seed initial master data"""
    
    # Check if already seeded
    existing = await db.lead_statuses.find_one({})
    if existing:
        return {"message": "Data already seeded"}
    
    # Seed Lead Statuses
    statuses = [
        {"id": str(uuid.uuid4()), "name": "Draft", "color": "#94A3B8", "order": 0, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "New", "color": "#4169E1", "order": 1, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Qualified", "color": "#10B981", "order": 2, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Proposal", "color": "#F59E0B", "order": 3, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Negotiation", "color": "#8B5CF6", "order": 4, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Won", "color": "#10B981", "order": 5, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Lost", "color": "#DC143C", "order": 6, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "On Hold", "color": "#64748B", "order": 7, "is_active": True}
    ]
    await db.lead_statuses.insert_many(statuses)
    
    # Seed Primary Categories
    primary_categories = [
        {"id": str(uuid.uuid4()), "name": "HR", "description": "Human Resources services", "is_active": True},
        {"id": str(uuid.uuid4()), "name": "IT", "description": "Information Technology services", "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Marketing", "description": "Marketing and advertising services", "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Finance", "description": "Financial services and consulting", "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Compliance", "description": "Legal and compliance services", "is_active": True}
    ]
    await db.primary_categories.insert_many(primary_categories)
    
    # Seed Secondary Categories
    hr_id = primary_categories[0]['id']
    it_id = primary_categories[1]['id']
    marketing_id = primary_categories[2]['id']
    finance_id = primary_categories[3]['id']
    compliance_id = primary_categories[4]['id']
    
    secondary_categories = [
        {"id": str(uuid.uuid4()), "name": "Recruitment", "primary_category_id": hr_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Training", "primary_category_id": hr_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Payroll", "primary_category_id": hr_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Software Development", "primary_category_id": it_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Cloud Services", "primary_category_id": it_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Cybersecurity", "primary_category_id": it_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Digital Marketing", "primary_category_id": marketing_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Brand Strategy", "primary_category_id": marketing_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Accounting", "primary_category_id": finance_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Tax Advisory", "primary_category_id": finance_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Legal Advisory", "primary_category_id": compliance_id, "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Audit Services", "primary_category_id": compliance_id, "is_active": True}
    ]
    await db.secondary_categories.insert_many(secondary_categories)
    
    # Seed Commission Templates
    commission_templates = [
        {"id": str(uuid.uuid4()), "name": "Standard", "vyapaar_percentage": 15.0, "description": "Standard commission rate", "is_active": True},
        {"id": str(uuid.uuid4()), "name": "Premium Partner", "vyapaar_percentage": 12.0, "description": "Reduced rate for premium partners", "is_active": True},
        {"id": str(uuid.uuid4()), "name": "High Value", "vyapaar_percentage": 10.0, "description": "For high value deals", "is_active": True}
    ]
    await db.commission_templates.insert_many(commission_templates)
    
    # Create default super admin
    admin_id = str(uuid.uuid4())
    admin_doc = {
        "id": admin_id,
        "email": "admin@vyapaarnetwork.com",
        "password": hash_password("admin123"),
        "name": "Super Admin",
        "role": UserRole.SUPER_ADMIN.value,
        "company_id": None,
        "phone": None,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(admin_doc)
    
    return {"message": "Seed data created successfully"}

# ==================== ROOT ====================

@api_router.get("/")
async def root():
    return {"message": "Vyapaar Network CRM API", "version": "1.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
