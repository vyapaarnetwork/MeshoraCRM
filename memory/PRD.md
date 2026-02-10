# Vyapaar Network CRM - Product Requirements Document

## Original Problem Statement
Build a multi-tenant, role-based CRM application called Vyapaar Network CRM with 4 user roles (Selling Partner, Sales Associate, Customer, Super Admin), master data management, lead management with follow-ups and comments, transparent commission logic, role-specific dashboards, and comprehensive reports.

## User Personas
1. **Super Admin (Vyapaar Network Team)**: Full system access, manages all masters, users, leads, commissions, and reports
2. **Selling Partner**: Company that sells products/services, can have multiple users, views assigned leads and commission summary, can refer leads
3. **Sales Associate**: Independent individual who brings leads, earns perpetual commission from Vyapaar's share
4. **Customer**: Company/individual looking for vendors, can submit and track lead requests

## Core Requirements (Static)
- Multi-tenant architecture with role-based access control (RBAC)
- JWT-based authentication
- Lead management with follow-ups and comments
- Master data management (Categories, Lead Status, Commission Templates)
- Transparent commission calculation and breakdown
- Role-specific dashboards with analytics
- Reports with filters and CSV export
- SendGrid email integration for follow-up reminders (configured, requires API key)

## Architecture
- **Frontend**: React 19 with Shadcn/UI, TailwindCSS, Recharts
- **Backend**: FastAPI with MongoDB (Motor async driver)
- **Authentication**: JWT tokens
- **Email**: SendGrid (configured, requires API key)
- **Styling**: Manrope + Inter fonts, Blue (#4169E1) + Red (#DC143C) brand colors

## What's Been Implemented

### Phase 1 - MVP Complete (Feb 9, 2025)
- [x] User registration for all 4 roles with company creation
- [x] JWT authentication with login/logout
- [x] Role-based access control in frontend and backend
- [x] Master Data Management:
  - Primary Categories (HR, IT, Marketing, Finance, Compliance)
  - Secondary Categories mapped to primary
  - Lead Statuses (Draft, New, Qualified, Proposal, Negotiation, Won, Lost, On Hold)
  - Commission Templates (Standard 15%, Premium Partner 12%, High Value 10%)
- [x] Lead Management:
  - Create, read, update, delete leads
  - Category and status tracking
  - Follow-up scheduling with completion tracking
  - Time-stamped, role-tagged comments
- [x] Commission Logic:
  - Vyapaar commission from deal value
  - Commission override at lead level
  - Sales Associate gets % from Vyapaar's share
  - Transparent breakdown display
- [x] Role-specific Dashboards
- [x] Reports & Analytics with CSV export

### Phase 2 - Enhanced Features (Feb 10, 2025)
- [x] Profile Settings Page
- [x] Lead Bulk Import with CSV template
- [x] Enhanced Reporting & Commission Engine

### Phase 3 - User Management & Lead State Improvements (Feb 10, 2025)
- [x] Customer-Only Self Registration
- [x] Admin User Creation (any role)
- [x] Draft Lead Status
- [x] Partner Sub-categories
- [x] Follow-up "Pending With" Assignment

### Phase 4 - User Management & Lead Referral (Feb 10, 2025)
- [x] **User Edit Functionality**:
  - Super Admin can edit any user's details
  - Update name, email, phone, role, company assignment
  - Optional password change during edit
- [x] **User Delete Functionality**:
  - Super Admin can delete users (soft delete - sets is_active=False)
  - Cannot delete own account (safety check)
  - Delete confirmation dialog
- [x] **Company Assignment for All Roles**:
  - Selling Partners, Customers, and Sales Associates can be assigned to companies
  - Dropdown shows all available companies during user create/edit
- [x] **Lead Referral Page (Selling Partners)**:
  - New "Lead Referral" menu item in sidebar for Selling Partners
  - Stats dashboard: Total Referrals, Pending Review, Assigned, Won Deals
  - Info card explaining the referral workflow
  - "New Referral" dialog with:
    - Lead title and description
    - Customer details (name, email, phone, company)
    - Category selection (primary and secondary)
    - Estimated deal value
    - Referral notes
  - Referrals saved in Draft status
  - Referrals track "referred_by_partner_id"
  - "My Referrals" table showing status and assignment
- [x] **Referral Status Transition**:
  - Referrals start in Draft status (no partner assigned)
  - When Super Admin assigns a selling partner, status changes to New

## Prioritized Backlog

### P0 - Critical (Next Sprint)
- [ ] SendGrid API key configuration for email reminders

### P1 - High Priority
- [ ] Email templates for follow-up reminders
- [ ] Lead assignment workflow with auto-routing based on partner sub-categories
- [ ] Dashboard date range filters

### P2 - Medium Priority  
- [ ] Dark mode toggle
- [ ] Lead activity timeline
- [ ] Notifications system
- [ ] Advanced search with multiple filters

### P3 - Nice to Have
- [ ] API documentation (Swagger)
- [ ] Audit logs
- [ ] Mobile-responsive improvements
- [ ] Custom dashboard widgets

## Test Credentials
- **Super Admin**: admin@vyapaarnetwork.com / admin123
- **Selling Partner**: partner1@test.com / test123

## API Endpoints Summary

### Authentication
- `POST /api/auth/register` - Customer registration only
- `POST /api/auth/login` - User authentication

### User Management
- `POST /api/users` - Admin creates user (any role)
- `GET /api/users` - List all users (Admin)
- `GET /api/users/{id}` - Get user details (Admin)
- `PUT /api/users/{id}` - Update user (Admin)
- `DELETE /api/users/{id}` - Soft delete user (Admin)

### Lead Management
- `GET /api/leads` - List leads (role-filtered)
- `POST /api/leads` - Create lead (Draft if no partner)
- `PUT /api/leads/{id}` - Update lead (auto Draft→New on partner assign)
- `POST /api/leads/{id}/follow-ups` - Add follow-up with pending_with

### Lead Referral (Selling Partners)
- `POST /api/leads/referral` - Create referral (Draft status)
- `GET /api/leads/my-referrals` - List partner's referrals

### Companies
- `GET /api/companies` - List companies with subcategories
- `POST /api/companies` - Create company with subcategory_ids
- `PUT /api/companies/{id}` - Update company

### Master Data
- `GET /api/master/lead-status` - Lead statuses including Draft
- `GET /api/master/primary-categories` - Primary categories
- `GET /api/master/secondary-categories` - Secondary categories

## Database Schema

### Users Collection
```json
{
  "id": "uuid",
  "email": "string",
  "password": "hashed",
  "name": "string",
  "role": "super_admin|selling_partner|sales_associate|customer",
  "company_id": "uuid|null",
  "phone": "string|null",
  "is_active": true,
  "created_at": "datetime"
}
```

### Leads Collection
```json
{
  "id": "uuid",
  "title": "string",
  "customer_name": "string",
  "customer_email": "string",
  "selling_partner_id": "uuid|null",
  "sales_associate_id": "uuid|null",
  "referred_by_partner_id": "uuid|null",
  "status_id": "uuid",
  "deal_value": "number",
  "follow_ups": [{
    "id": "uuid",
    "scheduled_date": "date",
    "notes": "string",
    "pending_with": "customer|selling_partner|null",
    "is_completed": false
  }],
  "comments": [],
  "created_at": "datetime"
}
```

### Companies Collection
```json
{
  "id": "uuid",
  "name": "string",
  "type": "selling_partner|customer",
  "subcategory_ids": ["uuid"],
  "vyapaar_commission_percentage": 15.0,
  "is_active": true
}
```
