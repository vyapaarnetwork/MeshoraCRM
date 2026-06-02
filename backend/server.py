from fastapi import FastAPI, APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File, Form, Request, Response
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
from datetime import datetime, timezone, timedelta, date
import jwt
import bcrypt
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client as TwilioClient
from enum import Enum
import csv
import io
import re
import json

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
    VYAPAAR_OPS = "vyapaar_ops"          # Phase 18: full access except user/company/category creation
    VYAPAAR_FINANCE = "vyapaar_finance"  # Phase 18: read everything + full commercials write access

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
    # Phase 30: sub-role inside a Customer / Selling-Partner company
    # (founder | sales | operations | finance). Ignored for vyapaar-side roles.
    company_role: Optional[str] = None
    # Phase 30: email notification opt-ins (dict of {notification_type: bool}).
    notification_preferences: Optional[Dict[str, bool]] = None

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
    subcategory_ids: Optional[List[str]] = None  # Inherited from company (selling partners)
    is_finance: bool = False  # Phase 2 commercials: can raise invoices / record payments
    is_delivery: bool = False  # Phase 2 commercials: can update milestone delivery status
    is_vyapaar_ops: bool = False  # Phase 17: Vyapaar Operations — full app access except user/company/category creation
    company_role: Optional[str] = None  # Phase 30: founder | sales | operations | finance
    notification_preferences: Optional[Dict[str, bool]] = None  # Phase 30

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Profile Update Models
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    notification_preferences: Optional[Dict[str, bool]] = None  # Phase 30: user-managed

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
    is_finance: bool = False
    is_delivery: bool = False
    is_vyapaar_ops: bool = False
    company_role: Optional[str] = None  # Phase 30
    notification_preferences: Optional[Dict[str, bool]] = None  # Phase 30

# Admin User Update Model
class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None  # Optional - only update if provided
    role: Optional[UserRole] = None
    company_id: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    is_finance: Optional[bool] = None
    is_delivery: Optional[bool] = None
    is_vyapaar_ops: Optional[bool] = None
    company_role: Optional[str] = None  # Phase 30: founder/sales/operations/finance
    notification_preferences: Optional[Dict[str, bool]] = None  # Phase 30

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
    # Commercials Phase 2.5
    COMMERCIAL_MILESTONE_DUE = "commercial_milestone_due"
    COMMERCIAL_INVOICE_OVERDUE = "commercial_invoice_overdue"
    COMMERCIAL_RENEWAL_WINDOW = "commercial_renewal_window"
    COMMERCIAL_BILLING_DUE = "commercial_billing_due"
    # Phase 1 (Revenue OS): collaboration mentions
    LEAD_MENTION = "lead_mention"
    # Phase 1.5: Task assignments
    TASK_ASSIGNED = "task_assigned"
    # Phase 2: Smart Notification rules
    RULE_LEAD_INACTIVE = "rule_lead_inactive"
    RULE_PROPOSAL_PENDING = "rule_proposal_pending"
    RULE_HIGH_VALUE_AT_RISK = "rule_high_value_at_risk"

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
    commercial_id: Optional[str] = None
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
    is_won: bool = False

class LeadStatusResponse(BaseModel):
    id: str
    name: str
    color: str
    order: int
    is_active: bool
    is_won: bool = False

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
    assignee_id: Optional[str] = None  # Phase 30: who is responsible for this follow-up
    reminder_minutes_before: Optional[int] = 120  # Phase 30: lead-time for the reminder

class FollowUpResponse(BaseModel):
    id: str
    scheduled_date: str
    notes: Optional[str] = None
    pending_with: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    reminder_minutes_before: Optional[int] = None
    is_completed: bool
    completed_at: Optional[str] = None
    completion_notes: Optional[str] = None
    created_at: str

class CommentCreate(BaseModel):
    content: str
    parent_comment_id: Optional[str] = None  # Phase 1: threaded comments
    is_public: bool = False  # Phase 27: visible inside the customer-facing Deal Room

class CommentResponse(BaseModel):
    id: str
    content: str
    user_id: str
    user_name: str
    user_role: str
    created_at: str
    parent_comment_id: Optional[str] = None
    is_public: bool = False

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
    status_is_won: bool = False
    follow_ups: List[FollowUpResponse] = []
    comments: List[CommentResponse] = []
    documents: List[DocumentResponse] = []
    assigned_partners: List[PartnerAssignment] = []  # All assigned partners (active, won, lost)
    active_partners_count: int = 0  # Count of currently active partners
    created_by: str
    created_by_name: Optional[str] = None
    created_at: str
    updated_at: str
    # Phase 27: Deal Room state
    deal_room_enabled: bool = False
    deal_room_opened_at: Optional[str] = None

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

# Phase 26: HttpOnly cookie helpers (JWT moved out of localStorage to mitigate XSS)
_AUTH_COOKIE_NAME = "access_token"
_AUTH_COOKIE_MAX_AGE = JWT_EXPIRATION_HOURS * 3600

def _set_auth_cookie(response: Response, token: str) -> None:
    """Set the JWT as an httpOnly cookie.
    SameSite=None + Secure is used so the cookie works across both same-origin (preview,
    where frontend & /api share the K8s ingress domain) AND cross-origin production
    setups (where the frontend custom domain — e.g. app.vyapaar.net — may differ from
    the backend domain). All requests are HTTPS so Secure is mandatory anyway, and the
    cookie is httpOnly to mitigate XSS. Cross-site cookie behaviour requires SameSite=None."""
    response.set_cookie(
        key=_AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=_AUTH_COOKIE_MAX_AGE,
        path="/",
    )

def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=_AUTH_COOKIE_NAME, path="/", samesite="none", secure=True)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
):
    # Phase 26: Read JWT from httpOnly cookie first (preferred), fall back to
    # Authorization Bearer header for legacy clients / API testing tools.
    token = request.cookies.get('access_token')
    if not token and credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user = await db.users.find_one({"id": payload['user_id']}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # Phase 18: Map Vyapaar Operations / Vyapaar Finance roles → existing flag system
    # so the rest of the codebase keeps working with `is_vyapaar_ops` / `is_finance` checks.
    if user.get('role') == UserRole.VYAPAAR_OPS.value:
        user['is_vyapaar_ops'] = True
    if user.get('role') == UserRole.VYAPAAR_FINANCE.value:
        user['is_finance'] = True
        user['is_vyapaar_ops'] = True         # grants read-everything access
        user['is_finance_only_role'] = True   # extra block: no lead/company/master writes
    # Phase 17: Vyapaar Operations users get full app access (same as super_admin)
    # except they cannot create users/companies/categories. We elevate their role
    # in-memory; the three creation endpoints have explicit blocks on the flag.
    if user.get('is_vyapaar_ops') and user.get('role') != UserRole.SUPER_ADMIN.value:
        user['original_role'] = user['role']
        user['role'] = UserRole.SUPER_ADMIN.value
    # Phase 18: Block VYAPAAR_FINANCE write access to non-commercials endpoints
    if user.get('is_finance_only_role') and request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        path = request.url.path
        # Allow writes only on commercials, notifications (mark-read), and self auth endpoints
        allowed_prefixes = ('/api/commercials', '/api/notifications', '/api/auth')
        if not any(path.startswith(p) for p in allowed_prefixes):
            raise HTTPException(
                status_code=403,
                detail="Vyapaar Finance role has read-only access to leads, companies, master data, and users."
            )
    return user

def block_finance_only_write(user: dict):
    """Phase 18: Explicit guard for routers/modules that bypass get_current_user request checks."""
    if user.get('is_finance_only_role'):
        raise HTTPException(
            status_code=403,
            detail="Vyapaar Finance role has read-only access outside the Commercials module."
        )

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
async def register(user_data: UserCreate, response: Response):
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
    _set_auth_cookie(response, token)
    
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
async def login(credentials: UserLogin, response: Response):
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
    _set_auth_cookie(response, token)
    
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
            is_finance=user.get('is_finance', False),
            is_delivery=user.get('is_delivery', False),
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
    
    # Phase 18: derive flags from the user's actual role so frontend can distinguish
    # ops vs finance vs super_admin properly (avoid synthetic elevation values).
    actual_role = current_user.get('original_role') or current_user['role']
    return UserResponse(
        id=current_user['id'],
        email=current_user['email'],
        name=current_user['name'],
        role=UserRole(actual_role),
        company_id=current_user.get('company_id'),
        company_name=company_name,
        phone=current_user.get('phone'),
        is_active=current_user.get('is_active', True),
        is_finance=current_user.get('is_finance', False) if actual_role != UserRole.VYAPAAR_FINANCE.value else True,
        is_delivery=current_user.get('is_delivery', False),
        is_vyapaar_ops=(actual_role == UserRole.VYAPAAR_OPS.value) or bool(
            current_user.get('is_vyapaar_ops', False) and actual_role != UserRole.VYAPAAR_FINANCE.value
        ),
        company_role=current_user.get('company_role'),
        notification_preferences=current_user.get('notification_preferences'),
        created_at=current_user['created_at']
    )

@api_router.post("/auth/logout")
async def logout(response: Response):
    """Phase 26: Clear the httpOnly auth cookie. Returns 200 regardless of auth state
    so the frontend can call this on any 'logout' click without needing a valid session."""
    _clear_auth_cookie(response)
    return {"ok": True}

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
        is_finance=updated_user.get('is_finance', False),
        is_delivery=updated_user.get('is_delivery', False),
        is_vyapaar_ops=updated_user.get('is_vyapaar_ops', False),
        company_role=updated_user.get('company_role'),
        notification_preferences=updated_user.get('notification_preferences'),
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

async def create_notification(user_id: str, notification_type: str, title: str, message: str, lead_id: str = None, data: dict = None, commercial_id: str = None):
    """Create a notification for a specific user.

    Phase 32: also dispatch an email via ZeptoMail when the recipient has the
    matching `notification_preferences[notification_type]` enabled. Email
    sending happens as a fire-and-forget asyncio task so the caller's request
    is never blocked by transactional email latency. Defaults to opt-IN: if the
    user hasn't set a preference for this type, we DO send (matches existing
    in-app notification behaviour)."""
    notification_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    notification_doc = {
        "id": notification_id,
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "lead_id": lead_id,
        "commercial_id": commercial_id,
        "data": data or {},
        "is_read": False,
        "created_at": now
    }
    
    await db.notifications.insert_one(notification_doc)

    # Phase 32 — dispatch email out-of-band
    try:
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1, "notification_preferences": 1, "is_active": 1})
        if user and user.get('is_active', True) and user.get('email'):
            prefs = user.get('notification_preferences') or {}
            # Opt-in by default: only skip if explicitly False
            if prefs.get(notification_type, True):
                from services import zeptomail as _zepto  # local import to avoid startup-time cycles
                ctx = {
                    "recipient_name": user.get('name') or '',
                    "title": title,
                    "message": message,
                    "lead_id": lead_id,
                    "commercial_id": commercial_id,
                    **(data or {}),
                }
                if lead_id:
                    ctx.setdefault("lead_url", f"https://app.vyapaar.net/leads/{lead_id}")
                if commercial_id:
                    ctx.setdefault("commercial_url", f"https://app.vyapaar.net/commercials/{commercial_id}")

                rendered = _zepto.render(notification_type, ctx) or _zepto.render("__generic__", {**ctx})
                if rendered is None:
                    # No renderer at all — synthesize a minimal generic body
                    rendered = {
                        "subject": f"[Meshora] {title}",
                        "html": f"<p>{message}</p>",
                        "text": message,
                    }
                # Fire-and-forget: never block notification persistence
                asyncio.create_task(_zepto.send_email(
                    to_address=user['email'],
                    to_name=user.get('name'),
                    subject=rendered["subject"],
                    html_body=rendered["html"],
                    text_body=rendered.get("text"),
                    db=db,
                    notification_type=notification_type,
                    user_id=user_id,
                    correlation_id=notification_id,
                ))
    except Exception as e:
        logger.warning("Email dispatch from create_notification failed (non-fatal): %s", e)

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
    if current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Vyapaar Operations cannot create users")
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
        "is_finance": user_data.is_finance,
        "is_delivery": user_data.is_delivery,
        "is_vyapaar_ops": user_data.is_vyapaar_ops,
        "company_role": user_data.company_role,
        "notification_preferences": user_data.notification_preferences,
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
        is_finance=user_data.is_finance,
        is_delivery=user_data.is_delivery,
        is_vyapaar_ops=user_data.is_vyapaar_ops,
        company_role=user_data.company_role,
        notification_preferences=user_data.notification_preferences,
        created_at=user_doc['created_at']
    )

