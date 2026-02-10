from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from enum import Enum
import csv
import io
import re

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'vyapaar-network-crm-secret-key-2025')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# SendGrid Configuration
SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@vyapaarnetwork.com')

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

class CompanyResponse(BaseModel):
    id: str
    name: str
    type: str
    vyapaar_commission_percentage: float
    address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    created_at: str
    is_active: bool

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

class FollowUpResponse(BaseModel):
    id: str
    scheduled_date: str
    notes: Optional[str] = None
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

class LeadResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None
    customer_company: Optional[str] = None
    selling_partner_id: Optional[str] = None
    selling_partner_name: Optional[str] = None
    sales_associate_id: Optional[str] = None
    sales_associate_name: Optional[str] = None
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
    created_by: str
    created_by_name: Optional[str] = None
    created_at: str
    updated_at: str

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
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    company_id = None
    company_name = None
    
    # Create company if needed
    if user_data.role in [UserRole.SELLING_PARTNER, UserRole.CUSTOMER] and user_data.company_name:
        company_id = str(uuid.uuid4())
        company_doc = {
            "id": company_id,
            "name": user_data.company_name,
            "type": "selling_partner" if user_data.role == UserRole.SELLING_PARTNER else "customer",
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

# ==================== USER ROUTES ====================

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

# ==================== COMPANY ROUTES ====================

@api_router.post("/companies", response_model=CompanyResponse)
async def create_company(company_data: CompanyCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can create companies")
    
    company_id = str(uuid.uuid4())
    company_doc = {
        "id": company_id,
        "name": company_data.name,
        "type": company_data.type,
        "vyapaar_commission_percentage": company_data.vyapaar_commission_percentage,
        "address": company_data.address,
        "contact_email": company_data.contact_email,
        "contact_phone": company_data.contact_phone,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True
    }
    
    await db.companies.insert_one(company_doc)
    
    return CompanyResponse(**{k: v for k, v in company_doc.items() if k != '_id'})

@api_router.get("/companies", response_model=List[CompanyResponse])
async def list_companies(type: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {"is_active": True}
    if type:
        query['type'] = type
    
    companies = await db.companies.find(query, {"_id": 0}).to_list(1000)
    return [CompanyResponse(**c) for c in companies]

@api_router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: str, current_user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse(**company)

@api_router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: str, company_data: CompanyCreate, current_user: dict = Depends(get_current_user)):
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can update companies")
    
    update_data = company_data.model_dump(exclude_unset=True)
    result = await db.companies.update_one({"id": company_id}, {"$set": update_data})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Company not found")
    
    company = await db.companies.find_one({"id": company_id}, {"_id": 0})
    return CompanyResponse(**company)

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

# ==================== LEAD ROUTES ====================

async def enrich_lead(lead: dict) -> LeadResponse:
    # Get related data
    selling_partner = None
    if lead.get('selling_partner_id'):
        selling_partner = await db.users.find_one({"id": lead['selling_partner_id']}, {"_id": 0})
    
    sales_associate = None
    if lead.get('sales_associate_id'):
        sales_associate = await db.users.find_one({"id": lead['sales_associate_id']}, {"_id": 0})
    
    primary_category = await db.primary_categories.find_one({"id": lead['primary_category_id']}, {"_id": 0})
    
    secondary_category = None
    if lead.get('secondary_category_id'):
        secondary_category = await db.secondary_categories.find_one({"id": lead['secondary_category_id']}, {"_id": 0})
    
    status = None
    if lead.get('status_id'):
        status = await db.lead_statuses.find_one({"id": lead['status_id']}, {"_id": 0})
    
    created_by_user = await db.users.find_one({"id": lead['created_by']}, {"_id": 0})
    
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
        created_by=lead['created_by'],
        created_by_name=created_by_user['name'] if created_by_user else None,
        created_at=lead['created_at'],
        updated_at=lead['updated_at']
    )

@api_router.post("/leads", response_model=LeadResponse)
async def create_lead(lead_data: LeadCreate, current_user: dict = Depends(get_current_user)):
    # Validate primary category
    primary = await db.primary_categories.find_one({"id": lead_data.primary_category_id}, {"_id": 0})
    if not primary:
        raise HTTPException(status_code=404, detail="Primary category not found")
    
    # Get default status if not provided
    status_id = lead_data.status_id
    if not status_id:
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
    return await enrich_lead(lead_doc)

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
    
    result = []
    for lead in leads:
        result.append(await enrich_lead(lead))
    
    return result

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
    
    await db.leads.update_one({"id": lead_id}, {"$set": update_data})
    
    updated_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
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