# NOTE: These specific routes must be defined BEFORE /users/{user_id} to avoid route conflicts
@api_router.get("/users/selling-partners", response_model=List[UserResponse])
async def list_selling_partners(
    subcategory_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List selling partners. If subcategory_id is provided, only return partners
    whose company is mapped to that subcategory."""
    users = await db.users.find(
        {"role": UserRole.SELLING_PARTNER.value, "is_active": True},
        {"_id": 0, "password": 0}
    ).to_list(1000)

    # Bulk fetch companies for all selling partners (avoid N+1)
    company_ids = list({u['company_id'] for u in users if u.get('company_id')})
    companies_map = {}
    if company_ids:
        companies = await db.companies.find(
            {"id": {"$in": company_ids}},
            {"_id": 0}
        ).to_list(1000)
        companies_map = {c['id']: c for c in companies}

    result = []
    for user in users:
        company = companies_map.get(user.get('company_id')) if user.get('company_id') else None
        company_name = company['name'] if company else None
        subcategory_ids = company.get('subcategory_ids', []) if company else []

        # Filter by subcategory if requested
        if subcategory_id and subcategory_id not in (subcategory_ids or []):
            continue

        result.append(UserResponse(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            role=UserRole(user['role']),
            company_id=user.get('company_id'),
            company_name=company_name,
            phone=user.get('phone'),
            is_active=user.get('is_active', True),
            created_at=user['created_at'],
            subcategory_ids=subcategory_ids or None
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

@api_router.get("/users/referrers", response_model=List[UserResponse])
async def list_referrers(current_user: dict = Depends(get_current_user)):
    """Returns users who can be assigned as a lead referrer — both sales associates
    and selling partners. Used by the Edit Lead "Referred By" dropdown since a lead
    can be referred by either persona."""
    users = await db.users.find(
        {
            "role": {"$in": [UserRole.SALES_ASSOCIATE.value, UserRole.SELLING_PARTNER.value]},
            "is_active": {"$ne": False},
        },
        {"_id": 0, "password": 0},
    ).sort("name", 1).to_list(2000)

    company_ids = list({u['company_id'] for u in users if u.get('company_id')})
    company_map = {}
    if company_ids:
        companies = await db.companies.find({"id": {"$in": company_ids}}, {"_id": 0}).to_list(len(company_ids))
        company_map = {c['id']: c.get('name') for c in companies}

    result = []
    for user in users:
        result.append(UserResponse(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            role=UserRole(user['role']),
            company_id=user.get('company_id'),
            company_name=company_map.get(user.get('company_id')),
            phone=user.get('phone'),
            is_active=user.get('is_active', True),
            created_at=user['created_at'],
        ))
    return result

# Phase 30 — Notification preference catalog
NOTIFICATION_TYPE_CATALOG = [
    {"key": "lead_assigned", "label": "Lead Assigned", "description": "When a new lead is assigned to you"},
    {"key": "lead_status_changed", "label": "Lead Status Changed", "description": "When status of a lead you own changes"},
    {"key": "lead_won", "label": "Deal Won", "description": "When a deal in your pipeline is marked Won"},
    {"key": "follow_up_reminder", "label": "Follow-up Reminder", "description": "Reminder ahead of a scheduled follow-up"},
    {"key": "follow_up_overdue", "label": "Follow-up Overdue", "description": "When a follow-up has passed its scheduled date"},
    {"key": "milestone_due", "label": "Milestone Due", "description": "When a commercial milestone is approaching its due date"},
    {"key": "invoice_overdue", "label": "Invoice Overdue", "description": "When an invoice you raised is past due"},
    {"key": "payment_received", "label": "Payment Received", "description": "When a payment is recorded against your deal"},
    {"key": "commercial_created", "label": "Commercial Created", "description": "When commercials are set up for your deal"},
    {"key": "comment_mention", "label": "Mention in Comment", "description": "When someone @mentions you in a lead/deal comment"},
    {"key": "weekly_war_room_digest", "label": "Weekly War Room Digest", "description": "Monday summary of what's hot, blocked, and at risk"},
]

@api_router.get("/notifications/types")
async def list_notification_types(current_user: dict = Depends(get_current_user)):
    """Phase 30: Returns the catalog of notification types users can opt in/out of."""
    return NOTIFICATION_TYPE_CATALOG

@api_router.get("/users/assignable", response_model=List[UserResponse])
async def list_assignable_users(
    company_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Phase 30: Users who can be picked as a follow-up assignee.
    Defaults to the caller's company peers; super_admin can pass any company_id."""
    if current_user['role'] == UserRole.SUPER_ADMIN.value:
        target_company = company_id
    else:
        target_company = current_user.get('company_id')

    query: Dict[str, Any] = {"is_active": {"$ne": False}}
    if target_company:
        query["company_id"] = target_company
    elif current_user['role'] != UserRole.SUPER_ADMIN.value:
        # Caller has no company — return only themselves so the UI doesn't break.
        query["id"] = current_user['id']

    users = await db.users.find(query, {"_id": 0, "password": 0}).sort("name", 1).to_list(500)
    cids = list({u.get('company_id') for u in users if u.get('company_id')})
    cmap: Dict[str, str] = {}
    if cids:
        cmps = await db.companies.find({"id": {"$in": cids}}, {"_id": 0}).to_list(len(cids))
        cmap = {c['id']: c.get('name') for c in cmps}
    return [
        UserResponse(
            id=u['id'], email=u['email'], name=u['name'], role=UserRole(u['role']),
            company_id=u.get('company_id'), company_name=cmap.get(u.get('company_id')),
            phone=u.get('phone'), is_active=u.get('is_active', True),
            is_finance=u.get('is_finance', False), is_delivery=u.get('is_delivery', False),
            is_vyapaar_ops=u.get('is_vyapaar_ops', False),
            company_role=u.get('company_role'),
            notification_preferences=u.get('notification_preferences'),
            created_at=u['created_at'],
        )
        for u in users
    ]

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
        is_finance=user.get('is_finance', False),
        is_delivery=user.get('is_delivery', False),
        is_vyapaar_ops=user.get('is_vyapaar_ops', False),
        company_role=user.get('company_role'),
        notification_preferences=user.get('notification_preferences'),
        created_at=user['created_at']
    )

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user_data: AdminUserUpdate, current_user: dict = Depends(get_current_user)):
    """Admin updates a user"""
    if current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Vyapaar Operations cannot edit users")
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
        is_finance=updated_user.get('is_finance', False),
        is_delivery=updated_user.get('is_delivery', False),
        is_vyapaar_ops=updated_user.get('is_vyapaar_ops', False),
        company_role=updated_user.get('company_role'),
        notification_preferences=updated_user.get('notification_preferences'),
        created_at=updated_user['created_at']
    )

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Admin deletes a user"""
    if current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Vyapaar Operations cannot delete users")
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
            is_finance=user.get('is_finance', False),
            is_delivery=user.get('is_delivery', False),
            is_vyapaar_ops=user.get('is_vyapaar_ops', False),
            company_role=user.get('company_role'),
            notification_preferences=user.get('notification_preferences'),
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
    if current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Vyapaar Operations cannot create companies")
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
    
    # Create default user for customer or selling-partner companies
    if company_data.type in ("customer", "selling_partner") and company_data.default_user_email and company_data.default_user_name:
        # Check if email already exists
        existing_user = await db.users.find_one({"email": company_data.default_user_email})
        if existing_user:
            raise HTTPException(status_code=400, detail=f"User email {company_data.default_user_email} already exists")
        
        default_role = (UserRole.SELLING_PARTNER if company_data.type == "selling_partner" else UserRole.CUSTOMER).value
        default_pwd = company_data.default_user_password or (
            "partner123" if company_data.type == "selling_partner" else "customer123"
        )
        user_id = str(uuid.uuid4())
        user_doc = {
            "id": user_id,
            "email": company_data.default_user_email,
            "password": hash_password(default_pwd),
            "name": company_data.default_user_name,
            "role": default_role,
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

# ==================== PARTNER ↔ SUB-CATEGORY MAPPING ====================

class PartnerSubcategoryToggle(BaseModel):
    company_id: str
    subcategory_id: str
    mapped: bool

@api_router.post("/master/partner-subcategory-toggle")
async def toggle_partner_subcategory(
    payload: PartnerSubcategoryToggle,
    current_user: dict = Depends(get_current_user)
):
    """Atomically add or remove a single subcategory_id from a selling-partner
    company's subcategory_ids list. Admin only."""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can modify partner mappings")

    company = await db.companies.find_one({"id": payload.company_id}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.get('type') != 'selling_partner':
        raise HTTPException(status_code=400, detail="Only selling-partner companies can be mapped to sub-categories")

    subcat = await db.secondary_categories.find_one({"id": payload.subcategory_id}, {"_id": 0})
    if not subcat:
        raise HTTPException(status_code=404, detail="Sub-category not found")

    if payload.mapped:
        await db.companies.update_one(
            {"id": payload.company_id},
            {"$addToSet": {"subcategory_ids": payload.subcategory_id}}
        )
    else:
        await db.companies.update_one(
            {"id": payload.company_id},
            {"$pull": {"subcategory_ids": payload.subcategory_id}}
        )

    updated = await db.companies.find_one({"id": payload.company_id}, {"_id": 0})
    return {
        "company_id": payload.company_id,
        "subcategory_id": payload.subcategory_id,
        "mapped": payload.mapped,
        "subcategory_ids": updated.get('subcategory_ids', [])
    }

@api_router.get("/master/partner-mappings")
async def list_partner_mappings(current_user: dict = Depends(get_current_user)):
    """Return all selling-partner companies with their current subcategory_ids and
    the count of active selling-partner users. Used by the Partner Mappings admin page."""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can view partner mappings")

    companies = await db.companies.find(
        {"type": "selling_partner", "is_active": True},
        {"_id": 0, "id": 1, "name": 1, "subcategory_ids": 1}
    ).to_list(1000)

    # Bulk count active SP users per company (avoid N+1)
    company_ids = [c['id'] for c in companies]
    user_counts = {}
    if company_ids:
        pipeline = [
            {"$match": {
                "company_id": {"$in": company_ids},
                "role": UserRole.SELLING_PARTNER.value,
                "is_active": True
            }},
            {"$group": {"_id": "$company_id", "count": {"$sum": 1}}}
        ]
        async for row in db.users.aggregate(pipeline):
            user_counts[row['_id']] = row['count']

    return [
        {
            "id": c['id'],
            "name": c['name'],
            "subcategory_ids": c.get('subcategory_ids') or [],
            "active_user_count": user_counts.get(c['id'], 0)
        }
        for c in companies
    ]

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
        "is_active": True,
        "is_won": status_data.is_won
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
    if current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Vyapaar Operations cannot create categories")
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
    if current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Vyapaar Operations cannot create categories")
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

async def _enrich_followups(followups: List[dict], users_map: Optional[Dict[str, Any]] = None) -> List[FollowUpResponse]:
    """Phase 30: turn raw follow-up dicts into FollowUpResponse with assignee_name resolved.
    `users_map` may be {id: name_string} OR {id: full_user_dict} — both are accepted."""
    if not followups:
        return []

    def _name_from(entry):
        if entry is None:
            return None
        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            return entry.get('name')
        return None

    if users_map is None:
        # Lazy-load only the assignee_ids we actually need
        assignee_ids = list({f.get('assignee_id') for f in followups if f.get('assignee_id')})
        users_map = {}
        if assignee_ids:
            users = await db.users.find({"id": {"$in": assignee_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(assignee_ids))
            users_map = {u['id']: u.get('name') for u in users}
    out = []
    for f in followups:
        aid = f.get('assignee_id')
        out.append(FollowUpResponse(
            id=f['id'],
            scheduled_date=f['scheduled_date'],
            notes=f.get('notes'),
            pending_with=f.get('pending_with'),
            assignee_id=aid,
            assignee_name=_name_from(users_map.get(aid)) if aid else None,
            reminder_minutes_before=f.get('reminder_minutes_before'),
            is_completed=bool(f.get('is_completed', False)),
            completed_at=f.get('completed_at'),
            completion_notes=f.get('completion_notes'),
            created_at=f['created_at'],
        ))
    return out

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
        status_is_won=bool(status.get('is_won')) if status else False,
        follow_ups=await _enrich_followups(lead.get('follow_ups', [])),
        comments=[CommentResponse(**c) for c in lead.get('comments', [])],
        documents=doc_responses,
        assigned_partners=[PartnerAssignment(**p) for p in lead.get('assigned_partners', [])],
        active_partners_count=len([p for p in lead.get('assigned_partners', []) if p.get('status') == 'active']),
        created_by=lead['created_by'],
        created_by_name=created_by_user['name'] if created_by_user else None,
        created_at=lead['created_at'],
        updated_at=lead['updated_at'],
        deal_room_enabled=bool(lead.get('deal_room_enabled', False)),
        deal_room_opened_at=lead.get('deal_room_opened_at'),
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
            status_is_won=bool(status.get('is_won')) if status else False,
            follow_ups=await _enrich_followups(lead.get('follow_ups', []), users_map=users_map),
            comments=[CommentResponse(**c) for c in lead.get('comments', [])],
            documents=doc_responses,
            assigned_partners=[PartnerAssignment(**p) for p in lead.get('assigned_partners', [])],
            active_partners_count=len([p for p in lead.get('assigned_partners', []) if p.get('status') == 'active']),
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

@api_router.get("/leads/health-summary")
async def list_leads_health_summary(
    status_id: Optional[str] = None,
    primary_category_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Phase 1 (Revenue OS): Batch-compute lead health for the current user's visible leads.

    Returns: {results: [{id, health: {score, band, days_inactive}, next_action: {label, urgency}}]}
    Heuristics are computed in-process; no extra DB roundtrips per lead.
    """
    query = {}
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        query['selling_partner_id'] = current_user['id']
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        query['sales_associate_id'] = current_user['id']
    elif current_user['role'] == UserRole.CUSTOMER.value:
        query['created_by'] = current_user['id']
    if status_id:
        query['status_id'] = status_id
    if primary_category_id:
        query['primary_category_id'] = primary_category_id

    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    won_map = {s['id']: bool(s.get('is_won')) for s in statuses}

    leads = await db.leads.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    results = []
    for lead in leads:
        lead['active_partners_count'] = len([p for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active'])
        lead['status_is_won'] = won_map.get(lead.get('status_id'), False)
        health = compute_lead_health(lead)
        next_action = compute_next_action(lead, health)
        results.append({
            "id": lead['id'],
            "health": {
                "score": health['score'],
                "band": health['band'],
                "days_inactive": health.get('days_inactive'),
            },
            "next_action": {
                "label": next_action['label'],
                "urgency": next_action['urgency'],
            },
        })
    return {"results": results}

@api_router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: str, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Access control
    is_email_match_only_customer = False
    if current_user['role'] == UserRole.SELLING_PARTNER.value and lead.get('selling_partner_id') != current_user['id']:
        # Also allow if they're in assigned_partners (multi-partner)
        if not any(p.get('partner_id') == current_user['id'] for p in (lead.get('assigned_partners') or [])):
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value and lead.get('sales_associate_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Access denied")
    elif current_user['role'] == UserRole.CUSTOMER.value:
        # Phase 27: also allow the customer whose email matches lead.customer_email (Deal Room access)
        is_creator = lead.get('created_by') == current_user['id']
        is_email_match = lead.get('customer_email') and lead.get('customer_email').lower() == (current_user.get('email') or '').lower()
        if not (is_creator or is_email_match):
            raise HTTPException(status_code=403, detail="Access denied")
        # If access is via email match (not creator), redact internal fields
        is_email_match_only_customer = is_email_match and not is_creator

    enriched = await enrich_lead(lead)
    if is_email_match_only_customer:
        # Phase 27: customer who only matches via email should not see internal commercial details
        enriched.description = None
        enriched.deal_value = 0
        enriched.commission_override = None
        enriched.sales_associate_commission = None
        enriched.commission_breakdown = None
        # Strip internal comments (only public ones survive)
        enriched.comments = [c for c in enriched.comments if getattr(c, 'is_public', False)]
        # Strip referrer / sales associate info
        enriched.referred_by_partner_id = None
        enriched.referred_by_partner_name = None
        enriched.referred_by_associate_id = None
        enriched.referred_by_associate_name = None
        enriched.sales_associate_id = None
        enriched.sales_associate_name = None
    return enriched

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
    
    # Track partner in assigned_partners when selling_partner_id changes
    if 'selling_partner_id' in update_data and new_partner_id and new_partner_id != old_partner_id:
        assigned_partners = lead.get('assigned_partners', [])
        
        # Check if this partner is already in assigned_partners
        existing = next((p for p in assigned_partners if p.get('partner_id') == new_partner_id), None)
        
        if not existing:
            # Add new partner to assigned_partners
            new_partner = await db.users.find_one({"id": new_partner_id}, {"_id": 0})
            assigned_partners.append({
                "partner_id": new_partner_id,
                "partner_name": new_partner['name'] if new_partner else None,
                "assigned_at": now,
                "assigned_by": current_user['id'],
                "assigned_by_name": current_user['name'],
                "status": "active",
                "won_at": None,
                "lost_at": None,
                "notes": f"Assigned by {current_user['name']}"
            })
            update_data['assigned_partners'] = assigned_partners
    
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

# Multi-Partner Assignment Endpoints
@api_router.post("/leads/{lead_id}/assign-partner", response_model=LeadResponse)
async def assign_additional_partner(lead_id: str, request: AssignPartnerRequest, current_user: dict = Depends(get_current_user)):
    """Assign an additional partner to a lead (admin only)"""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can assign partners")
    
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Verify partner exists and is a selling partner
    partner = await db.users.find_one({"id": request.partner_id, "role": UserRole.SELLING_PARTNER.value}, {"_id": 0})
    if not partner:
        raise HTTPException(status_code=404, detail="Selling partner not found")
    
    assigned_partners = lead.get('assigned_partners', [])
    
    # Check if partner is already assigned
    existing = next((p for p in assigned_partners if p.get('partner_id') == request.partner_id), None)
    if existing:
        if existing.get('status') == 'active':
            raise HTTPException(status_code=400, detail="Partner is already assigned to this lead")
        # If partner was previously lost, reactivate them
        existing['status'] = 'active'
        existing['lost_at'] = None
        existing['notes'] = f"Re-assigned by {current_user['name']}"
    else:
        now = datetime.now(timezone.utc).isoformat()
        assigned_partners.append({
            "partner_id": request.partner_id,
            "partner_name": partner['name'],
            "assigned_at": now,
            "assigned_by": current_user['id'],
            "assigned_by_name": current_user['name'],
            "status": "active",
            "won_at": None,
            "lost_at": None,
            "notes": request.notes or f"Assigned by {current_user['name']}"
        })
    
    # Update lead
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {
            "assigned_partners": assigned_partners,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Create notification for the partner
    await create_notification_for_user(
        request.partner_id,
        notification_type="lead_assigned",
        title="New Lead Assigned",
        message=f"You have been assigned to lead: {lead['title']}",
        lead_id=lead_id
    )
    
    # Send SMS
    await send_lead_assignment_sms(request.partner_id, lead['title'], lead['customer_name'])
    
    updated_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return await enrich_lead(updated_lead)

@api_router.post("/leads/{lead_id}/mark-partner-won", response_model=LeadResponse)
async def mark_partner_won(lead_id: str, request: MarkPartnerWonRequest, current_user: dict = Depends(get_current_user)):
    """Mark a partner as the winner of the deal (admin only). Other partners are marked as lost."""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can mark partner as won")
    
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    assigned_partners = lead.get('assigned_partners', [])
    if not assigned_partners:
        raise HTTPException(status_code=400, detail="No partners assigned to this lead")
    
    # Find the winning partner
    winner = next((p for p in assigned_partners if p.get('partner_id') == request.partner_id), None)
    if not winner:
        raise HTTPException(status_code=400, detail="Partner is not assigned to this lead")
    
    if winner.get('status') != 'active':
        raise HTTPException(status_code=400, detail="Partner is not active on this lead")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Mark the winner and lose others
    for partner in assigned_partners:
        if partner['partner_id'] == request.partner_id:
            partner['status'] = 'won'
            partner['won_at'] = now
            partner['notes'] = request.notes or f"Won the deal"
        elif partner['status'] == 'active':
            partner['status'] = 'lost'
            partner['lost_at'] = now
            partner['notes'] = f"Lost to another partner"
    
    # Update lead with winning partner as the selling_partner_id
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {
            "selling_partner_id": request.partner_id,
            "assigned_partners": assigned_partners,
            "updated_at": now
        }}
    )
    
    # Notify the winning partner
    await create_notification_for_user(
        request.partner_id,
        notification_type="lead_won",
        title="Congratulations! You Won the Deal",
        message=f"You have won the deal for lead: {lead['title']}",
        lead_id=lead_id
    )
    
    updated_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return await enrich_lead(updated_lead)

@api_router.post("/leads/{lead_id}/remove-partner", response_model=LeadResponse)
async def remove_partner_from_lead(lead_id: str, request: AssignPartnerRequest, current_user: dict = Depends(get_current_user)):
    """Remove a partner from a lead (mark as lost). Admin only."""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can remove partners")
    
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    assigned_partners = lead.get('assigned_partners', [])
    
    # Find the partner to remove
    partner_assignment = next((p for p in assigned_partners if p.get('partner_id') == request.partner_id), None)
    if not partner_assignment:
        raise HTTPException(status_code=400, detail="Partner is not assigned to this lead")
    
    if partner_assignment.get('status') != 'active':
        raise HTTPException(status_code=400, detail="Partner is not active on this lead")
    
    now = datetime.now(timezone.utc).isoformat()
    partner_assignment['status'] = 'lost'
    partner_assignment['lost_at'] = now
    partner_assignment['notes'] = request.notes or f"Removed by {current_user['name']}"
    
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {
            "assigned_partners": assigned_partners,
            "updated_at": now
        }}
    )
    
    updated_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return await enrich_lead(updated_lead)

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
        "assignee_id": followup_data.assignee_id,  # Phase 30
        "reminder_minutes_before": followup_data.reminder_minutes_before or 120,  # Phase 30
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
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parent_comment_id": comment_data.parent_comment_id,
        "is_public": bool(comment_data.is_public),
    }
    
    await db.leads.update_one(
        {"id": lead_id},
        {
            "$push": {"comments": comment},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )

    # Phase 1: parse @mentions and notify mentioned users
    try:
        await _notify_mentions(comment_data.content, lead_id, lead.get('title', ''), current_user)
    except Exception as e:
        logger.warning(f"@mention notification failed: {e}")

    updated_lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return await enrich_lead(updated_lead)

# ==================== PHASE 1: ACTIVITY TIMELINE, HEALTH SCORE, NEXT ACTION, @MENTIONS ====================

def _parse_mentions(content: str) -> List[str]:
    """Extract @mentioned usernames from comment content. Returns lowercased name fragments."""
    return [m.lower() for m in re.findall(r'@([a-zA-Z][a-zA-Z0-9_.\-]{1,40})', content or '')]

async def _notify_mentions(content: str, lead_id: str, lead_title: str, author: dict):
    """Resolve @mentions in a comment and emit in-app notifications to matched users."""
    mentions = _parse_mentions(content)
    if not mentions:
        return
    # Match by case-insensitive name OR email-local-part. Limit to active users.
    notified_user_ids = set()
    for token in mentions:
        if not token:
            continue
        cursor = db.users.find({
            "is_active": True,
            "$or": [
                {"name": {"$regex": f"^{re.escape(token)}", "$options": "i"}},
                {"email": {"$regex": f"^{re.escape(token)}@", "$options": "i"}},
            ]
        }, {"_id": 0})
        async for u in cursor:
            uid = u.get('id')
            if not uid or uid == author.get('id') or uid in notified_user_ids:
                continue
            notified_user_ids.add(uid)
            try:
                await create_notification(
                    user_id=uid,
                    notification_type="lead_mention",
                    title=f"{author.get('name', 'Someone')} mentioned you",
                    message=f"On lead \"{lead_title}\": {content[:140]}",
                    lead_id=lead_id,
                    data={"author_id": author.get('id'), "author_name": author.get('name')}
                )
            except Exception as e:
                logger.warning(f"Failed to send mention notification to {uid}: {e}")

def _days_since(iso_string: Optional[str]) -> Optional[float]:
    if not iso_string:
        return None
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    except Exception:
        return None

def compute_lead_health(lead: dict) -> Dict[str, Any]:
    """Heuristic Lead Health Score → returns {score: 0-100, band: hot/warm/cold/at_risk, factors: [...]}.

    Factors weighted:
      - Recent activity (40 pts): days since last comment/follow-up/status change
      - Follow-up completion rate (20 pts)
      - Stage progression (20 pts): does the lead have a status set + is it 'won'/'lost' or progressing?
      - Deal value tier (10 pts): bigger deals get priority weight
      - Created-by recency (10 pts): newer leads start neutral
    """
    factors = []
    score = 50  # neutral starting point

    # Most recent activity timestamp
    last_activity_times = [lead.get('updated_at'), lead.get('created_at')]
    for c in lead.get('comments', []) or []:
        last_activity_times.append(c.get('created_at'))
    for f in lead.get('follow_ups', []) or []:
        last_activity_times.append(f.get('created_at'))
        if f.get('completed_at'):
            last_activity_times.append(f.get('completed_at'))
    last_activity_times = [t for t in last_activity_times if t]
    days_inactive = None
    if last_activity_times:
        days_inactive = min([_days_since(t) for t in last_activity_times if _days_since(t) is not None] or [None])

    if days_inactive is None:
        factors.append({"name": "Activity", "impact": 0, "detail": "No activity data"})
    elif days_inactive <= 2:
        score += 25; factors.append({"name": "Recent activity", "impact": +25, "detail": f"Last touched {days_inactive:.0f}d ago"})
    elif days_inactive <= 7:
        score += 10; factors.append({"name": "Some activity", "impact": +10, "detail": f"Last touched {days_inactive:.0f}d ago"})
    elif days_inactive <= 21:
        score -= 10; factors.append({"name": "Slowing down", "impact": -10, "detail": f"No activity for {days_inactive:.0f}d"})
    else:
        score -= 25; factors.append({"name": "Stale", "impact": -25, "detail": f"No activity for {days_inactive:.0f}d"})

    # Follow-up completion
    follow_ups = lead.get('follow_ups', []) or []
    overdue = 0  # Phase 29 fix: initialize outside the if so it's always present in the return dict.
    if follow_ups:
        completed = sum(1 for f in follow_ups if f.get('is_completed'))
        rate = completed / max(len(follow_ups), 1)
        if rate >= 0.7:
            score += 10; factors.append({"name": "Strong follow-through", "impact": +10, "detail": f"{int(rate*100)}% follow-ups completed"})
        elif rate <= 0.3:
            score -= 10; factors.append({"name": "Weak follow-through", "impact": -10, "detail": f"{int(rate*100)}% follow-ups completed"})

        # Overdue follow-ups
        today = datetime.now(timezone.utc).date()
        for f in follow_ups:
            if not f.get('is_completed') and f.get('scheduled_date'):
                try:
                    if datetime.fromisoformat(f['scheduled_date']).date() < today:
                        overdue += 1
                except Exception:
                    pass
        if overdue:
            score -= min(15, overdue * 5)
            factors.append({"name": "Overdue follow-ups", "impact": -min(15, overdue * 5), "detail": f"{overdue} overdue"})

    # Deal value priority
    deal_value = float(lead.get('deal_value') or 0)
    if deal_value >= 1_000_000:
        score += 10; factors.append({"name": "Large deal", "impact": +10, "detail": "Deal ≥ ₹10L"})
    elif deal_value >= 100_000:
        score += 5; factors.append({"name": "Mid-size deal", "impact": +5, "detail": "Deal ≥ ₹1L"})

    # Cap and band
    score = max(0, min(100, int(score)))
    if score >= 75:
        band = "hot"
    elif score >= 55:
        band = "warm"
    elif score >= 35:
        band = "cold"
    else:
        band = "at_risk"

    return {
        "score": score,
        "band": band,
        "days_inactive": round(days_inactive, 1) if days_inactive is not None else None,
        "overdue_count": overdue,  # Phase 29 fix: expose for War Room follow-up-pending classifier + card payload
        "factors": factors,
    }

def compute_next_action(lead: dict, health: Dict[str, Any]) -> Dict[str, Any]:
    """Rules-engine next-action recommendation. Returns {label, reason, urgency, action_type}."""
    today = datetime.now(timezone.utc).date()
    follow_ups = lead.get('follow_ups', []) or []

    # 1. Overdue follow-ups beat everything
    for f in follow_ups:
        if not f.get('is_completed') and f.get('scheduled_date'):
            try:
                d = datetime.fromisoformat(f['scheduled_date']).date()
                if d < today:
                    return {
                        "label": "Complete overdue follow-up",
                        "reason": f"Scheduled for {f['scheduled_date']} — already past due",
                        "urgency": "critical",
                        "action_type": "complete_followup",
                        "ref_id": f.get('id'),
                    }
            except Exception:
                pass

    # 2. Won status but no commercial set up
    if lead.get('status_is_won'):
        return {
            "label": "Set up commercials",
            "reason": "Lead marked Won — configure project milestones or recurring contract",
            "urgency": "high",
            "action_type": "setup_commercials",
        }

    # 3. No follow-up scheduled at all
    if not any(not f.get('is_completed') for f in follow_ups):
        return {
            "label": "Schedule next follow-up",
            "reason": "No pending follow-ups on this lead",
            "urgency": "high" if health['band'] in ("cold", "at_risk") else "medium",
            "action_type": "schedule_followup",
        }

    # 4. No partner assigned
    if not lead.get('active_partners_count') and not lead.get('selling_partner_id'):
        return {
            "label": "Assign a selling partner",
            "reason": "Lead has no active partner working on it",
            "urgency": "high",
            "action_type": "assign_partner",
        }

    # 5. Health is critical
    if health['band'] == "at_risk":
        return {
            "label": "Re-engage stakeholder",
            "reason": f"Lead has gone quiet ({health.get('days_inactive')}d). Reach out to the customer.",
            "urgency": "high",
            "action_type": "reengage",
        }

    # 6. Default — touch base
    return {
        "label": "Touch base with customer",
        "reason": "Keep momentum by checking in",
        "urgency": "low",
        "action_type": "touch_base",
    }

@api_router.get("/leads/{lead_id}/health")
async def get_lead_health(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Return health score + next action for a lead."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    # also pull active_partners_count from doc
    lead['active_partners_count'] = len([p for p in lead.get('assigned_partners', []) if p.get('status') == 'active'])
    # is_won flag
    status_is_won = False
    if lead.get('status_id'):
        st = await db.lead_statuses.find_one({"id": lead['status_id']}, {"_id": 0})
        status_is_won = bool(st and st.get('is_won'))
    lead['status_is_won'] = status_is_won

    health = compute_lead_health(lead)
    next_action = compute_next_action(lead, health)
    return {"health": health, "next_action": next_action}

@api_router.get("/leads/{lead_id}/activity")
async def get_lead_activity(lead_id: str, current_user: dict = Depends(get_current_user)):
    """Unified chronological activity timeline aggregated from:
    - Lead creation
    - Status changes (inferred from updated_at + status_name)
    - Comments
    - Follow-ups (scheduled + completed)
    - Partner assignments (active/won/lost)
    - Commercial activity (if linked)
    """
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    events: List[Dict[str, Any]] = []

    # Lead creation
    creator = await db.users.find_one({"id": lead.get('created_by')}, {"_id": 0})
    events.append({
        "id": f"create-{lead['id']}",
        "type": "lead_created",
        "title": "Lead created",
        "description": lead.get('title', ''),
        "user_name": (creator or {}).get('name', 'Unknown'),
        "user_id": lead.get('created_by'),
        "timestamp": lead.get('created_at'),
        "icon": "Sparkles",
    })

    # Comments
    for c in lead.get('comments', []) or []:
        events.append({
            "id": f"comment-{c.get('id')}",
            "type": "comment",
            "title": f"Comment by {c.get('user_name')}",
            "description": c.get('content', ''),
            "user_name": c.get('user_name'),
            "user_id": c.get('user_id'),
            "user_role": c.get('user_role'),
            "timestamp": c.get('created_at'),
            "icon": "MessageSquare",
        })

    # Follow-ups: scheduled
    for f in lead.get('follow_ups', []) or []:
        events.append({
            "id": f"followup-create-{f.get('id')}",
            "type": "followup_scheduled",
            "title": f"Follow-up scheduled for {f.get('scheduled_date')}",
            "description": f.get('notes') or '',
            "user_name": None,
            "timestamp": f.get('created_at'),
            "icon": "Calendar",
            "metadata": {"pending_with": f.get('pending_with')},
        })
        if f.get('is_completed') and f.get('completed_at'):
            events.append({
                "id": f"followup-complete-{f.get('id')}",
                "type": "followup_completed",
                "title": "Follow-up completed",
                "description": f.get('completion_notes') or '',
                "timestamp": f.get('completed_at'),
                "icon": "CheckCircle",
            })

    # Partner assignments
    for p in lead.get('assigned_partners', []) or []:
        events.append({
            "id": f"partner-assigned-{p.get('partner_id')}-{p.get('assigned_at', '')}",
            "type": "partner_assigned",
            "title": f"Partner {p.get('partner_name') or 'Unknown'} assigned",
            "description": p.get('notes') or '',
            "user_name": p.get('assigned_by_name'),
            "timestamp": p.get('assigned_at'),
            "icon": "UserPlus",
        })
        if p.get('won_at'):
            events.append({
                "id": f"partner-won-{p.get('partner_id')}",
                "type": "partner_won",
                "title": f"{p.get('partner_name')} marked as winner",
                "timestamp": p.get('won_at'),
                "icon": "Trophy",
            })
        if p.get('lost_at'):
            events.append({
                "id": f"partner-lost-{p.get('partner_id')}",
                "type": "partner_lost",
                "title": f"{p.get('partner_name')} marked as lost",
                "timestamp": p.get('lost_at'),
                "icon": "UserMinus",
            })

    # Commercial activity (if linked)
    commercial = await db.commercials.find_one({"lead_id": lead_id}, {"_id": 0})
    if commercial:
        for a in (commercial.get('activity') or [])[-50:]:  # last 50 events
            events.append({
                "id": f"commercial-{a.get('id', uuid.uuid4())}",
                "type": f"commercial_{a.get('event_type', 'update')}",
                "title": a.get('description') or a.get('event_type', 'Commercial update'),
                "description": _json_dumps_safe(a.get('metadata')),
                "user_name": a.get('user_name'),
                "timestamp": a.get('timestamp') or a.get('created_at'),
                "icon": "Briefcase",
            })

    # Sort reverse-chronological, filter out events with no timestamp
    events = [e for e in events if e.get('timestamp')]
    events.sort(key=lambda e: e['timestamp'], reverse=True)

    return {"activities": events, "count": len(events)}

def _json_dumps_safe(obj):
    """Stringify metadata for activity descriptions; returns '' for None/empty."""
    if not obj:
        return ''
    try:
        import json as _j
        return _j.dumps(obj, default=str)[:200]
    except Exception:
        return str(obj)[:200]

# --- Smart follow-ups: snooze + recurrence support ---

class FollowUpSnoozeRequest(BaseModel):
    new_scheduled_date: str

@api_router.patch("/leads/{lead_id}/follow-ups/{followup_id}/snooze", response_model=LeadResponse)
async def snooze_follow_up(
    lead_id: str,
    followup_id: str,
    body: FollowUpSnoozeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Reschedule a pending follow-up to a new date (snooze)."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    follow_ups = lead.get('follow_ups', [])
    found = False
    for fu in follow_ups:
        if fu['id'] == followup_id:
            if fu.get('is_completed'):
                raise HTTPException(status_code=400, detail="Cannot snooze a completed follow-up")
            fu['scheduled_date'] = body.new_scheduled_date
            fu['snoozed_at'] = datetime.now(timezone.utc).isoformat()
            fu['snoozed_by'] = current_user['id']
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {"follow_ups": follow_ups, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    updated = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    return await enrich_lead(updated)

# ==================== PHASE 2: AI MEETING SUMMARIES ====================

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

class MeetingSummaryRequest(BaseModel):
    raw_notes: str
    meeting_date: Optional[str] = None  # ISO date
    auto_create_tasks: bool = True  # auto-convert action items into Tasks

@api_router.post("/leads/{lead_id}/ai/meeting-summary")
async def ai_meeting_summary(
    lead_id: str,
    body: MeetingSummaryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Convert raw meeting notes / call transcript into structured intelligence using Gemini 3 Pro.
    Stores the summary as a special-typed comment on the lead, posts a structured 'meeting_summary'
    activity event, and optionally creates Tasks from extracted action items.
    """
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=503, detail="LLM key not configured")

    if not (body.raw_notes or '').strip():
        raise HTTPException(status_code=400, detail="raw_notes is required")
    if len(body.raw_notes) > 25000:
        raise HTTPException(status_code=400, detail="raw_notes too long (max 25000 chars)")

    from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: WPS433

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"meeting-summary-{lead_id}-{uuid.uuid4()}",
        system_message=(
            "You are a sales/CRM intelligence analyst. Given raw meeting notes, call transcripts, "
            "or voice transcripts, extract structured intelligence. ALWAYS respond with STRICT JSON. "
            "No prose, no markdown, no code fences. The JSON object MUST have these keys:\n"
            "- summary (string, 2-3 sentences)\n"
            "- risks (array of short strings — concerns, blockers, friction)\n"
            "- opportunities (array of short strings — upsells, expansion, new use cases)\n"
            "- next_steps (array of short strings — recommended actions for the team)\n"
            "- action_items (array of {title, owner_hint?, priority? in [low|medium|high], due_in_days?})\n"
            "- sentiment (string: positive | neutral | negative | mixed)\n"
            "- key_stakeholders (array of {name, role_hint?})\n\n"
            "Keep arrays concise (max 5 items each). Be specific and actionable. "
            "If the notes are too short or unclear, return empty arrays but still produce a summary."
        )
    ).with_model("gemini", "gemini-3.1-pro-preview")

    prompt = (
        f"Lead: {lead.get('title', '')}\n"
        f"Customer: {lead.get('customer_name', '')} ({lead.get('customer_company', '')})\n"
        f"Meeting date: {body.meeting_date or 'unknown'}\n\n"
        f"Raw notes / transcript:\n{body.raw_notes.strip()}\n\n"
        "Output STRICT JSON only."
    )

    try:
        response = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        logger.exception(f"LLM error during meeting summary: {e}")
        raise HTTPException(status_code=502, detail=f"AI request failed: {str(e)[:120]}")

    raw = (response or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except Exception:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            raise HTTPException(status_code=502, detail="AI returned non-JSON output")
        try:
            parsed = json.loads(m.group(0))
        except Exception:
            raise HTTPException(status_code=502, detail="AI returned malformed JSON")

    # Normalize structure
    summary_text = (parsed.get('summary') or '').strip()
    risks = [str(x).strip() for x in (parsed.get('risks') or []) if str(x).strip()][:5]
    opportunities = [str(x).strip() for x in (parsed.get('opportunities') or []) if str(x).strip()][:5]
    next_steps = [str(x).strip() for x in (parsed.get('next_steps') or []) if str(x).strip()][:5]
    action_items = [a for a in (parsed.get('action_items') or []) if isinstance(a, dict) and a.get('title')][:5]
    sentiment = (parsed.get('sentiment') or 'neutral').lower()
    if sentiment not in ('positive', 'neutral', 'negative', 'mixed'):
        sentiment = 'neutral'
    stakeholders = [s for s in (parsed.get('key_stakeholders') or []) if isinstance(s, dict) and s.get('name')][:8]

    summary_doc = {
        "summary": summary_text,
        "risks": risks,
        "opportunities": opportunities,
        "next_steps": next_steps,
        "action_items": action_items,
        "sentiment": sentiment,
        "key_stakeholders": stakeholders,
        "raw_notes_preview": body.raw_notes[:280],
        "meeting_date": body.meeting_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user['id'],
        "created_by_name": current_user['name'],
    }

    # Persist as a structured comment so it shows in the timeline
    comment_payload = (
        f"📝 Meeting Summary ({body.meeting_date or 'no date'})\n\n"
        f"{summary_text}\n\n"
        + (f"⚠️ Risks: " + " · ".join(risks) + "\n" if risks else '')
        + (f"💡 Opportunities: " + " · ".join(opportunities) + "\n" if opportunities else '')
        + (f"➡️ Next steps: " + " · ".join(next_steps) + "\n" if next_steps else '')
    )
    comment = {
        "id": str(uuid.uuid4()),
        "content": comment_payload.strip(),
        "user_id": current_user['id'],
        "user_name": current_user['name'],
        "user_role": current_user['role'],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parent_comment_id": None,
        "meeting_summary": summary_doc,  # embedded structured payload
    }

    await db.leads.update_one(
        {"id": lead_id},
        {
            "$push": {"comments": comment, "meeting_summaries": summary_doc},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        }
    )

    # Optionally create Tasks from action items
    created_task_ids = []
    if body.auto_create_tasks and action_items:
        today = datetime.now(timezone.utc).date()
        for ai_item in action_items:
            due = None
            try:
                offset = int(ai_item.get('due_in_days') or 0)
                if offset > 0:
                    due = (today + timedelta(days=offset)).isoformat()
            except Exception:
                due = None
            priority = (ai_item.get('priority') or 'medium').lower()
            if priority not in ('low', 'medium', 'high'):
                priority = 'medium'
            task = {
                "id": str(uuid.uuid4()),
                "title": str(ai_item.get('title', '')).strip()[:200] or 'AI action item',
                "description": f"From meeting on {body.meeting_date or 'unspecified date'}. Owner hint: {ai_item.get('owner_hint') or '—'}",
                "assignee_id": current_user['id'],
                "lead_id": lead_id,
                "commercial_id": None,
                "due_date": due,
                "priority": priority,
                "status": "todo",
                "created_by": current_user['id'],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "source": "ai_meeting_summary",
            }
            await db.tasks.insert_one(task)
            created_task_ids.append(task['id'])

    return {
        "summary": summary_doc,
        "comment_id": comment['id'],
        "created_task_ids": created_task_ids,
    }

@api_router.get("/leads/{lead_id}/ai/meeting-summaries")
async def list_meeting_summaries(lead_id: str, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"summaries": (lead.get('meeting_summaries') or [])[::-1]}

# ==================== PHASE 1.5: TASKS + DASHBOARD DIGEST ====================

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assignee_id: Optional[str] = None  # If None, defaults to creator
    lead_id: Optional[str] = None
    commercial_id: Optional[str] = None
    due_date: Optional[str] = None  # ISO date
    priority: str = "medium"  # low | medium | high
    status: str = "todo"  # todo | in_progress | done

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None

async def _enrich_task(task: dict) -> dict:
    """Attach assignee + creator + lead names to a task doc."""
    if task.get('assignee_id'):
        u = await db.users.find_one({"id": task['assignee_id']}, {"_id": 0})
        task['assignee_name'] = (u or {}).get('name')
    if task.get('created_by'):
        u = await db.users.find_one({"id": task['created_by']}, {"_id": 0})
        task['created_by_name'] = (u or {}).get('name')
    if task.get('lead_id'):
        lead = await db.leads.find_one({"id": task['lead_id']}, {"_id": 0})
        task['lead_title'] = (lead or {}).get('title')
    return task

@api_router.post("/tasks")
async def create_task(body: TaskCreate, current_user: dict = Depends(get_current_user)):
    if body.status not in ("todo", "in_progress", "done"):
        raise HTTPException(status_code=400, detail="Invalid status")
    if body.priority not in ("low", "medium", "high"):
        raise HTTPException(status_code=400, detail="Invalid priority")

    task = {
        "id": str(uuid.uuid4()),
        "title": body.title.strip(),
        "description": (body.description or '').strip(),
        "assignee_id": body.assignee_id or current_user['id'],
        "lead_id": body.lead_id,
        "commercial_id": body.commercial_id,
        "due_date": body.due_date,
        "priority": body.priority,
        "status": body.status,
        "created_by": current_user['id'],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    await db.tasks.insert_one(task)
    task.pop('_id', None)

    # Notify assignee if different from creator
    if task['assignee_id'] != current_user['id']:
        try:
            lead_title = ""
            if task.get('lead_id'):
                lead = await db.leads.find_one({"id": task['lead_id']}, {"_id": 0})
                lead_title = (lead or {}).get('title', '')
            await create_notification(
                user_id=task['assignee_id'],
                notification_type="task_assigned",
                title=f"New task: {task['title']}",
                message=(f"On lead \"{lead_title}\" — " if lead_title else "") + (task['description'] or 'No description')[:140],
                lead_id=task.get('lead_id'),
                data={"task_id": task['id'], "priority": task['priority']},
            )
        except Exception as e:
            logger.warning(f"Failed to notify task assignee: {e}")

    return await _enrich_task({**task})

@api_router.get("/tasks")
async def list_tasks(
    lead_id: Optional[str] = None,
    assignee_id: Optional[str] = None,
    status: Optional[str] = None,
    mine: bool = False,
    current_user: dict = Depends(get_current_user),
):
    query = {}
    if lead_id:
        query['lead_id'] = lead_id
    if assignee_id:
        query['assignee_id'] = assignee_id
    if status:
        query['status'] = status
    if mine:
        query['assignee_id'] = current_user['id']
    # Default scope: non-admins only see tasks they created or are assigned
    if not (current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_vyapaar_ops')):
        query = {**query, "$or": [{"assignee_id": current_user['id']}, {"created_by": current_user['id']}]}

    tasks = await db.tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [await _enrich_task(t) for t in tasks]

@api_router.patch("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate, current_user: dict = Depends(get_current_user)):
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    is_admin_like = current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_vyapaar_ops')
    if not (is_admin_like or task.get('created_by') == current_user['id'] or task.get('assignee_id') == current_user['id']):
        raise HTTPException(status_code=403, detail="Not authorized to modify this task")

    updates = {k: v for k, v in body.dict(exclude_unset=True).items() if v is not None}
    if 'status' in updates:
        if updates['status'] not in ("todo", "in_progress", "done"):
            raise HTTPException(status_code=400, detail="Invalid status")
        if updates['status'] == "done" and task.get('status') != "done":
            updates['completed_at'] = datetime.now(timezone.utc).isoformat()
        elif updates['status'] != "done":
            updates['completed_at'] = None
    updates['updated_at'] = datetime.now(timezone.utc).isoformat()

    await db.tasks.update_one({"id": task_id}, {"$set": updates})
    new_task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    return await _enrich_task(new_task)

@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, current_user: dict = Depends(get_current_user)):
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    is_admin_like = current_user.get('role') == UserRole.SUPER_ADMIN.value or current_user.get('is_vyapaar_ops')
    if not (is_admin_like or task.get('created_by') == current_user['id']):
        raise HTTPException(status_code=403, detail="Not authorized to delete this task")
    await db.tasks.delete_one({"id": task_id})
    return {"deleted": True}

# ---------- Dashboard digest ----------
@api_router.get("/dashboard/digest")
async def dashboard_digest(current_user: dict = Depends(get_current_user)):
    """Single endpoint returning the user's daily collaboration digest counts.
    Scope respects role: customers see their own data, partners see their assigned leads, etc.
    """
    now = datetime.now(timezone.utc)
    week_ago_iso = (now - timedelta(days=7)).isoformat()
    today_iso = now.date().isoformat()

    # Build lead query scoped to current user
    lead_query = {}
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        lead_query['selling_partner_id'] = current_user['id']
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        lead_query['sales_associate_id'] = current_user['id']
    elif current_user['role'] == UserRole.CUSTOMER.value:
        lead_query['created_by'] = current_user['id']

    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    won_map = {s['id']: bool(s.get('is_won')) for s in statuses}

    leads = await db.leads.find(lead_query, {"_id": 0}).to_list(1000)
    hot_count = at_risk_count = cold_count = warm_count = 0
    leads_gone_cold_week = 0
    overdue_followups = 0
    upcoming_followups_today = 0

    for lead in leads:
        lead['active_partners_count'] = len([p for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active'])
        lead['status_is_won'] = won_map.get(lead.get('status_id'), False)
        h = compute_lead_health(lead)
        if h['band'] == 'hot': hot_count += 1
        elif h['band'] == 'warm': warm_count += 1
        elif h['band'] == 'cold': cold_count += 1
        elif h['band'] == 'at_risk':
            at_risk_count += 1
            # "Gone cold this week" = was recently active, now at risk
            updated_at = lead.get('updated_at') or lead.get('created_at')
            if updated_at and updated_at < week_ago_iso and h.get('days_inactive') and h['days_inactive'] <= 10:
                leads_gone_cold_week += 1

        for f in lead.get('follow_ups') or []:
            if not f.get('is_completed') and f.get('scheduled_date'):
                if f['scheduled_date'] < today_iso:
                    overdue_followups += 1
                elif f['scheduled_date'] == today_iso:
                    upcoming_followups_today += 1

    # @mentions for me — unread
    mentions_for_me = await db.notifications.count_documents({
        "user_id": current_user['id'],
        "type": "lead_mention",
        "read": False,
    })

    # Tasks
    my_open_tasks = await db.tasks.count_documents({
        "assignee_id": current_user['id'],
        "status": {"$ne": "done"},
    })
    overdue_tasks = await db.tasks.count_documents({
        "assignee_id": current_user['id'],
        "status": {"$ne": "done"},
        "due_date": {"$lt": today_iso, "$ne": None},
    })

    return {
        "user": {
            "id": current_user['id'],
            "name": current_user['name'],
        },
        "leads": {
            "total": len(leads),
            "hot": hot_count,
            "warm": warm_count,
            "cold": cold_count,
            "at_risk": at_risk_count,
            "gone_cold_this_week": leads_gone_cold_week,
        },
        "follow_ups": {
            "overdue": overdue_followups,
            "today": upcoming_followups_today,
        },
        "mentions": {
            "unread": mentions_for_me,
        },
        "tasks": {
            "open": my_open_tasks,
            "overdue": overdue_tasks,
        },
    }

# ==================== PHASE 2: REVENUE INTELLIGENCE ====================

# Heuristic probability mapping by lead status name (case-insensitive substring match)
_STATUS_PROBABILITY = {
    'new': 0.10,
    'contact': 0.25,           # "contacted"
    'qualified': 0.40,
    'proposal': 0.60,
    'negotiat': 0.75,          # "negotiation"
    'won': 1.00,
    'lost': 0.00,
    'renewal': 0.65,
    'draft': 0.10,
}

def _probability_for(status_name: Optional[str], status_is_won: bool, status_is_lost: bool = False) -> float:
    if status_is_won:
        return 1.0
    if status_is_lost:
        return 0.0
    name = (status_name or '').lower()
    for key, p in _STATUS_PROBABILITY.items():
        if key in name:
            return p
    return 0.30  # safe default for unknown statuses

@api_router.get("/dashboard/revenue-intelligence")
async def revenue_intelligence(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Phase 2: Revenue Intelligence Dashboard.

    Returns KPI cards (pipeline, weighted, MRR/ARR, win rate), pipeline-by-stage breakdown,
    forecast-by-month, top selling partners by revenue, health distribution by deal value,
    and at-risk pipeline sum.
    """
    # Role-based scope
    lead_query: Dict[str, Any] = {}
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        lead_query['selling_partner_id'] = current_user['id']
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        lead_query['sales_associate_id'] = current_user['id']
    elif current_user['role'] == UserRole.CUSTOMER.value:
        lead_query['created_by'] = current_user['id']

    # Date filter (created_at)
    if start_date or end_date:
        cond = {}
        if start_date:
            cond["$gte"] = start_date
        if end_date:
            cond["$lte"] = end_date + 'T23:59:59'
        lead_query['created_at'] = cond

    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}

    leads = await db.leads.find(lead_query, {"_id": 0}).to_list(2000)

    # KPI aggregates
    total_pipeline = 0.0
    weighted_pipeline = 0.0
    won_value = 0.0
    won_count = 0
    closed_count = 0  # won + lost
    at_risk_value = 0.0
    by_stage: Dict[str, Dict[str, Any]] = {}
    by_partner: Dict[str, Dict[str, Any]] = {}
    health_buckets = {"hot": 0.0, "warm": 0.0, "cold": 0.0, "at_risk": 0.0}

    for lead in leads:
        st = status_map.get(lead.get('status_id') or '')
        status_is_won = bool(st and st.get('is_won'))
        status_is_lost = bool(st and st.get('is_lost'))
        status_name = (st or {}).get('name', 'Unstaged')
        deal_value = float(lead.get('deal_value') or 0)

        # Pipeline = open (non-closed)
        if not status_is_won and not status_is_lost:
            total_pipeline += deal_value
            prob = _probability_for(status_name, False)
            weighted_pipeline += deal_value * prob

        if status_is_won:
            won_value += deal_value
            won_count += 1
            closed_count += 1
        if status_is_lost:
            closed_count += 1

        # Stage breakdown
        stage_key = status_name
        if stage_key not in by_stage:
            by_stage[stage_key] = {"stage": stage_key, "count": 0, "total_value": 0.0, "weighted_value": 0.0, "color": (st or {}).get('color', '#6366F1')}
        by_stage[stage_key]['count'] += 1
        by_stage[stage_key]['total_value'] += deal_value
        by_stage[stage_key]['weighted_value'] += deal_value * _probability_for(status_name, status_is_won, status_is_lost)

        # Partner breakdown (only count Won deals for revenue)
        partner_id = lead.get('selling_partner_id')
        partner_name = lead.get('selling_partner_name') or 'Unassigned'
        if partner_id or partner_name == 'Unassigned':
            pkey = partner_id or '__unassigned__'
            if pkey not in by_partner:
                by_partner[pkey] = {"partner_id": partner_id, "partner_name": partner_name, "won_revenue": 0.0, "deal_count": 0, "won_count": 0}
            by_partner[pkey]['deal_count'] += 1
            if status_is_won:
                by_partner[pkey]['won_revenue'] += deal_value
                by_partner[pkey]['won_count'] += 1

        # Health bucket by value
        lead_for_health = {**lead}
        lead_for_health['active_partners_count'] = len([p for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active'])
        lead_for_health['status_is_won'] = status_is_won
        h = compute_lead_health(lead_for_health)
        health_buckets[h['band']] = health_buckets.get(h['band'], 0) + deal_value
        if h['band'] == 'at_risk' and not status_is_won and not status_is_lost:
            at_risk_value += deal_value

    win_rate = (won_count / closed_count * 100) if closed_count > 0 else 0
    avg_deal_size = (won_value / won_count) if won_count > 0 else 0

    # MRR / ARR from commercials (recurring deals)
    commercials = await db.commercials.find({"$or": [{"type": "recurring"}, {"deal_type": "recurring"}]}, {"_id": 0}).to_list(2000)
    mrr = 0.0
    arr = 0.0
    for c in commercials:
        if c.get('status') == 'cancelled' or c.get('status') == 'churned':
            continue
        billing_cycle = (c.get('billing_cycle') or 'monthly').lower()
        amount = float(c.get('recurring_amount') or c.get('total_value') or 0)
        if amount <= 0:
            continue
        if billing_cycle == 'monthly':
            mrr += amount
        elif billing_cycle == 'quarterly':
            mrr += amount / 3.0
        elif billing_cycle == 'annual' or billing_cycle == 'yearly':
            mrr += amount / 12.0
    arr = mrr * 12

    # Forecast next 90 days — weighted pipeline expected to close monthly
    today = datetime.now(timezone.utc).date()
    forecast = []
    for offset_months in range(3):
        month_start = (today.replace(day=1) + timedelta(days=32 * offset_months)).replace(day=1)
        # forecasted revenue = weighted_pipeline / 3 (uniform spread) — simple but tunable
        label = month_start.strftime("%b %Y")
        forecast.append({
            "month": label,
            "month_iso": month_start.isoformat(),
            "forecasted": round(weighted_pipeline / 3, 2),
        })

    # Win rate trend (last 6 months)
    win_trend = []
    for offset_months in range(5, -1, -1):
        month_dt = (today.replace(day=1) - timedelta(days=30 * offset_months)).replace(day=1)
        m_start_iso = month_dt.isoformat()
        next_month = (month_dt.replace(day=28) + timedelta(days=4)).replace(day=1)
        m_end_iso = next_month.isoformat()
        month_won = sum(
            1 for l in leads
            if status_map.get(l.get('status_id') or '', {}).get('is_won')
            and l.get('updated_at', '') >= m_start_iso and l.get('updated_at', '') < m_end_iso
        )
        month_closed = sum(
            1 for l in leads
            if (status_map.get(l.get('status_id') or '', {}).get('is_won') or status_map.get(l.get('status_id') or '', {}).get('is_lost'))
            and l.get('updated_at', '') >= m_start_iso and l.get('updated_at', '') < m_end_iso
        )
        win_trend.append({
            "month": month_dt.strftime("%b"),
            "won": month_won,
            "closed": month_closed,
            "win_rate": round((month_won / month_closed * 100) if month_closed > 0 else 0, 1),
        })

    return {
        "kpis": {
            "total_pipeline": round(total_pipeline, 2),
            "weighted_pipeline": round(weighted_pipeline, 2),
            "won_value": round(won_value, 2),
            "won_count": won_count,
            "avg_deal_size": round(avg_deal_size, 2),
            "win_rate": round(win_rate, 1),
            "at_risk_value": round(at_risk_value, 2),
            "mrr": round(mrr, 2),
            "arr": round(arr, 2),
            "total_leads": len(leads),
        },
        "pipeline_by_stage": sorted(by_stage.values(), key=lambda x: -x['total_value']),
        "top_partners": sorted(by_partner.values(), key=lambda x: -x['won_revenue'])[:8],
        "forecast": forecast,
        "win_rate_trend": win_trend,
        "health_value_distribution": [
            {"band": "hot", "value": round(health_buckets['hot'], 2)},
            {"band": "warm", "value": round(health_buckets['warm'], 2)},
            {"band": "cold", "value": round(health_buckets['cold'], 2)},
            {"band": "at_risk", "value": round(health_buckets['at_risk'], 2)},
        ],
    }

# ==================== PHASE 24: PREDICTIVE REVENUE FORECASTING ====================

def _ema(values: List[float], alpha: float = 0.5) -> float:
    """Exponential moving average for trend smoothing."""
    if not values:
        return 0.0
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema

def _months_between(start: datetime, end: datetime) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)

@api_router.get("/dashboard/predictive-forecast")
async def predictive_forecast(
    horizon_months: int = 6,
    current_user: dict = Depends(get_current_user),
):
    """Predictive Revenue Forecasting.
    Combines:
      - Statistical baseline (linear regression + EMA on last 12 months of won revenue)
      - Pipeline-weighted forecast (weighted_pipeline / stage-velocity)
      - Per-lead closure probability (status_prob × health_factor × recency_factor)
      - Optional AI narrative (Gemini) — best-effort, falls back silently
    """
    horizon_months = max(1, min(12, int(horizon_months or 6)))

    lead_query: Dict[str, Any] = {}
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        lead_query['selling_partner_id'] = current_user['id']
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        lead_query['sales_associate_id'] = current_user['id']
    elif current_user['role'] == UserRole.CUSTOMER.value:
        lead_query['created_by'] = current_user['id']

    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}
    leads = await db.leads.find(lead_query, {"_id": 0}).to_list(5000)

    today = datetime.now(timezone.utc).date()
    today_dt = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

    # 1) Historical won revenue per month (last 12 months) — for statistical baseline
    history_window = 12
    history_buckets: Dict[str, float] = {}
    history_counts: Dict[str, int] = {}
    for i in range(history_window - 1, -1, -1):
        m_dt = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        history_buckets[m_dt.isoformat()] = 0.0
        history_counts[m_dt.isoformat()] = 0

    avg_close_days_by_stage: Dict[str, List[float]] = {}
    won_close_days: List[float] = []

    for lead in leads:
        st = status_map.get(lead.get('status_id') or '') or {}
        if not st.get('is_won'):
            continue
        updated = lead.get('updated_at') or lead.get('created_at') or ''
        if not updated:
            continue
        try:
            d = datetime.fromisoformat(updated.replace('Z', '+00:00')).date()
        except Exception:
            continue
        m_iso = d.replace(day=1).isoformat()
        if m_iso in history_buckets:
            history_buckets[m_iso] += float(lead.get('deal_value') or 0)
            history_counts[m_iso] += 1
        # Average days to close (created → won)
        try:
            created = datetime.fromisoformat((lead.get('created_at') or '').replace('Z', '+00:00')).date()
            days = (d - created).days
            if 0 <= days <= 720:
                won_close_days.append(days)
        except Exception:
            pass

    history_series = [
        {"month": datetime.fromisoformat(k).strftime("%b %Y"), "month_iso": k, "won_revenue": round(v, 2), "won_count": history_counts[k]}
        for k, v in sorted(history_buckets.items())
    ]
    monthly_values = [h['won_revenue'] for h in history_series]

    # 2) Statistical baseline (linear regression slope + EMA)
    n = len(monthly_values)
    if n >= 2 and sum(monthly_values) > 0:
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(monthly_values) / n
        num = sum((xs[i] - x_mean) * (monthly_values[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n)) or 1
        slope = num / den
        intercept = y_mean - slope * x_mean
    else:
        slope = 0.0
        intercept = monthly_values[-1] if monthly_values else 0.0

    ema_baseline = _ema(monthly_values, alpha=0.55)
    avg_won = (sum(monthly_values) / n) if n > 0 else 0.0

    # 3) Pipeline-weighted forecast — assign each open lead an expected close month
    avg_close_overall = (sum(won_close_days) / len(won_close_days)) if won_close_days else 60.0
    pipeline_per_month: Dict[str, float] = {}
    closure_predictions = []  # per-lead

    for lead in leads:
        st = status_map.get(lead.get('status_id') or '') or {}
        if st.get('is_won') or st.get('is_lost'):
            continue
        status_name = st.get('name', 'Unstaged')
        deal_value = float(lead.get('deal_value') or 0)
        if deal_value <= 0:
            continue

        # Probability from status + health + recency
        status_prob = _probability_for(status_name, False)

        lead_for_h = {**lead, 'active_partners_count': len([p for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active']), 'status_is_won': False}
        h = compute_lead_health(lead_for_h)
        # Health multiplier: hot 1.2 / warm 1.0 / cold 0.75 / at_risk 0.5
        health_mult = {"hot": 1.2, "warm": 1.0, "cold": 0.75, "at_risk": 0.5}.get(h['band'], 1.0)
        # Recency: leads inactive > 30 days get penalized
        days_inactive = h.get('days_inactive') or 0
        recency_mult = 1.0 if days_inactive <= 7 else (0.85 if days_inactive <= 30 else 0.6)

        prob = min(1.0, max(0.0, status_prob * health_mult * recency_mult))
        expected = deal_value * prob

        # Expected close date — stage-based offset (rough heuristic on avg_close_overall)
        stage_offset_days = {
            'new': avg_close_overall, 'contact': avg_close_overall * 0.85,
            'qualified': avg_close_overall * 0.7, 'proposal': avg_close_overall * 0.45,
            'negotiat': avg_close_overall * 0.25, 'renewal': avg_close_overall * 0.4,
        }
        offset = avg_close_overall
        for k, off in stage_offset_days.items():
            if k in status_name.lower():
                offset = off
                break
        # If lead has overdue follow-ups, push out 14 days
        if (h.get('overdue_count') or 0) > 0:
            offset += 14
        expected_close = today + timedelta(days=max(0, int(offset)))

        # Bucket into target month
        month_key = expected_close.replace(day=1).isoformat()
        pipeline_per_month[month_key] = pipeline_per_month.get(month_key, 0) + expected

        closure_predictions.append({
            "lead_id": lead.get('id'),
            "title": lead.get('title', ''),
            "customer_company": lead.get('customer_company', ''),
            "deal_value": deal_value,
            "stage": status_name,
            "probability": round(prob * 100, 1),
            "expected_revenue": round(expected, 2),
            "health_band": h['band'],
            "expected_close_date": expected_close.isoformat(),
            "days_to_close": (expected_close - today).days,
        })

    # 4) Build horizon forecast — combine statistical + pipeline-weighted, weighted
    forecast = []
    for i in range(horizon_months):
        m_dt = (today.replace(day=1) + timedelta(days=32 * i)).replace(day=1)
        m_iso = m_dt.isoformat()
        stat_forecast = max(0, intercept + slope * (n + i))   # linear projection
        stat_blend = (stat_forecast * 0.55) + (ema_baseline * 0.25) + (avg_won * 0.20)
        pipeline_predicted = pipeline_per_month.get(m_iso, 0)
        combined = round((stat_blend * 0.45) + (pipeline_predicted * 0.55), 2)

        # Confidence band: ±25% widening with horizon
        spread = 0.18 + (i * 0.04)
        forecast.append({
            "month": m_dt.strftime("%b %Y"),
            "month_iso": m_iso,
            "stat_forecast": round(stat_blend, 2),
            "pipeline_forecast": round(pipeline_predicted, 2),
            "combined": combined,
            "low": round(combined * (1 - spread), 2),
            "high": round(combined * (1 + spread), 2),
        })

    # 5) Top closure predictions for next 90 days
    closure_predictions.sort(key=lambda x: (-x['expected_revenue']))
    next_90 = [c for c in closure_predictions if c['days_to_close'] <= 90][:20]

    # 6) AI narrative (best-effort)
    ai_narrative = None
    if EMERGENT_LLM_KEY and forecast:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: WPS433
            summary_lines = [f"  - {f['month']}: ₹{f['combined']:,.0f} (range ₹{f['low']:,.0f}–₹{f['high']:,.0f})" for f in forecast[:horizon_months]]
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"forecast-{uuid.uuid4()}",
                system_message=(
                    "You are a revenue operations analyst. Given a forecast table, write a 2-3 sentence executive summary "
                    "highlighting trend direction, biggest opportunity month, and one risk. Be concrete with numbers. "
                    "Use Indian Rupee notation (₹). No markdown, no bullets, no preamble like 'Here is the summary'."
                ),
            ).with_model("gemini", "gemini-3.1-pro-preview")
            prompt = (
                f"Last 6 months won revenue (₹): {[round(x, 0) for x in monthly_values[-6:]]}\n"
                f"Forecast (next {horizon_months} months):\n" + "\n".join(summary_lines) + "\n"
                f"Pipeline tracked: {len(closure_predictions)} open deals, total weighted ₹{sum(c['expected_revenue'] for c in closure_predictions):,.0f}"
            )
            raw = await chat.send_message(UserMessage(text=prompt))
            ai_narrative = (raw or '').strip().strip('`').strip()[:600]
        except Exception as e:
            logger.warning(f"AI narrative failed (silent fallback): {e}")
            ai_narrative = None

    # 7) Trend signal
    if n >= 3:
        recent_3 = sum(monthly_values[-3:]) / 3
        prior_3 = (sum(monthly_values[-6:-3]) / 3) if n >= 6 else recent_3
        if prior_3 > 0:
            mom_change_pct = ((recent_3 - prior_3) / prior_3) * 100
        else:
            mom_change_pct = 0
        trend_direction = "up" if mom_change_pct > 5 else ("down" if mom_change_pct < -5 else "flat")
    else:
        mom_change_pct = 0
        trend_direction = "flat"

    return {
        "horizon_months": horizon_months,
        "history": history_series,
        "forecast": forecast,
        "closure_predictions_next_90d": next_90,
        "summary": {
            "total_forecast": round(sum(f['combined'] for f in forecast), 2),
            "avg_monthly_forecast": round(sum(f['combined'] for f in forecast) / horizon_months, 2) if horizon_months else 0,
            "avg_historical_monthly": round(avg_won, 2),
            "trend_direction": trend_direction,
            "mom_change_pct": round(mom_change_pct, 1),
            "pipeline_weighted_total": round(sum(c['expected_revenue'] for c in closure_predictions), 2),
            "open_deal_count": len(closure_predictions),
            "avg_close_days": round(avg_close_overall, 1),
        },
        "ai_narrative": ai_narrative,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

# ==================== PHASE 25: PARTNER COMMISSION & REFERRAL ANALYTICS ====================
# (Companion endpoint to the existing partner-intelligence at line ~5457 — commission/referral
# data that the leaderboard endpoint doesn't expose.)

@api_router.get("/dashboard/partner-commission-analytics")
async def partner_commission_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    # Restrict to roles that can see this — admin/ops/finance only
    if current_user['role'] not in (
        UserRole.SUPER_ADMIN.value, UserRole.VYAPAAR_OPS.value, UserRole.VYAPAAR_FINANCE.value
    ):
        raise HTTPException(status_code=403, detail="Admin/Operations/Finance only")

    lead_query: Dict[str, Any] = {}
    if start_date or end_date:
        cond = {}
        if start_date:
            cond["$gte"] = start_date
        if end_date:
            cond["$lte"] = end_date + 'T23:59:59'
        lead_query['created_at'] = cond

    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}
    leads = await db.leads.find(lead_query, {"_id": 0}).to_list(5000)
    users = await db.users.find({"role": "selling_partner"}, {"_id": 0}).to_list(2000)
    associates = await db.users.find({"role": "sales_associate"}, {"_id": 0}).to_list(2000)

    # Build partner stats
    partner_stats: Dict[str, Dict[str, Any]] = {}
    associate_stats: Dict[str, Dict[str, Any]] = {}
    today = datetime.now(timezone.utc).date()

    def _ensure_partner(pid: str, pname: str):
        if pid not in partner_stats:
            partner_stats[pid] = {
                "partner_id": pid,
                "partner_name": pname,
                "assigned_count": 0,
                "won_count": 0,
                "lost_count": 0,
                "open_count": 0,
                "won_revenue": 0.0,
                "open_pipeline": 0.0,
                "total_close_days": 0.0,
                "close_days_samples": 0,
                "commission_paid": 0.0,
                "referrals_brought": 0,
                "referrals_won": 0,
                "categories": {},
                "monthly_won": {},  # YYYY-MM: deal_count
            }

    for u in users:
        _ensure_partner(u['id'], u.get('name', u.get('email', 'Unknown')))

    for lead in leads:
        st = status_map.get(lead.get('status_id') or '') or {}
        is_won = bool(st.get('is_won'))
        is_lost = bool(st.get('is_lost'))
        deal_value = float(lead.get('deal_value') or 0)
        primary_cat = lead.get('primary_category_name') or 'Uncategorized'

        # Stats for all assigned_partners (multi-partner concurrent assignment supported)
        for ap in (lead.get('assigned_partners') or []):
            pid = ap.get('partner_id')
            if not pid:
                continue
            _ensure_partner(pid, ap.get('partner_name', 'Unknown'))
            partner_stats[pid]['assigned_count'] += 1
            ap_status = ap.get('status', 'active')
            if ap_status == 'won':
                partner_stats[pid]['won_count'] += 1
                partner_stats[pid]['won_revenue'] += deal_value
                # Time to close
                try:
                    if ap.get('assigned_at') and ap.get('won_at'):
                        a = datetime.fromisoformat(ap['assigned_at'].replace('Z', '+00:00')).date()
                        w = datetime.fromisoformat(ap['won_at'].replace('Z', '+00:00')).date()
                        days = (w - a).days
                        if 0 <= days <= 720:
                            partner_stats[pid]['total_close_days'] += days
                            partner_stats[pid]['close_days_samples'] += 1
                except Exception:
                    pass
                # Monthly heatmap
                try:
                    w = datetime.fromisoformat(ap['won_at'].replace('Z', '+00:00')).date()
                    mkey = w.strftime("%Y-%m")
                    partner_stats[pid]['monthly_won'][mkey] = partner_stats[pid]['monthly_won'].get(mkey, 0) + 1
                except Exception:
                    pass
            elif ap_status == 'lost':
                partner_stats[pid]['lost_count'] += 1
            else:
                partner_stats[pid]['open_count'] += 1
                partner_stats[pid]['open_pipeline'] += deal_value
            # Categories
            cat = partner_stats[pid]['categories']
            cat[primary_cat] = cat.get(primary_cat, 0) + 1

        # Referrer commission tracking — admin commission share goes to platform
        # We approximate partner's commission as the selling_partner_share when won
        if is_won and lead.get('selling_partner_id'):
            pid = lead['selling_partner_id']
            _ensure_partner(pid, lead.get('selling_partner_name', 'Unknown'))
            v_pct = float(lead.get('vyapaar_percentage') or 0)
            sa_pct = float(lead.get('sales_associate_commission') or 0)
            v_share = deal_value * (v_pct / 100)
            sa_share = v_share * (sa_pct / 100) if sa_pct else 0
            v_net = v_share - sa_share
            partner_share = deal_value - v_share
            partner_stats[pid]['commission_paid'] += partner_share

            # Associate commission tracking
            if lead.get('sales_associate_id') and sa_share > 0:
                aid = lead['sales_associate_id']
                if aid not in associate_stats:
                    associate_stats[aid] = {
                        "associate_id": aid,
                        "associate_name": lead.get('sales_associate_name', 'Unknown'),
                        "leads_brought": 0,
                        "won_count": 0,
                        "won_revenue": 0.0,
                        "commission_earned": 0.0,
                    }
                associate_stats[aid]['won_count'] += 1
                associate_stats[aid]['won_revenue'] += deal_value
                associate_stats[aid]['commission_earned'] += sa_share

        # Track lead origination by associate (regardless of won/lost)
        if lead.get('sales_associate_id'):
            aid = lead['sales_associate_id']
            if aid not in associate_stats:
                associate_stats[aid] = {
                    "associate_id": aid,
                    "associate_name": lead.get('sales_associate_name', 'Unknown'),
                    "leads_brought": 0,
                    "won_count": 0,
                    "won_revenue": 0.0,
                    "commission_earned": 0.0,
                }
            associate_stats[aid]['leads_brought'] += 1

        # Referral tracking — referred_by_partner_id
        ref_pid = lead.get('referred_by_partner_id')
        if ref_pid:
            _ensure_partner(ref_pid, lead.get('referred_by_partner_name', 'Unknown'))
            partner_stats[ref_pid]['referrals_brought'] += 1
            if is_won:
                partner_stats[ref_pid]['referrals_won'] += 1

    # Compute derived metrics + rank
    partners_list = []
    for p in partner_stats.values():
        conv = (p['won_count'] / p['assigned_count'] * 100) if p['assigned_count'] > 0 else 0
        avg_close = (p['total_close_days'] / p['close_days_samples']) if p['close_days_samples'] > 0 else None
        avg_deal = (p['won_revenue'] / p['won_count']) if p['won_count'] > 0 else 0
        referral_conv = (p['referrals_won'] / p['referrals_brought'] * 100) if p['referrals_brought'] > 0 else 0
        # Performance score (composite, 0-100)
        score = 0
        score += min(50, p['won_count'] * 3)          # win volume
        score += min(25, conv / 4)                     # conversion
        score += min(15, p['won_revenue'] / 1e6 * 5)   # revenue scale (₹10L = full pts)
        if avg_close is not None:
            score += max(0, 10 - min(10, avg_close / 30))  # speed bonus
        partners_list.append({
            "partner_id": p['partner_id'],
            "partner_name": p['partner_name'],
            "assigned_count": p['assigned_count'],
            "won_count": p['won_count'],
            "lost_count": p['lost_count'],
            "open_count": p['open_count'],
            "won_revenue": round(p['won_revenue'], 2),
            "open_pipeline": round(p['open_pipeline'], 2),
            "conversion_rate": round(conv, 1),
            "avg_close_days": round(avg_close, 1) if avg_close is not None else None,
            "avg_deal_size": round(avg_deal, 2),
            "commission_paid": round(p['commission_paid'], 2),
            "referrals_brought": p['referrals_brought'],
            "referrals_won": p['referrals_won'],
            "referral_conversion": round(referral_conv, 1),
            "top_category": (max(p['categories'].items(), key=lambda x: x[1])[0] if p['categories'] else None),
            "performance_score": round(min(100, max(0, score)), 1),
            "monthly_won": p['monthly_won'],
        })

    partners_list.sort(key=lambda x: -x['performance_score'])

    # Build heatmap matrix for top 8 partners × last 6 months
    top_8 = partners_list[:8]
    months = []
    for i in range(5, -1, -1):
        m_dt = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        months.append(m_dt.strftime("%Y-%m"))
    heatmap = {
        "months": [datetime.strptime(m, "%Y-%m").strftime("%b") for m in months],
        "partners": [
            {
                "partner_name": p['partner_name'],
                "values": [p['monthly_won'].get(m, 0) for m in months],
            }
            for p in top_8
        ],
    }

    # Associates list
    associates_list = sorted(associate_stats.values(), key=lambda x: -x['commission_earned'])

    # Aggregate KPIs
    total_partners = len([p for p in partners_list if p['assigned_count'] > 0])
    total_commission = sum(p['commission_paid'] for p in partners_list)
    total_won_revenue = sum(p['won_revenue'] for p in partners_list)
    avg_partner_revenue = (total_won_revenue / total_partners) if total_partners > 0 else 0

    # Category specialization (across system)
    category_partner_map: Dict[str, Dict[str, int]] = {}
    for p in partners_list:
        if not p['top_category']:
            continue
        category_partner_map.setdefault(p['top_category'], {})[p['partner_name']] = p['won_count']
    category_leaders = []
    for cat, partner_dict in category_partner_map.items():
        top_partner = max(partner_dict.items(), key=lambda x: x[1])
        category_leaders.append({
            "category": cat,
            "leader": top_partner[0],
            "wins": top_partner[1],
        })
    category_leaders.sort(key=lambda x: -x['wins'])

    return {
        "kpis": {
            "active_partners": total_partners,
            "total_partner_revenue": round(total_won_revenue, 2),
            "total_commission_paid": round(total_commission, 2),
            "avg_partner_revenue": round(avg_partner_revenue, 2),
            "top_performer": partners_list[0]['partner_name'] if partners_list else None,
            "top_performer_revenue": partners_list[0]['won_revenue'] if partners_list else 0,
        },
        "partners": partners_list,
        "top_associates": associates_list[:10],
        "heatmap": heatmap,
        "category_leaders": category_leaders[:10],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ==================== PHASE 27 + 27.5 — DEAL ROOMS ====================
# Moved to routers/deal_room.py (extracted Phase 31, Jun 1 2026).
# See `api_router.include_router(deal_room_router)` near the bottom of this file.


# ==================== PHASE 2: STAKEHOLDERS ====================

class StakeholderCreate(BaseModel):
    name: str
    role_type: str  # decision_maker | influencer | technical_evaluator | finance_approver | blocker | champion | end_user
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None  # e.g. "VP Sales"
    notes: Optional[str] = None
    engagement: str = "neutral"  # supportive | neutral | resistant | unknown

class StakeholderUpdate(BaseModel):
    name: Optional[str] = None
    role_type: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None
    engagement: Optional[str] = None

VALID_STAKEHOLDER_ROLES = {
    "decision_maker", "influencer", "technical_evaluator", "finance_approver",
    "blocker", "champion", "end_user", "other"
}
VALID_ENGAGEMENT = {"supportive", "neutral", "resistant", "unknown"}


# ==================== PHASE 29: WEEKLY WAR ROOM ====================
# Smart-bucket Kanban board + Weekly Review Mode + AI session summary.
# Buckets are COMPUTED from lead signals — no manual drag-drop. The value is the
# auto-categorization itself: leads land where they need attention this week.

WAR_ROOM_BUCKETS = [
    {"id": "high_priority", "label": "🔥 High Priority", "color": "#EF4444"},
    {"id": "blocked", "label": "⚠️ Blocked", "color": "#F59E0B"},
    {"id": "followup_pending", "label": "🟡 Follow-up Pending", "color": "#EAB308"},
    {"id": "commercial_pending", "label": "💰 Commercial Pending", "color": "#10B981"},
    {"id": "partner_coordination", "label": "🤝 Partner Coordination", "color": "#8B5CF6"},
    {"id": "open_leads", "label": "📋 Open Leads", "color": "#3B82F6"},
    {"id": "inactive", "label": "💤 Inactive", "color": "#64748B"},
    {"id": "recently_won", "label": "✅ Recently Won", "color": "#22C55E"},
]

def _classify_war_room_bucket(lead: dict, health: dict, today: date) -> str:
    """Decide which War Room bucket a lead belongs to. Priority order matters —
    a lead can only be in one bucket; we pick the most actionable.

    Phase 29.1: a manual `war_room_bucket_override` on the lead doc takes precedence
    over the computed bucket — UNLESS the lead has just been won/lost (we auto-clear
    overrides for terminal states so won deals always land in 'recently_won')."""
    status_is_won = bool(lead.get('status_is_won'))
    status_is_lost = bool(lead.get('status_is_lost'))

    override = lead.get('war_room_bucket_override')
    valid_bucket_ids = {b['id'] for b in WAR_ROOM_BUCKETS}
    if (override in valid_bucket_ids
        and not status_is_won
        and not status_is_lost):
        return override

    # 1) Recently Won — within last 14 days (gives admin reason to celebrate)
    if status_is_won:
        try:
            updated = datetime.fromisoformat((lead.get('updated_at') or '').replace('Z', '+00:00')).date()
            if (today - updated).days <= 14:
                return "recently_won"
        except Exception:
            pass
        return "recently_won"

    if status_is_lost:
        return None  # excluded from board

    days_inactive = health.get('days_inactive') or 0
    overdue_count = health.get('overdue_count') or 0
    health_band = health.get('band', 'cold')
    deal_value = float(lead.get('deal_value') or 0)
    has_blocker = any(
        '#blocker' in (c.get('content') or '').lower() or '#blocked' in (c.get('content') or '').lower()
        for c in (lead.get('comments') or [])[-10:]
    )
    pending_approvals = sum(1 for a in (lead.get('approvals') or []) if a.get('status') == 'pending')
    has_active_partners = any(p.get('status') == 'active' for p in (lead.get('assigned_partners') or []))

    # 2) Blocked — explicit #blocker comment or pending approval waiting > 3 days
    if has_blocker:
        return "blocked"
    if pending_approvals:
        oldest_pending = min(
            (a.get('created_at') for a in (lead.get('approvals') or []) if a.get('status') == 'pending'),
            default=None,
        )
        if oldest_pending:
            try:
                cd = datetime.fromisoformat(oldest_pending.replace('Z', '+00:00')).date()
                if (today - cd).days >= 3:
                    return "blocked"
            except Exception:
                pass

    # 3) Inactive — > 21 days no activity (any health band)
    if days_inactive >= 21:
        return "inactive"

    # 4) High Priority — Hot/At-risk band + deal value >= 100000 + recent activity
    if health_band in ('hot', 'at_risk') and deal_value >= 100000 and days_inactive <= 14:
        return "high_priority"

    # 5) Follow-up Pending — overdue follow-ups
    if overdue_count > 0:
        return "followup_pending"

    # 6) Commercial Pending — has commercial but not yet "active" stage; or status name contains 'proposal'/'commercial'
    status_name = (lead.get('status_name') or '').lower()
    if 'proposal' in status_name or 'commercial' in status_name or 'negotiat' in status_name or 'quote' in status_name:
        return "commercial_pending"

    # 7) Partner Coordination — has active partner + days_inactive 7-21 (waiting on partner)
    if has_active_partners and 7 <= days_inactive <= 21:
        return "partner_coordination"

    # Default — any non-won/lost lead that didn't match a specific urgency bucket
    # lands here. Previously these were dropped (causing the "30 open / 0 cards"
    # discrepancy users saw in the header KPI).
    if days_inactive >= 14:
        return "inactive"
    return "open_leads"

@api_router.get("/war-room/board")
async def war_room_board(
    owner_id: Optional[str] = None,
    partner_id: Optional[str] = None,
    category_id: Optional[str] = None,
    min_value: Optional[float] = None,
    current_user: dict = Depends(get_current_user),
):
    """Compute the smart-bucket board. Returns buckets + revenue strip + counts.
    Buckets are computed per-request (cheap on <10k leads, easy to extend)."""

    lead_query: Dict[str, Any] = {}
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        lead_query['selling_partner_id'] = current_user['id']
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        lead_query['sales_associate_id'] = current_user['id']
    elif current_user['role'] == UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Not available for customers")

    if owner_id:
        lead_query['$or'] = [
            {'selling_partner_id': owner_id},
            {'sales_associate_id': owner_id},
        ]
    if partner_id:
        lead_query['$or'] = [
            {'selling_partner_id': partner_id},
            {'assigned_partners.partner_id': partner_id},
        ]
    if category_id:
        lead_query['primary_category_id'] = category_id

    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}

    leads = await db.leads.find(lead_query, {"_id": 0}).to_list(5000)
    today = datetime.now(timezone.utc).date()

    bucket_map: Dict[str, List[dict]] = {b['id']: [] for b in WAR_ROOM_BUCKETS}

    total_pipeline = 0.0
    weighted_pipeline = 0.0
    at_risk_pipeline = 0.0
    inactive_pipeline = 0.0

    for lead in leads:
        st = status_map.get(lead.get('status_id') or '') or {}
        lead['status_is_won'] = bool(st.get('is_won'))
        lead['status_is_lost'] = bool(st.get('is_lost'))
        lead['status_name'] = st.get('name')
        lead['status_color'] = st.get('color')

        # Filter by min_value
        deal_value = float(lead.get('deal_value') or 0)
        if min_value is not None and deal_value < min_value:
            continue

        # Compute health
        h = compute_lead_health(lead)
        bucket = _classify_war_room_bucket(lead, h, today)
        if not bucket:
            continue

        # Aggregate revenue stats (exclude won)
        if not lead['status_is_won']:
            total_pipeline += deal_value
            prob = _probability_for(st.get('name', ''), False) / 100
            weighted_pipeline += deal_value * prob
            if h['band'] == 'at_risk':
                at_risk_pipeline += deal_value
            if bucket == 'inactive':
                inactive_pipeline += deal_value

        # Strip down to card-friendly payload
        # Top public/internal comment count + mentions count
        comment_count = len(lead.get('comments') or [])
        pending_approvals_n = sum(1 for a in (lead.get('approvals') or []) if a.get('status') == 'pending')
        next_action = h.get('next_action') or {}

        # Last follow-up date (most recent regardless of complete status)
        followups = lead.get('follow_ups') or []
        next_followup = None
        next_followup_overdue = False
        if followups:
            pending = [f for f in followups if not f.get('is_completed') and f.get('scheduled_date')]
            if pending:
                pending.sort(key=lambda f: f['scheduled_date'])
                nf = pending[0]
                next_followup = nf['scheduled_date']
                next_followup_overdue = (nf['scheduled_date'] < today.isoformat())

        card = {
            "id": lead['id'],
            "title": lead.get('title') or lead.get('customer_company') or 'Untitled',
            "customer_company": lead.get('customer_company'),
            "customer_name": lead.get('customer_name'),
            "primary_category_name": lead.get('primary_category_name'),
            "deal_value": deal_value,
            "status_name": st.get('name'),
            "status_color": st.get('color'),
            "selling_partner_name": lead.get('selling_partner_name'),
            "sales_associate_name": lead.get('sales_associate_name'),
            "referred_by_partner_name": lead.get('referred_by_partner_name'),
            "active_partners_count": sum(1 for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active'),
            "days_inactive": h.get('days_inactive'),
            "overdue_count": h.get('overdue_count'),
            "health_band": h.get('band'),
            "health_score": h.get('score'),
            "next_action_label": next_action.get('label'),
            "next_action_kind": next_action.get('kind'),
            "next_followup": next_followup,
            "next_followup_overdue": next_followup_overdue,
            "comment_count": comment_count,
            "pending_approvals": pending_approvals_n,
            "probability": _probability_for(st.get('name', ''), False),
            "expected_revenue": round(deal_value * (_probability_for(st.get('name', ''), False) / 100), 0),
            "deal_room_enabled": bool(lead.get('deal_room_enabled')),
            "updated_at": lead.get('updated_at'),
            # Phase 29.1: flag manually-overridden cards so the UI can show a "📌 pinned" indicator
            "is_manual_override": bool(lead.get('war_room_bucket_override')) and not lead['status_is_won'] and not lead['status_is_lost'],
        }
        bucket_map[bucket].append(card)

    # Sort each bucket by deal_value desc (highest revenue first)
    for bid in bucket_map:
        bucket_map[bid].sort(key=lambda c: -(c['deal_value'] or 0))

    return {
        "buckets": [
            {
                **b,
                "count": len(bucket_map[b['id']]),
                "total_value": round(sum(c['deal_value'] or 0 for c in bucket_map[b['id']]), 2),
                "leads": bucket_map[b['id']],
            }
            for b in WAR_ROOM_BUCKETS
        ],
        "kpis": {
            "total_pipeline": round(total_pipeline, 2),
            "weighted_pipeline": round(weighted_pipeline, 2),
            "at_risk_pipeline": round(at_risk_pipeline, 2),
            "inactive_pipeline": round(inactive_pipeline, 2),
            "total_leads": sum(len(bucket_map[bid]) for bid in bucket_map),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

# ----- WEEKLY REVIEW SESSIONS -----

# Phase 29.1: manual bucket override via drag-and-drop
class WarRoomBucketOverride(BaseModel):
    bucket: Optional[str] = None  # one of WAR_ROOM_BUCKETS ids, or None to clear

# Phase 29.3: saved views (named filter presets per user)
class WarRoomViewCreate(BaseModel):
    name: str
    hidden_buckets: List[str] = []
    owner_id: Optional[str] = None
    partner_id: Optional[str] = None
    category_id: Optional[str] = None
    min_value: Optional[float] = None

class WarRoomViewUpdate(BaseModel):
    name: Optional[str] = None
    hidden_buckets: Optional[List[str]] = None
    owner_id: Optional[str] = None
    partner_id: Optional[str] = None
    category_id: Optional[str] = None
    min_value: Optional[float] = None

@api_router.post("/war-room/views")
async def create_war_room_view(body: WarRoomViewCreate, current_user: dict = Depends(get_current_user)):
    """Create a saved War Room view (filter + bucket-visibility preset) for the current user."""
    if current_user['role'] == UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Not available for customers")
    name = (body.name or '').strip()[:80]
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    valid_bucket_ids = {b['id'] for b in WAR_ROOM_BUCKETS}
    hidden = [bid for bid in (body.hidden_buckets or []) if bid in valid_bucket_ids]

    # Enforce a per-user cap (gentle — keeps the dropdown tidy)
    existing_count = await db.war_room_views.count_documents({"user_id": current_user['id']})
    if existing_count >= 20:
        raise HTTPException(status_code=400, detail="Maximum 20 saved views per user — delete one first")

    view = {
        "id": str(uuid.uuid4()),
        "user_id": current_user['id'],
        "name": name,
        "hidden_buckets": hidden,
        "owner_id": body.owner_id,
        "partner_id": body.partner_id,
        "category_id": body.category_id,
        "min_value": body.min_value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.war_room_views.insert_one(view)
    view.pop('_id', None)
    return view

@api_router.get("/war-room/views")
async def list_war_room_views(current_user: dict = Depends(get_current_user)):
    """List the current user's saved views (newest first)."""
    if current_user['role'] == UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Not available for customers")
    views = await db.war_room_views.find(
        {"user_id": current_user['id']}, {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    return views

@api_router.patch("/war-room/views/{view_id}")
async def update_war_room_view(view_id: str, body: WarRoomViewUpdate, current_user: dict = Depends(get_current_user)):
    view = await db.war_room_views.find_one({"id": view_id, "user_id": current_user['id']}, {"_id": 0})
    if not view:
        raise HTTPException(status_code=404, detail="View not found")
    valid_bucket_ids = {b['id'] for b in WAR_ROOM_BUCKETS}
    update: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if body.name is not None:
        n = body.name.strip()[:80]
        if not n:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        update['name'] = n
    if body.hidden_buckets is not None:
        update['hidden_buckets'] = [bid for bid in body.hidden_buckets if bid in valid_bucket_ids]
    for f in ('owner_id', 'partner_id', 'category_id', 'min_value'):
        v = getattr(body, f)
        if v is not None or f in body.dict(exclude_unset=True):
            update[f] = v
    await db.war_room_views.update_one({"id": view_id}, {"$set": update})
    refreshed = await db.war_room_views.find_one({"id": view_id}, {"_id": 0})
    return refreshed

@api_router.delete("/war-room/views/{view_id}")
async def delete_war_room_view(view_id: str, current_user: dict = Depends(get_current_user)):
    res = await db.war_room_views.delete_one({"id": view_id, "user_id": current_user['id']})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="View not found")
    return {"ok": True}

@api_router.patch("/war-room/leads/{lead_id}/bucket")
async def override_war_room_bucket(
    lead_id: str, body: WarRoomBucketOverride, current_user: dict = Depends(get_current_user)
):
    """Manually pin a lead to a specific War Room bucket (e.g. via drag-and-drop).
    Pass bucket=None to clear the override and let the auto-classifier take over again.
    Honored by `_classify_war_room_bucket` unless the lead is won/lost."""
    if current_user['role'] == UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Not available for customers")

    valid_bucket_ids = {b['id'] for b in WAR_ROOM_BUCKETS}
    if body.bucket is not None and body.bucket not in valid_bucket_ids:
        raise HTTPException(status_code=400, detail=f"Invalid bucket id. Allowed: {sorted(valid_bucket_ids)}")

    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Lead-level RBAC: same rules as get_lead
    role = current_user.get('role')
    if role == UserRole.SELLING_PARTNER.value:
        if (lead.get('selling_partner_id') != current_user['id']
            and not any(p.get('partner_id') == current_user['id'] for p in (lead.get('assigned_partners') or []))):
            raise HTTPException(status_code=403, detail="Access denied")
    elif role == UserRole.SALES_ASSOCIATE.value and lead.get('sales_associate_id') != current_user['id']:
        raise HTTPException(status_code=403, detail="Access denied")

    now = datetime.now(timezone.utc).isoformat()
    if body.bucket is None:
        await db.leads.update_one(
            {"id": lead_id},
            {"$unset": {"war_room_bucket_override": "", "war_room_bucket_override_at": "", "war_room_bucket_override_by": ""},
             "$set": {"updated_at": now}}
        )
        return {"ok": True, "bucket": None, "cleared": True}

    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {
            "war_room_bucket_override": body.bucket,
            "war_room_bucket_override_at": now,
            "war_room_bucket_override_by": current_user['id'],
            "updated_at": now,
        }}
    )
    return {"ok": True, "bucket": body.bucket, "lead_id": lead_id}

# ----- WEEKLY REVIEW SESSIONS -----

class WarRoomSessionStart(BaseModel):
    title: Optional[str] = None

class WarRoomSessionNotesUpdate(BaseModel):
    notes: str

class WarRoomDiscussLead(BaseModel):
    lead_id: str
    note: Optional[str] = None

@api_router.post("/war-room/sessions/start")
async def start_war_room_session(body: WarRoomSessionStart, current_user: dict = Depends(get_current_user)):
    """Start a new Weekly Review session. Closes any open session from same user first."""
    if current_user['role'] == UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Not available for customers")
    # Close any open sessions from this user
    await db.war_room_sessions.update_many(
        {"started_by": current_user['id'], "ended_at": None},
        {"$set": {"ended_at": datetime.now(timezone.utc).isoformat(), "auto_closed": True}}
    )
    today = datetime.now(timezone.utc)
    iso_week = today.strftime("%Y-W%V")
    session = {
        "id": str(uuid.uuid4()),
        "title": (body.title or '').strip() or f"Weekly Review {iso_week}",
        "iso_week": iso_week,
        "started_by": current_user['id'],
        "started_by_name": current_user['name'],
        "started_at": today.isoformat(),
        "ended_at": None,
        "notes": "",
        "discussed_lead_ids": [],
        "discussion_notes": {},  # lead_id -> note
        "summary": None,
        "action_items": [],
    }
    await db.war_room_sessions.insert_one(session)
    session.pop('_id', None)
    return session

@api_router.get("/war-room/sessions/active")
async def get_active_war_room_session(current_user: dict = Depends(get_current_user)):
    """Return the current user's active (not-yet-ended) session if any."""
    if current_user['role'] == UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Not available for customers")
    s = await db.war_room_sessions.find_one(
        {"started_by": current_user['id'], "ended_at": None},
        {"_id": 0}
    )
    return s

@api_router.patch("/war-room/sessions/{session_id}/notes")
async def update_war_room_session_notes(session_id: str, body: WarRoomSessionNotesUpdate, current_user: dict = Depends(get_current_user)):
    session = await db.war_room_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session['started_by'] != current_user['id'] and current_user.get('role') != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Not authorized")
    if session.get('ended_at'):
        raise HTTPException(status_code=400, detail="Session already ended")
    await db.war_room_sessions.update_one(
        {"id": session_id},
        {"$set": {"notes": (body.notes or '')[:20000]}}
    )
    return {"ok": True}

@api_router.post("/war-room/sessions/{session_id}/discuss")
async def discuss_lead_in_session(session_id: str, body: WarRoomDiscussLead, current_user: dict = Depends(get_current_user)):
    """Mark a lead as discussed in this session, optionally with a per-lead note."""
    session = await db.war_room_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session['started_by'] != current_user['id'] and current_user.get('role') != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Not authorized")
    if session.get('ended_at'):
        raise HTTPException(status_code=400, detail="Session already ended")
    update = {}
    if body.lead_id not in (session.get('discussed_lead_ids') or []):
        update["$addToSet"] = {"discussed_lead_ids": body.lead_id}
    if body.note:
        notes_map = session.get('discussion_notes') or {}
        notes_map[body.lead_id] = (body.note or '').strip()[:2000]
        update.setdefault("$set", {})["discussion_notes"] = notes_map
    if update:
        await db.war_room_sessions.update_one({"id": session_id}, update)
    return {"ok": True}

@api_router.post("/war-room/sessions/{session_id}/end")
async def end_war_room_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """End the session and generate AI summary + extract action items into Tasks."""
    session = await db.war_room_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session['started_by'] != current_user['id'] and current_user.get('role') != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Not authorized")
    if session.get('ended_at'):
        return session  # idempotent

    # Gather context for the AI: discussed leads + session notes + per-lead notes
    discussed_ids = session.get('discussed_lead_ids') or []
    discussion_notes = session.get('discussion_notes') or {}
    leads_brief: List[str] = []
    if discussed_ids:
        leads = await db.leads.find({"id": {"$in": discussed_ids}}, {"_id": 0}).to_list(200)
        statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
        smap = {s['id']: s for s in statuses}
        for ld in leads:
            st = smap.get(ld.get('status_id') or '') or {}
            line = f"- {ld.get('title','Untitled')} ({ld.get('customer_company','')}, ₹{ld.get('deal_value') or 0:,.0f}, stage: {st.get('name','?')})"
            note = discussion_notes.get(ld['id'])
            if note:
                line += f" — note: {note}"
            leads_brief.append(line)

    summary_payload = {
        "leads_progressed": [],
        "high_risk_leads": [],
        "blocked_opportunities": [],
        "revenue_updates": "",
        "partner_dependencies": [],
        "action_items": [],
        "upcoming_followups": [],
        "executive_summary": "",
    }

    if EMERGENT_LLM_KEY:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: WPS433
            sys_msg = (
                "You are an expert sales operations analyst summarizing a weekly review meeting. "
                "Given the meeting notes + list of leads discussed, output STRICT valid JSON with this shape — no markdown, no preamble, no trailing text:\n"
                "{\"executive_summary\": str (2-3 sentences), \"leads_progressed\": [str], \"high_risk_leads\": [str], "
                "\"blocked_opportunities\": [str], \"revenue_updates\": str, \"partner_dependencies\": [str], "
                "\"action_items\": [{\"action\": str, \"owner\": str|null, \"due_date\": YYYY-MM-DD|null, \"lead_hint\": str|null}], "
                "\"upcoming_followups\": [str]}.\n"
                "For action_items, parse statements like 'Hardik to send proposal by Thursday' into {action, owner, due_date}. "
                "If owner is unclear, set null. Convert relative dates ('Thursday', 'next week') to absolute YYYY-MM-DD assuming today is "
                f"{datetime.now(timezone.utc).date().isoformat()}. "
                "Be concise — each list item ≤ 100 chars. Output JSON ONLY."
            )
            prompt = (
                f"Meeting title: {session.get('title','Weekly Review')}\n"
                f"Started by: {session.get('started_by_name','')}\n\n"
                f"Leads discussed ({len(leads_brief)}):\n" + ("\n".join(leads_brief) or '(none)') + "\n\n"
                f"Meeting notes:\n{session.get('notes','') or '(none)'}"
            )
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"war-room-{session_id}",
                system_message=sys_msg,
            ).with_model("gemini", "gemini-3.1-pro-preview")
            raw = await chat.send_message(UserMessage(text=prompt))
            raw = (raw or '').strip().strip('`')
            if raw.lower().startswith('json'):
                raw = raw[4:].strip()
            try:
                parsed = json.loads(raw)
                for k in summary_payload:
                    if k in parsed:
                        summary_payload[k] = parsed[k]
            except json.JSONDecodeError as je:
                logger.warning(f"War room AI summary JSON parse failed: {je}; raw={raw[:200]}")
                summary_payload['executive_summary'] = raw[:500]
        except Exception as e:
            logger.warning(f"War room AI summary failed: {e}")
            summary_payload['executive_summary'] = "AI summary unavailable for this session."

    # Materialize action_items into Tasks (best-effort attribution to the user)
    user_lookup: Dict[str, str] = {}
    users = await db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(500)
    for u in users:
        user_lookup[u.get('name', '').lower().strip()] = u['id']
        if u.get('email'):
            user_lookup[u['email'].lower().strip()] = u['id']

    materialized_tasks: List[dict] = []
    for ai in (summary_payload.get('action_items') or []):
        if not isinstance(ai, dict):
            continue
        owner_id = None
        owner_name = ai.get('owner')
        if owner_name:
            owner_id = user_lookup.get((owner_name or '').lower().strip())
        # Try to attach a lead — if lead_hint matches a discussed lead title, pick it
        lead_id_match = None
        hint = (ai.get('lead_hint') or '').lower().strip()
        if hint and discussed_ids:
            for ld_id in discussed_ids:
                ld = await db.leads.find_one({"id": ld_id}, {"_id": 0, "title": 1, "customer_company": 1})
                if not ld:
                    continue
                if hint in (ld.get('title', '').lower()) or hint in (ld.get('customer_company', '').lower()):
                    lead_id_match = ld_id
                    break
        task = {
            "id": str(uuid.uuid4()),
            "title": (ai.get('action') or '').strip()[:300] or 'War Room action item',
            "description": f"Auto-extracted from Weekly Review session: {session.get('title')}",
            "assignee_id": owner_id or current_user['id'],
            "lead_id": lead_id_match,
            "commercial_id": None,
            "due_date": ai.get('due_date'),
            "priority": "high",
            "status": "todo",
            "created_by": current_user['id'],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "source": "war_room_session",
            "source_session_id": session_id,
        }
        await db.tasks.insert_one(task)
        task.pop('_id', None)
        materialized_tasks.append(task)
        # Notify the assignee
        if owner_id and owner_id != current_user['id']:
            try:
                await create_notification(
                    user_id=owner_id,
                    title=f"New task from Weekly Review · {session.get('title')}",
                    message=task['title'],
                    notification_type=NotificationType.LEAD_MENTION,
                    lead_id=lead_id_match,
                )
            except Exception:
                pass

    ended_at = datetime.now(timezone.utc).isoformat()
    await db.war_room_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "ended_at": ended_at,
            "summary": summary_payload,
            "materialized_task_ids": [t['id'] for t in materialized_tasks],
            "materialized_task_count": len(materialized_tasks),
        }}
    )
    session['ended_at'] = ended_at
    session['summary'] = summary_payload
    session['materialized_task_ids'] = [t['id'] for t in materialized_tasks]
    session['materialized_task_count'] = len(materialized_tasks)
    return session

@api_router.get("/war-room/sessions")
async def list_war_room_sessions(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """List recent sessions. Admin sees all; partner/associate sees their own."""
    if current_user['role'] == UserRole.CUSTOMER.value:
        raise HTTPException(status_code=403, detail="Not available for customers")
    q: Dict[str, Any] = {}
    if current_user['role'] != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops'):
        q['started_by'] = current_user['id']
    sessions = await db.war_room_sessions.find(q, {"_id": 0}).sort("started_at", -1).limit(min(50, max(1, limit))).to_list(50)
    return sessions

@api_router.get("/war-room/sessions/{session_id}")
async def get_war_room_session(session_id: str, current_user: dict = Depends(get_current_user)):
    session = await db.war_room_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if (session['started_by'] != current_user['id']
        and current_user.get('role') != UserRole.SUPER_ADMIN.value
        and not current_user.get('is_vyapaar_ops')):
        raise HTTPException(status_code=403, detail="Not authorized")
    return session


@api_router.get("/leads/{lead_id}/stakeholders")
async def list_stakeholders(lead_id: str, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead.get('stakeholders') or []

@api_router.post("/leads/{lead_id}/stakeholders")
async def add_stakeholder(lead_id: str, body: StakeholderCreate, current_user: dict = Depends(get_current_user)):
    if body.role_type not in VALID_STAKEHOLDER_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role_type. Must be one of {sorted(VALID_STAKEHOLDER_ROLES)}")
    if body.engagement not in VALID_ENGAGEMENT:
        raise HTTPException(status_code=400, detail="Invalid engagement")
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    stakeholder = {
        "id": str(uuid.uuid4()),
        **body.dict(),
        "created_by": current_user['id'],
        "created_by_name": current_user['name'],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.leads.update_one(
        {"id": lead_id},
        {"$push": {"stakeholders": stakeholder}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return stakeholder

@api_router.patch("/leads/{lead_id}/stakeholders/{stakeholder_id}")
async def update_stakeholder(lead_id: str, stakeholder_id: str, body: StakeholderUpdate, current_user: dict = Depends(get_current_user)):
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    stakeholders = lead.get('stakeholders') or []
    updated = None
    for s in stakeholders:
        if s['id'] == stakeholder_id:
            for k, v in body.dict(exclude_unset=True).items():
                if v is None:
                    continue
                if k == 'role_type' and v not in VALID_STAKEHOLDER_ROLES:
                    raise HTTPException(status_code=400, detail="Invalid role_type")
                if k == 'engagement' and v not in VALID_ENGAGEMENT:
                    raise HTTPException(status_code=400, detail="Invalid engagement")
                s[k] = v
            s['updated_at'] = datetime.now(timezone.utc).isoformat()
            updated = s
            break
    if not updated:
        raise HTTPException(status_code=404, detail="Stakeholder not found")
    await db.leads.update_one({"id": lead_id}, {"$set": {"stakeholders": stakeholders, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return updated

@api_router.delete("/leads/{lead_id}/stakeholders/{stakeholder_id}")
async def delete_stakeholder(lead_id: str, stakeholder_id: str, current_user: dict = Depends(get_current_user)):
    res = await db.leads.update_one(
        {"id": lead_id},
        {"$pull": {"stakeholders": {"id": stakeholder_id}}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Stakeholder not found")
    return {"deleted": True}

# ==================== PHASE 2: SMART NOTIFICATIONS ENGINE ====================

@api_router.post("/notifications/run-rules")
async def run_smart_notification_rules(current_user: dict = Depends(get_current_user)):
    """Manually-triggered smart-rules evaluator. Iterates over all active leads and emits
    in-app notifications for triggered rules (with dedup so re-runs don't spam).

    Rules:
      R1: Lead inactive 10+ days → notify the owner (created_by) and assigned partners
      R2: Proposal pending follow-up — Lead is in 'Proposal' status with overdue follow-up
      R3: High-value lead (>=10L) gone at-risk → notify admins
    """
    if current_user['role'] not in (UserRole.SUPER_ADMIN.value,) and not current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Admin only")

    today = datetime.now(timezone.utc).date()
    today_iso = today.isoformat()
    leads = await db.leads.find({}, {"_id": 0}).to_list(2000)
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}

    fired = []
    for lead in leads:
        st = status_map.get(lead.get('status_id') or '') or {}
        if st.get('is_won') or st.get('is_lost'):
            continue

        lead_for_h = {**lead}
        lead_for_h['active_partners_count'] = len([p for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active'])
        lead_for_h['status_is_won'] = bool(st.get('is_won'))
        h = compute_lead_health(lead_for_h)
        days_inactive = h.get('days_inactive') or 0

        recipients = set()
        if lead.get('created_by'):
            recipients.add(lead['created_by'])
        for p in (lead.get('assigned_partners') or []):
            if p.get('status') == 'active' and p.get('partner_id'):
                recipients.add(p['partner_id'])

        # R1 — inactive 10+ days
        if days_inactive >= 10:
            for uid in recipients:
                dedup_key = f"rule-r1-{lead['id']}-{today_iso}"
                exists = await db.notifications.find_one({"user_id": uid, "data.dedup_key": dedup_key})
                if exists:
                    continue
                await create_notification(
                    user_id=uid,
                    notification_type="rule_lead_inactive",
                    title=f"Lead quiet for {int(days_inactive)} days",
                    message=f"\"{lead.get('title', '')}\" hasn't seen activity in {int(days_inactive)} days. Reach out today.",
                    lead_id=lead['id'],
                    data={"dedup_key": dedup_key, "rule": "R1"},
                )
                fired.append({"rule": "R1", "lead_id": lead['id'], "user_id": uid})

        # R2 — proposal stage + overdue follow-up
        if 'proposal' in (st.get('name') or '').lower():
            overdue_count = sum(
                1 for f in (lead.get('follow_ups') or [])
                if not f.get('is_completed') and (f.get('scheduled_date') or '') < today_iso
            )
            if overdue_count > 0:
                for uid in recipients:
                    dedup_key = f"rule-r2-{lead['id']}-{today_iso}"
                    exists = await db.notifications.find_one({"user_id": uid, "data.dedup_key": dedup_key})
                    if exists:
                        continue
                    await create_notification(
                        user_id=uid,
                        notification_type="rule_proposal_pending",
                        title=f"Proposal pending follow-up",
                        message=f"\"{lead.get('title', '')}\" is in Proposal stage with {overdue_count} overdue follow-up(s).",
                        lead_id=lead['id'],
                        data={"dedup_key": dedup_key, "rule": "R2"},
                    )
                    fired.append({"rule": "R2", "lead_id": lead['id'], "user_id": uid})

        # R3 — high value at risk
        if float(lead.get('deal_value') or 0) >= 1_000_000 and h['band'] == 'at_risk':
            admins = await db.users.find(
                {"$or": [{"role": "super_admin"}, {"is_vyapaar_ops": True}]},
                {"_id": 0, "id": 1}
            ).to_list(50)
            for admin in admins:
                dedup_key = f"rule-r3-{lead['id']}-{today_iso}"
                exists = await db.notifications.find_one({"user_id": admin['id'], "data.dedup_key": dedup_key})
                if exists:
                    continue
                await create_notification(
                    user_id=admin['id'],
                    notification_type="rule_high_value_at_risk",
                    title=f"High-value deal at risk",
                    message=f"\"{lead.get('title', '')}\" (₹{lead.get('deal_value'):,}) has dropped to At Risk. Engage immediately.",
                    lead_id=lead['id'],
                    data={"dedup_key": dedup_key, "rule": "R3"},
                )
                fired.append({"rule": "R3", "lead_id": lead['id'], "user_id": admin['id']})

    return {"fired_count": len(fired), "events": fired[:50]}

# ==================== PHASE 3: AI DEAL RISK + AI FOLLOW-UP ASSISTANT ====================

def _build_lead_ai_context(lead: dict, status_map: dict) -> str:
    """Compose a rich text context block for the LLM from a lead document."""
    st = status_map.get(lead.get('status_id') or '') or {}
    status_name = st.get('name', 'Unstaged')
    deal_value = float(lead.get('deal_value') or 0)
    lead_for_h = {**lead, 'active_partners_count': len([p for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active']), 'status_is_won': bool(st.get('is_won'))}
    h = compute_lead_health(lead_for_h)

    follow_ups = lead.get('follow_ups') or []
    today_iso = datetime.now(timezone.utc).date().isoformat()
    overdue = [f for f in follow_ups if not f.get('is_completed') and (f.get('scheduled_date') or '') < today_iso]
    pending = [f for f in follow_ups if not f.get('is_completed') and not ((f.get('scheduled_date') or '') < today_iso)]
    completed = [f for f in follow_ups if f.get('is_completed')]

    last_comments = (lead.get('comments') or [])[-5:]
    summaries = (lead.get('meeting_summaries') or [])[-2:]
    stakeholders = lead.get('stakeholders') or []
    partners = [p for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active']

    blocks = []
    blocks.append(f"Lead: {lead.get('title','')}  |  Status: {status_name}  |  Deal: ₹{deal_value:,.0f}")
    blocks.append(f"Customer: {lead.get('customer_name','')} @ {lead.get('customer_company','')}")
    blocks.append(f"Health: {h['band']} ({h['score']}/100). Days inactive: {h.get('days_inactive')}")
    blocks.append(f"Follow-ups: {len(overdue)} overdue, {len(pending)} pending, {len(completed)} completed")
    if partners:
        blocks.append(f"Active partners: " + ", ".join(p.get('partner_name', '') for p in partners))

    if stakeholders:
        blocks.append("\nStakeholders:")
        for s in stakeholders[:8]:
            blocks.append(f"  - {s.get('name','')} ({s.get('role_type','')}, engagement={s.get('engagement','neutral')}){' — '+s.get('notes') if s.get('notes') else ''}")
    else:
        blocks.append("\nStakeholders: NONE MAPPED (this is a risk signal — buyer-side relationships are not understood)")

    if summaries:
        blocks.append("\nRecent meeting summaries:")
        for s in summaries:
            blocks.append(f"  - [{s.get('meeting_date','?')}] sentiment={s.get('sentiment','?')}: {s.get('summary','')[:240]}")
            if s.get('risks'):
                blocks.append(f"      risks: {' · '.join(s['risks'][:3])}")

    if last_comments:
        blocks.append("\nRecent comments:")
        for c in last_comments:
            blocks.append(f"  - [{c.get('created_at','')[:10]}] {c.get('user_name','')}: {c.get('content','')[:200]}")

    return "\n".join(blocks)

async def _ai_lead_chat(lead_id: str, system_msg: str, user_prompt: str) -> dict:
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=503, detail="LLM key not configured")
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: WPS433
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"ai-lead-{lead_id}-{uuid.uuid4()}",
        system_message=system_msg,
    ).with_model("gemini", "gemini-3.1-pro-preview")
    try:
        raw = await chat.send_message(UserMessage(text=user_prompt))
    except Exception as e:
        logger.exception(f"LLM error: {e}")
        raise HTTPException(status_code=502, detail=f"AI request failed: {str(e)[:120]}")
    text = (raw or '').strip()
    if text.startswith('```'):
        text = text.strip('`')
        if text.lower().startswith('json'):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if not m:
            raise HTTPException(status_code=502, detail="AI returned non-JSON output")
        try:
            return json.loads(m.group(0))
        except Exception:
            raise HTTPException(status_code=502, detail="AI returned malformed JSON")

@api_router.post("/leads/{lead_id}/ai/risk-analysis")
async def ai_deal_risk(lead_id: str, current_user: dict = Depends(get_current_user)):
    """AI-driven deal risk analysis. Considers inactivity, sentiment from meeting summaries,
    stakeholder gaps, follow-up health, and deal-value tier to compute a risk score + factors
    + mitigations. Stored on the lead under `ai_risk_analysis`."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}

    context = _build_lead_ai_context(lead, status_map)
    system_msg = (
        "You are a senior B2B sales risk analyst. Analyze the provided lead context and return STRICT JSON only. "
        "No prose, no markdown, no code fences. Schema:\n"
        "{\n"
        '  "risk_score": 0-100 integer (higher = more risk),\n'
        '  "risk_level": one of [low, medium, high, critical],\n'
        '  "closure_probability": 0-100 integer (likelihood deal closes won),\n'
        '  "top_risk_factors": array of {factor: string, severity: low|medium|high, evidence: string},\n'
        '  "stakeholder_gaps": array of strings (e.g. "No champion identified", "Finance approver missing"),\n'
        '  "recommended_mitigations": array of strings (1-line specific actions),\n'
        '  "early_warning_signals": array of strings,\n'
        '  "confidence": 0-100 integer (how confident is the model given available data)\n'
        "}\n"
        "Be specific. Use the actual lead details, NOT generic advice. Penalize stakeholder gaps and inactivity hard. "
        "If meeting sentiment was negative, raise risk. If a champion is supportive, lower risk."
    )
    parsed = await _ai_lead_chat(lead_id, system_msg, f"Lead context:\n{context}\n\nReturn STRICT JSON only.")

    # Normalize and store
    result = {
        "risk_score": int(parsed.get('risk_score') or 50),
        "risk_level": (parsed.get('risk_level') or 'medium').lower(),
        "closure_probability": int(parsed.get('closure_probability') or 30),
        "top_risk_factors": (parsed.get('top_risk_factors') or [])[:6],
        "stakeholder_gaps": [str(x) for x in (parsed.get('stakeholder_gaps') or [])][:6],
        "recommended_mitigations": [str(x) for x in (parsed.get('recommended_mitigations') or [])][:6],
        "early_warning_signals": [str(x) for x in (parsed.get('early_warning_signals') or [])][:6],
        "confidence": int(parsed.get('confidence') or 60),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": current_user['name'],
    }
    if result['risk_level'] not in ('low', 'medium', 'high', 'critical'):
        result['risk_level'] = 'medium'
    for v in ('risk_score', 'closure_probability', 'confidence'):
        result[v] = max(0, min(100, result[v]))

    await db.leads.update_one({"id": lead_id}, {"$set": {"ai_risk_analysis": result, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return result

@api_router.post("/leads/{lead_id}/ai/follow-up-suggestion")
async def ai_followup_suggestion(lead_id: str, current_user: dict = Depends(get_current_user)):
    """AI Follow-up Assistant. Returns the recommended next action, optimal timing,
    a ready-to-send conversation starter, and (if applicable) a proposal recommendation."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}

    context = _build_lead_ai_context(lead, status_map)
    system_msg = (
        "You are a senior B2B sales playbook strategist. Given the lead context, recommend the single best next move. "
        "Return STRICT JSON only. Schema:\n"
        "{\n"
        '  "recommended_action": string (clear, specific verb-led next step),\n'
        '  "rationale": string (1-2 sentences explaining WHY based on the lead context),\n'
        '  "suggested_timing": {when: string e.g. "tomorrow morning"|"next Monday", reason: string},\n'
        '  "channel": one of [email, call, whatsapp, meeting, slack],\n'
        '  "conversation_starter": string (a ready-to-send opening line, 2-3 sentences, professional but warm),\n'
        '  "proposal_recommendation": optional string (only if proposal stage),\n'
        '  "stakeholders_to_loop_in": array of strings (names from the stakeholder list),\n'
        '  "questions_to_ask": array of 2-3 questions to learn more,\n'
        '  "confidence": 0-100 integer\n'
        "}\n"
        "Be specific. If you see meeting summaries, reference what was discussed. "
        "If a stakeholder is resistant, propose how to handle them. If a champion exists, leverage them. "
        "Do NOT use placeholder names like [Customer Name]; use the actual names from the context."
    )
    parsed = await _ai_lead_chat(lead_id, system_msg, f"Lead context:\n{context}\n\nReturn STRICT JSON only.")

    result = {
        "recommended_action": str(parsed.get('recommended_action') or '').strip()[:300],
        "rationale": str(parsed.get('rationale') or '').strip()[:600],
        "suggested_timing": parsed.get('suggested_timing') or {"when": "today", "reason": ""},
        "channel": (parsed.get('channel') or 'email').lower(),
        "conversation_starter": str(parsed.get('conversation_starter') or '').strip()[:1500],
        "proposal_recommendation": str(parsed.get('proposal_recommendation') or '').strip()[:500] or None,
        "stakeholders_to_loop_in": [str(x) for x in (parsed.get('stakeholders_to_loop_in') or [])][:5],
        "questions_to_ask": [str(x) for x in (parsed.get('questions_to_ask') or [])][:5],
        "confidence": max(0, min(100, int(parsed.get('confidence') or 70))),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": current_user['name'],
    }
    if result['channel'] not in ('email', 'call', 'whatsapp', 'meeting', 'slack'):
        result['channel'] = 'email'
    return result

# ==================== PHASE 3: AI COMMAND BAR ====================

class CommandQueryRequest(BaseModel):
    query: str

@api_router.post("/ai/command")
async def ai_command_bar(body: CommandQueryRequest, current_user: dict = Depends(get_current_user)):
    """Natural-language CRM query. Gemini converts the prompt to a structured filter spec
    (whitelisted fields), then we apply it server-side. The LLM NEVER touches raw Mongo.
    """
    q = (body.query or '').strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query is required")
    if len(q) > 500:
        raise HTTPException(status_code=400, detail="Query too long")

    # First — list available statuses + categories + partners so the AI can ground its filters
    statuses = await db.lead_statuses.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
    primary_cats = await db.primary_categories.find({}, {"_id": 0, "name": 1}).to_list(100)
    partners = await db.users.find({"role": "selling_partner", "is_active": True}, {"_id": 0, "name": 1, "company_name": 1}).to_list(200)

    grounding = (
        "Available lead statuses: " + ", ".join([s['name'] for s in statuses][:30]) + "\n"
        "Available categories: " + ", ".join([c['name'] for c in primary_cats][:30]) + "\n"
        "Sample selling partners: " + ", ".join([p['name'] for p in partners][:15])
    )

    system_msg = (
        "You are a CRM query parser. Convert the user's natural-language question into a STRICT JSON filter spec. "
        "Return ONLY the JSON object, no prose, no markdown, no code fences.\n"
        "Schema:\n"
        "{\n"
        '  "intent": one of [search_leads, get_at_risk, top_partners, stats, help, unknown],\n'
        '  "filters": {\n'
        '    "status_name_contains": optional string,\n'
        '    "primary_category_contains": optional string,\n'
        '    "partner_name_contains": optional string,\n'
        '    "customer_name_contains": optional string,\n'
        '    "customer_company_contains": optional string,\n'
        '    "health_bands": optional array (subset of [hot, warm, cold, at_risk]),\n'
        '    "min_deal_value": optional number,\n'
        '    "max_deal_value": optional number,\n'
        '    "days_inactive_min": optional number,\n'
        '    "days_inactive_max": optional number,\n'
        '    "is_won": optional boolean,\n'
        '    "is_lost": optional boolean,\n'
        '    "limit": integer default 20 max 50\n'
        '  },\n'
        '  "summary": string (1 sentence describing what we will show),\n'
        '  "suggested_followups": array of up to 3 strings (other queries the user might want)\n'
        "}\n"
        "Use null or omit fields the user did not specify. Map words to filters:\n"
        "  'hot/warm/cold/at risk' → health_bands; 'won deals' → is_won=true; 'lost' → is_lost=true; "
        "'big/large/high-value' → min_deal_value=100000 (1 lakh); 'inactive/stale/cold for X days' → days_inactive_min=X.\n"
        f"Grounding (use these EXACT strings if matched in the user query):\n{grounding}"
    )

    parsed = await _ai_lead_chat("command-" + str(uuid.uuid4())[:8], system_msg, f"User query: {q}\n\nReturn STRICT JSON only.")

    filters = parsed.get('filters') or {}
    intent = (parsed.get('intent') or 'search_leads').lower()
    if intent not in ('search_leads', 'get_at_risk', 'top_partners', 'stats', 'help', 'unknown'):
        intent = 'search_leads'
    summary = str(parsed.get('summary') or '').strip()[:300]
    suggested = [str(x) for x in (parsed.get('suggested_followups') or [])][:3]
    limit = int(filters.get('limit') or 20)
    limit = max(1, min(50, limit))

    # Apply server-side filtering against the leads collection (role-scoped)
    lead_query: Dict[str, Any] = {}
    if current_user['role'] == UserRole.SELLING_PARTNER.value:
        lead_query['selling_partner_id'] = current_user['id']
    elif current_user['role'] == UserRole.SALES_ASSOCIATE.value:
        lead_query['sales_associate_id'] = current_user['id']
    elif current_user['role'] == UserRole.CUSTOMER.value:
        lead_query['created_by'] = current_user['id']

    def _ci_regex(val: str) -> Dict[str, str]:
        return {"$regex": re.escape(val.strip()), "$options": "i"}

    if filters.get('customer_name_contains'):
        lead_query['customer_name'] = _ci_regex(filters['customer_name_contains'])
    if filters.get('customer_company_contains'):
        lead_query['customer_company'] = _ci_regex(filters['customer_company_contains'])
    if filters.get('partner_name_contains'):
        lead_query['selling_partner_name'] = _ci_regex(filters['partner_name_contains'])
    if filters.get('primary_category_contains'):
        lead_query['primary_category_name'] = _ci_regex(filters['primary_category_contains'])

    # Status filter — match name
    if filters.get('status_name_contains'):
        matched = [s['id'] for s in statuses if filters['status_name_contains'].lower() in (s.get('name') or '').lower()]
        if matched:
            lead_query['status_id'] = {"$in": matched}

    # is_won / is_lost via status_map
    if filters.get('is_won') is True:
        won_ids = []
        all_st = await db.lead_statuses.find({"is_won": True}, {"_id": 0, "id": 1}).to_list(50)
        won_ids = [s['id'] for s in all_st]
        if won_ids:
            lead_query['status_id'] = {"$in": won_ids}
    elif filters.get('is_lost') is True:
        all_st = await db.lead_statuses.find({"is_lost": True}, {"_id": 0, "id": 1}).to_list(50)
        lost_ids = [s['id'] for s in all_st]
        if lost_ids:
            lead_query['status_id'] = {"$in": lost_ids}

    # Deal value bounds
    if filters.get('min_deal_value') is not None or filters.get('max_deal_value') is not None:
        cond = {}
        if filters.get('min_deal_value') is not None:
            cond["$gte"] = float(filters['min_deal_value'])
        if filters.get('max_deal_value') is not None:
            cond["$lte"] = float(filters['max_deal_value'])
        lead_query['deal_value'] = cond

    raw_leads = await db.leads.find(lead_query, {"_id": 0}).sort("updated_at", -1).to_list(500)

    # Post-filter by health band + days_inactive (computed in Python)
    health_bands_filter = set([str(x).lower() for x in (filters.get('health_bands') or [])])
    days_min = filters.get('days_inactive_min')
    days_max = filters.get('days_inactive_max')

    status_full = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map_full = {s['id']: s for s in status_full}

    results = []
    for lead in raw_leads:
        st = status_map_full.get(lead.get('status_id') or '') or {}
        lead['active_partners_count'] = len([p for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active'])
        lead['status_is_won'] = bool(st.get('is_won'))
        h = compute_lead_health(lead)
        if health_bands_filter and h['band'] not in health_bands_filter:
            continue
        di = h.get('days_inactive')
        if days_min is not None and (di is None or di < float(days_min)):
            continue
        if days_max is not None and (di is None or di > float(days_max)):
            continue
        if intent == 'get_at_risk' and h['band'] != 'at_risk':
            continue
        results.append({
            "id": lead['id'],
            "title": lead.get('title'),
            "customer_name": lead.get('customer_name'),
            "customer_company": lead.get('customer_company'),
            "status_name": st.get('name'),
            "status_color": st.get('color', '#6366F1'),
            "deal_value": lead.get('deal_value') or 0,
            "primary_category_name": lead.get('primary_category_name'),
            "selling_partner_name": lead.get('selling_partner_name'),
            "health": {"score": h['score'], "band": h['band'], "days_inactive": h.get('days_inactive')},
        })
        if len(results) >= limit:
            break

    return {
        "intent": intent,
        "filters": filters,
        "summary": summary or f"Found {len(results)} lead(s) matching your query",
        "suggested_followups": suggested,
        "results": results,
        "count": len(results),
    }

# ==================== PHASE 3: PARTNER INTELLIGENCE LAYER ====================

@api_router.get("/dashboard/partner-intelligence")
async def partner_intelligence(current_user: dict = Depends(get_current_user)):
    """Phase 3: Partner Intelligence dashboard.

    Returns leaderboard (composite score), conversion funnel, category strength matrix,
    pipeline-per-partner, and average deal cycle time.
    """
    if current_user['role'] not in (UserRole.SUPER_ADMIN.value,) and not current_user.get('is_vyapaar_ops') and current_user['role'] != UserRole.SELLING_PARTNER.value:
        raise HTTPException(status_code=403, detail="Not authorized")

    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}

    partners = await db.users.find({"role": "selling_partner", "is_active": True}, {"_id": 0}).to_list(500)
    partner_by_id = {p['id']: p for p in partners}
    leads = await db.leads.find({}, {"_id": 0}).to_list(5000)

    # Aggregations
    by_partner: Dict[str, Dict[str, Any]] = {}
    cat_matrix: Dict[str, Dict[str, int]] = {}  # partner_id -> {category: won_count}

    today = datetime.now(timezone.utc).date()

    for lead in leads:
        st = status_map.get(lead.get('status_id') or '') or {}
        is_won = bool(st.get('is_won'))
        is_lost = bool(st.get('is_lost'))
        is_closed = is_won or is_lost

        # Determine all partner IDs touching this lead (active + historical)
        partner_ids = set()
        if lead.get('selling_partner_id'):
            partner_ids.add(lead['selling_partner_id'])
        for ap in (lead.get('assigned_partners') or []):
            if ap.get('partner_id'):
                partner_ids.add(ap['partner_id'])

        for pid in partner_ids:
            if pid not in by_partner:
                p = partner_by_id.get(pid) or {}
                by_partner[pid] = {
                    "partner_id": pid,
                    "partner_name": p.get('name') or 'Unknown',
                    "company_name": p.get('company_name'),
                    "assigned": 0, "engaged": 0, "won": 0, "lost": 0,
                    "open_pipeline": 0.0, "won_revenue": 0.0,
                    "cycle_days_sum": 0.0, "cycle_days_count": 0,
                    "avg_deal_size": 0.0,
                }
            entry = by_partner[pid]
            entry['assigned'] += 1
            if len(lead.get('comments') or []) + len(lead.get('follow_ups') or []) > 0:
                entry['engaged'] += 1
            deal_value = float(lead.get('deal_value') or 0)
            if is_won:
                entry['won'] += 1
                entry['won_revenue'] += deal_value
                # Cycle days = (status updated_at) - created_at
                try:
                    created = datetime.fromisoformat((lead.get('created_at') or '').replace('Z', '+00:00'))
                    closed = datetime.fromisoformat((lead.get('updated_at') or '').replace('Z', '+00:00'))
                    cycle = (closed - created).total_seconds() / 86400
                    if 0 <= cycle <= 730:
                        entry['cycle_days_sum'] += cycle
                        entry['cycle_days_count'] += 1
                except Exception:
                    pass
                # Category matrix
                cat = lead.get('primary_category_name') or 'Uncategorized'
                cat_matrix.setdefault(pid, {})[cat] = cat_matrix.get(pid, {}).get(cat, 0) + 1
            elif is_lost:
                entry['lost'] += 1
            else:
                entry['open_pipeline'] += deal_value

    # Compute composite scores
    leaderboard = []
    for pid, e in by_partner.items():
        closed = e['won'] + e['lost']
        win_rate = (e['won'] / closed * 100) if closed > 0 else 0
        avg_cycle = (e['cycle_days_sum'] / e['cycle_days_count']) if e['cycle_days_count'] > 0 else None
        avg_deal_size = (e['won_revenue'] / e['won']) if e['won'] > 0 else 0
        # Composite: 40% won_revenue (normalized), 30% win_rate, 20% engagement, 10% speed
        revenue_score = min(100, (e['won_revenue'] / 1_000_000) * 10) if e['won_revenue'] else 0
        engagement_pct = (e['engaged'] / e['assigned'] * 100) if e['assigned'] > 0 else 0
        speed_score = 0
        if avg_cycle is not None:
            speed_score = max(0, min(100, 100 - (avg_cycle / 0.9)))  # ~90 days = 0pts
        composite = round((revenue_score * 0.4) + (win_rate * 0.3) + (engagement_pct * 0.2) + (speed_score * 0.1), 1)
        leaderboard.append({
            **e,
            "win_rate": round(win_rate, 1),
            "avg_cycle_days": round(avg_cycle, 1) if avg_cycle else None,
            "avg_deal_size": round(avg_deal_size, 0),
            "engagement_pct": round(engagement_pct, 1),
            "composite_score": composite,
        })
    leaderboard.sort(key=lambda x: -x['composite_score'])

    # Build top categories per partner (for the matrix heatmap)
    top_categories: Dict[str, List[Dict[str, Any]]] = {}
    for pid, cats in cat_matrix.items():
        top_categories[pid] = sorted(
            [{"category": c, "won_count": n} for c, n in cats.items()],
            key=lambda x: -x['won_count']
        )[:5]

    # Health summary
    total_partners = len(partners)
    active_partners = sum(1 for e in leaderboard if e['assigned'] > 0)

    return {
        "kpis": {
            "total_partners": total_partners,
            "active_partners": active_partners,
            "total_won_revenue": round(sum(e['won_revenue'] for e in leaderboard), 2),
            "avg_win_rate": round(
                sum(e['win_rate'] for e in leaderboard if e['won'] + e['lost'] > 0)
                / max(1, sum(1 for e in leaderboard if e['won'] + e['lost'] > 0)),
                1
            ),
        },
        "leaderboard": leaderboard,
        "top_categories": top_categories,
    }

@api_router.post("/partners/{partner_id}/ai/coaching")
async def ai_partner_coaching(partner_id: str, current_user: dict = Depends(get_current_user)):
    """Generate AI coaching tips for a selling partner using their historical performance."""
    if current_user['role'] != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Admin only")

    partner = await db.users.find_one({"id": partner_id, "role": "selling_partner"}, {"_id": 0})
    if not partner:
        raise HTTPException(status_code=404, detail="Selling partner not found")

    statuses = await db.lead_statuses.find({}, {"_id": 0}).to_list(200)
    status_map = {s['id']: s for s in statuses}
    leads = await db.leads.find({
        "$or": [
            {"selling_partner_id": partner_id},
            {"assigned_partners.partner_id": partner_id},
        ]
    }, {"_id": 0}).to_list(2000)

    # Build summary stats
    won = lost = open_ = 0
    won_rev = 0.0; open_val = 0.0
    by_stage: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    examples_to_focus: List[Dict[str, Any]] = []
    for lead in leads:
        st = status_map.get(lead.get('status_id') or '') or {}
        stage = st.get('name', 'Unstaged')
        by_stage[stage] = by_stage.get(stage, 0) + 1
        if st.get('is_won'):
            won += 1; won_rev += float(lead.get('deal_value') or 0)
            cat = lead.get('primary_category_name') or 'Uncategorized'
            by_category[cat] = by_category.get(cat, 0) + 1
        elif st.get('is_lost'):
            lost += 1
        else:
            open_ += 1; open_val += float(lead.get('deal_value') or 0)
            # Compute health to find at-risk for focus
            lead['active_partners_count'] = len([p for p in (lead.get('assigned_partners') or []) if p.get('status') == 'active'])
            lead['status_is_won'] = False
            h = compute_lead_health(lead)
            if h['band'] in ('at_risk', 'cold') and len(examples_to_focus) < 5:
                examples_to_focus.append({"id": lead['id'], "title": lead.get('title'), "deal_value": lead.get('deal_value') or 0, "band": h['band'], "stage": stage})

    closed = won + lost
    win_rate = (won / closed * 100) if closed else 0

    context = (
        f"Selling Partner: {partner.get('name')} ({partner.get('company_name') or 'No company'})\n"
        f"Total deals touched: {len(leads)} (won {won}, lost {lost}, open {open_})\n"
        f"Won revenue: ₹{won_rev:,.0f} | Open pipeline: ₹{open_val:,.0f} | Win rate: {win_rate:.1f}%\n"
        f"Deals by stage: " + ", ".join(f"{s}={c}" for s, c in by_stage.items()) + "\n"
        f"Won categories: " + (", ".join(f"{c}={n}" for c, n in sorted(by_category.items(), key=lambda x: -x[1])[:5]) or "—") + "\n"
        f"At-risk / cold open leads (for focus): " + (", ".join(f"\"{e['title']}\" ({e['stage']}, {e['band']}, ₹{e['deal_value']:,.0f})" for e in examples_to_focus) or "—")
    )
    system_msg = (
        "You are a senior sales coach analyzing a selling partner's performance. Return STRICT JSON only. Schema:\n"
        "{\n"
        '  "summary": string (1-2 sentences overall),\n'
        '  "strengths": array of 2-4 short bullets,\n'
        '  "weaknesses": array of 2-4 short bullets,\n'
        '  "coaching_tips": array of 3-5 actionable, specific tips (one sentence each),\n'
        '  "leads_to_focus": array of {lead_id, title, why_focus} — pull from the at-risk/cold list,\n'
        '  "next_training_topic": short string (e.g. "negotiation pricing objections"),\n'
        '  "confidence": 0-100 integer\n'
        "}\n"
        "Use the actual stats and lead titles from context. Avoid generic advice. If the partner has very few deals, acknowledge it and recommend volume-building tactics."
    )
    parsed = await _ai_lead_chat(f"partner-coach-{partner_id}", system_msg, f"Partner context:\n{context}\n\nReturn STRICT JSON only.")

    return {
        "partner": {"id": partner_id, "name": partner.get('name'), "company_name": partner.get('company_name')},
        "stats": {
            "won": won, "lost": lost, "open": open_,
            "won_revenue": round(won_rev, 2), "open_pipeline": round(open_val, 2),
            "win_rate": round(win_rate, 1), "total_deals": len(leads),
        },
        "summary": str(parsed.get('summary') or ''),
        "strengths": [str(x) for x in (parsed.get('strengths') or [])][:5],
        "weaknesses": [str(x) for x in (parsed.get('weaknesses') or [])][:5],
        "coaching_tips": [str(x) for x in (parsed.get('coaching_tips') or [])][:6],
        "leads_to_focus": (parsed.get('leads_to_focus') or [])[:5],
        "next_training_topic": str(parsed.get('next_training_topic') or ''),
        "confidence": max(0, min(100, int(parsed.get('confidence') or 70))),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

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

@api_router.get("/dashboard/health-check")
async def get_dashboard_health_check(current_user: dict = Depends(get_current_user)):
    """Surface configuration & workflow gaps that would block leads from being assigned
    or processed. Admin-only."""
    if current_user['role'] != UserRole.SUPER_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only super admin can view health check")

    items = []

    # 1. SP companies with no active users -> won't appear in lead-assignment dropdowns
    sp_companies = await db.companies.find(
        {"type": "selling_partner", "is_active": True},
        {"_id": 0, "id": 1, "name": 1, "subcategory_ids": 1}
    ).to_list(1000)

    sp_company_ids = [c['id'] for c in sp_companies]
    user_counts = {}
    if sp_company_ids:
        pipeline = [
            {"$match": {
                "company_id": {"$in": sp_company_ids},
                "role": UserRole.SELLING_PARTNER.value,
                "is_active": True
            }},
            {"$group": {"_id": "$company_id", "count": {"$sum": 1}}}
        ]
        async for row in db.users.aggregate(pipeline):
            user_counts[row['_id']] = row['count']

    no_user_companies = [c for c in sp_companies if user_counts.get(c['id'], 0) == 0]
    if no_user_companies:
        items.append({
            "key": "sp_companies_no_users",
            "severity": "warning",
            "title": "Partner companies without users",
            "count": len(no_user_companies),
            "description": "These selling-partner companies have no active users and won't appear in the Add Lead dropdown.",
            "action_label": "Add users in Partner Mappings",
            "action_path": "/partner-mappings",
            "details": [{"id": c['id'], "name": c['name']} for c in no_user_companies[:5]],
        })

    # 2. SP companies that have users but are not mapped to any sub-category
    no_subcat_companies = [
        c for c in sp_companies
        if user_counts.get(c['id'], 0) > 0 and not (c.get('subcategory_ids') or [])
    ]
    if no_subcat_companies:
        items.append({
            "key": "sp_companies_no_subcats",
            "severity": "warning",
            "title": "Partners not mapped to any sub-category",
            "count": len(no_subcat_companies),
            "description": "These selling-partner companies have users but aren't mapped to any sub-category, so leads can't be routed to them.",
            "action_label": "Map sub-categories",
            "action_path": "/partner-mappings",
            "details": [{"id": c['id'], "name": c['name']} for c in no_subcat_companies[:5]],
        })

    # 3. Sub-categories with no partner company mapped
    secondary_cats = await db.secondary_categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    mapped_subcat_ids = set()
    for c in sp_companies:
        for sid in (c.get('subcategory_ids') or []):
            mapped_subcat_ids.add(sid)
    unmapped_subcats = [s for s in secondary_cats if s['id'] not in mapped_subcat_ids]
    if unmapped_subcats:
        items.append({
            "key": "subcategories_no_partners",
            "severity": "info",
            "title": "Sub-categories with no partner mapped",
            "count": len(unmapped_subcats),
            "description": "No partner company can take leads for these sub-categories. Leads under them will get stuck.",
            "action_label": "Map partners",
            "action_path": "/partner-mappings",
            "details": [{"id": s['id'], "name": s['name']} for s in unmapped_subcats[:5]],
        })

    # 4. Leads stuck in Draft status for > 7 days
    statuses = await db.lead_statuses.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(100)
    draft_status_ids = [s['id'] for s in statuses if s['name'].lower() == 'draft']
    if draft_status_ids:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        stale_leads = await db.leads.find(
            {"status_id": {"$in": draft_status_ids}, "created_at": {"$lt": cutoff}},
            {"_id": 0, "id": 1, "company_name": 1, "created_at": 1}
        ).sort("created_at", 1).to_list(500)
        if stale_leads:
            items.append({
                "key": "leads_draft_stale",
                "severity": "critical",
                "title": "Leads stuck in Draft > 7 days",
                "count": len(stale_leads),
                "description": "These referred leads haven't been picked up. Assign a partner or close them.",
                "action_label": "Review draft leads",
                "action_path": "/leads?status=draft",
                "details": [
                    {"id": l['id'], "name": l.get('company_name') or 'Untitled lead'}
                    for l in stale_leads[:5]
                ],
            })

    # 5. Active leads without any assigned partner (not draft, not won/lost) older than 3 days
    cutoff_3d = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    terminal_status_ids = [
        s['id'] for s in statuses
        if s['name'].lower() in ('draft', 'won', 'lost', 'closed')
    ]
    unassigned_query = {
        "created_at": {"$lt": cutoff_3d},
        "$and": [
            {"$or": [
                {"selling_partner_id": {"$exists": False}},
                {"selling_partner_id": None},
                {"selling_partner_id": ""},
            ]},
            {"$or": [
                {"assigned_partners": {"$exists": False}},
                {"assigned_partners": {"$size": 0}},
            ]},
        ],
    }
    if terminal_status_ids:
        unassigned_query["status_id"] = {"$nin": terminal_status_ids}
    unassigned_leads = await db.leads.find(
        unassigned_query,
        {"_id": 0, "id": 1, "company_name": 1}
    ).to_list(500)
    if unassigned_leads:
        items.append({
            "key": "leads_unassigned",
            "severity": "warning",
            "title": "Active leads without any partner",
            "count": len(unassigned_leads),
            "description": "Created >3 days ago and no selling partner assigned. Likely needs admin intervention.",
            "action_label": "Review leads",
            "action_path": "/leads",
            "details": [
                {"id": l['id'], "name": l.get('company_name') or 'Untitled lead'}
                for l in unassigned_leads[:5]
            ],
        })

    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    items.sort(key=lambda x: (severity_rank.get(x['severity'], 99), -x['count']))

    return {
        "items": items,
        "total_issues": sum(i['count'] for i in items),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


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
            vyapaar_pct = lead.get('commission_override') or 15.0
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
    # Enriched info for referrer leaderboard (role + company name for partners).
    company_ids = list({u.get('company_id') for u in users if u.get('company_id')})
    company_name_map = {}
    if company_ids:
        cmps = await db.companies.find({"id": {"$in": company_ids}}, {"_id": 0}).to_list(len(company_ids))
        company_name_map = {c['id']: c.get('name') for c in cmps}
    user_info_map = {
        u['id']: {
            "name": u['name'],
            "role": u.get('role'),
            "company_name": company_name_map.get(u.get('company_id')),
        }
        for u in users
    }
    
    total_gross_commission = 0
    total_sa_payouts = 0
    total_net_revenue = 0
    partner_wise = {}
    category_wise = {}
    period_wise = {}
    referrer_wise = {}
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
            
            # Referrer-wise (Sales Associate OR Selling Partner who was set as
            # the lead's referrer via sales_associate_id). Used for the admin
            # "Top Referrers" leaderboard.
            referrer_id = lead.get('sales_associate_id')
            if referrer_id:
                if referrer_id not in referrer_wise:
                    info = user_info_map.get(referrer_id, {})
                    referrer_wise[referrer_id] = {
                        "id": referrer_id,
                        "name": info.get('name') or "Unknown",
                        "role": info.get('role') or "unknown",
                        "company_name": info.get('company_name'),
                        "referred_deals": 0,
                        "referred_deal_value": 0,
                        "earnings": 0,
                    }
                referrer_wise[referrer_id]['referred_deals'] += 1
                referrer_wise[referrer_id]['referred_deal_value'] += deal_value
                referrer_wise[referrer_id]['earnings'] += sa_payout

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
        "top_referrers": [
            {**r, "referred_deal_value": round(r['referred_deal_value'], 2), "earnings": round(r['earnings'], 2)}
            for r in sorted(referrer_wise.values(), key=lambda x: x['earnings'], reverse=True)[:10]
        ],
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
    """Detailed referrer earnings report (covers both Sales Associates and
    Selling Partners who were set as the lead's referrer via sales_associate_id).
    Lifetime + period filtered view."""
    if current_user['role'] not in [UserRole.SUPER_ADMIN.value, UserRole.SALES_ASSOCIATE.value, UserRole.SELLING_PARTNER.value]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user['role'] in [UserRole.SALES_ASSOCIATE.value, UserRole.SELLING_PARTNER.value] and current_user['id'] != associate_id:
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

@app.on_event("startup")
async def ensure_zeptomail_logs_ttl():
    """Phase 32 — ensure email_logs collection has a 90-day TTL index."""
    try:
        from services import zeptomail as _zepto
        await _zepto.ensure_email_logs_ttl(db)
    except Exception as e:
        logger.warning(f"email_logs TTL setup failed: {e}")


@app.on_event("startup")
async def start_followup_reminder_scheduler():
    """Phase 33 — kick off the in-process asyncio loop that scans for
    due follow-up reminders every 60s and dispatches emails."""
    try:
        from services import zeptomail as _zepto
        from services import scheduler as _sched
        _sched.start_reminder_loop(db, _zepto)
        logger.info("Phase 33 follow-up reminder scheduler started.")
    except Exception as e:
        logger.warning(f"Follow-up scheduler startup failed: {e}")


@app.on_event("shutdown")
async def stop_followup_reminder_scheduler():
    try:
        from services import scheduler as _sched
        _sched.stop_reminder_loop()
    except Exception as e:
        logger.warning(f"Follow-up scheduler shutdown failed: {e}")


@api_router.post("/admin/dispatch-follow-up-reminders")
async def admin_run_followup_reminders(current_user: dict = Depends(get_current_user)):
    """Phase 33 — admin-only manual trigger that runs the scheduler pass NOW
    instead of waiting up to 60s for the loop. Returns scanned/sent counts."""
    if current_user.get('role') != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Admin only")
    from services import zeptomail as _zepto
    from services import scheduler as _sched
    if not _zepto.is_configured():
        raise HTTPException(status_code=503, detail="ZeptoMail is not configured on this environment")
    result = await _sched.dispatch_due_reminders(db, _zepto)
    return result


@api_router.post("/admin/dispatch-milestone-reminders")
async def admin_run_milestone_reminders(window_hours: int = 48, current_user: dict = Depends(get_current_user)):
    """Phase 33.5 — admin-only manual trigger for the milestone-due scan.
    Pass ?window_hours= to override the default 48h look-ahead. Returns scanned/sent."""
    if current_user.get('role') != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Admin only")
    from services import zeptomail as _zepto
    from services import scheduler as _sched
    if not _zepto.is_configured():
        raise HTTPException(status_code=503, detail="ZeptoMail is not configured on this environment")
    result = await _sched.dispatch_due_milestone_reminders(db, _zepto, window_hours=max(1, min(168, int(window_hours))))
    return result


class TestEmailRequest(BaseModel):
    to_address: EmailStr
    notification_type: Optional[str] = None  # if set, render via that template
    subject: Optional[str] = None
    html_body: Optional[str] = None


@api_router.post("/admin/test-email")
async def admin_send_test_email(body: TestEmailRequest, current_user: dict = Depends(get_current_user)):
    """Phase 32 — admin-only test endpoint to verify the ZeptoMail integration end-to-end.
    Pass either a `notification_type` (uses our template) or a custom `subject`+`html_body`."""
    if current_user.get('role') != UserRole.SUPER_ADMIN.value and not current_user.get('is_vyapaar_ops'):
        raise HTTPException(status_code=403, detail="Admin only")

    from services import zeptomail as _zepto
    if not _zepto.is_configured():
        raise HTTPException(status_code=503, detail="ZeptoMail is not configured on this environment")

    if body.notification_type:
        rendered = _zepto.render(body.notification_type, {
            "recipient_name": current_user.get('name', ''),
            "lead_title": "Acme Corp — Renewal",
            "customer_name": "Anita Sharma",
            "customer_company": "Acme Corp",
            "assigned_by_name": current_user.get('name', 'Admin'),
            "scheduled_date": "tomorrow at 4pm",
            "notes": "Confirm proposal numbers; share updated SOW.",
            "inviter_name": current_user.get('name', 'Vyapaar Admin'),
            "magic_link": "https://app.vyapaar.net/deal-room/sample-token",
            "permissions": ["view", "comment", "approve"],
            "expires_at": "in 14 days",
            "approval_title": "Approve final pricing",
            "requester_name": current_user.get('name', 'Admin'),
            "amount_formatted": "₹1,25,000",
            "title": "Test notification",
            "message": "This is a test email from Meshora's notifications pipeline.",
            "lead_id": "sample-lead",
            "lead_url": "https://app.vyapaar.net/leads/sample-lead",
        }) or {}
        subject = rendered.get("subject") or f"[Meshora] Test: {body.notification_type}"
        html = rendered.get("html") or "<p>This is a test email from Meshora.</p>"
        text = rendered.get("text")
    elif body.subject and body.html_body:
        subject = body.subject
        html = body.html_body
        text = None
    else:
        subject = "[Meshora] Test email"
        html = "<p>This is a test email from your Meshora ZeptoMail integration. If you see this, the wiring works.</p>"
        text = "Meshora ZeptoMail integration test."

    result = await _zepto.send_email(
        to_address=body.to_address,
        subject=subject,
        html_body=html,
        text_body=text,
        to_name=current_user.get('name'),
        db=db,
        notification_type=body.notification_type or "admin_test",
        user_id=current_user['id'],
        correlation_id=str(uuid.uuid4()),
    )
    return result


# Mount commercials router (extracted to routers/commercials.py)
from routers.commercials import router as commercials_router  # noqa: E402
api_router.include_router(commercials_router)

# Mount deal-room router (Phase 27/27.5 — extracted to routers/deal_room.py)
from routers.deal_room import router as deal_room_router  # noqa: E402
api_router.include_router(deal_room_router)

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

@app.on_event("startup")
async def backfill_lead_status_is_won():
    """Ensure existing 'Won' lead statuses have is_won=True for the Closed-Won wizard."""
    try:
        await db.lead_statuses.update_many(
            {"is_won": {"$exists": False}},
            {"$set": {"is_won": False}}
        )
        await db.lead_statuses.update_many(
            {"name": {"$regex": "^won$", "$options": "i"}},
            {"$set": {"is_won": True}}
        )
        await db.lead_statuses.update_many(
            {"name": {"$regex": "closed.?won", "$options": "i"}},
            {"$set": {"is_won": True}}
        )
    except Exception as e:
        logger.warning(f"Lead status is_won backfill failed: {e}")

