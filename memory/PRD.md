# Vyapaar Network CRM - Product Requirements Document

## Original Problem Statement
Build a multi-tenant, role-based CRM application called Vyapaar Network CRM with 4 user roles (Selling Partner, Sales Associate, Customer, Super Admin), master data management, lead management with follow-ups and comments, transparent commission logic, role-specific dashboards, and comprehensive reports.

## User Personas
1. **Super Admin (Vyapaar Network Team)**: Full system access, manages all masters, users, leads, commissions, reports, email templates, and grid analytics
2. **Selling Partner**: Company that sells products/services, can refer leads, request internal services, views assigned leads and commission summary
3. **Sales Associate**: Independent individual who brings leads, earns perpetual commission, can refer leads
4. **Customer**: Company/individual looking for vendors, can submit leads and manage their company team members

## What's Been Implemented

### Phase 1-3 - MVP + Enhancements (Feb 9-10, 2025)
- [x] JWT authentication with 4 user roles
- [x] Master Data Management (Categories, Lead Status, Commission Templates)
- [x] Lead Management with follow-ups and comments
- [x] Commission calculation with transparent breakdown
- [x] Role-specific Dashboards
- [x] Reports & Analytics with CSV export

### Phase 4 - Lead Referral, Notifications & Grid Report (Feb 10, 2025)
- [x] Lead Referral for Selling Partners and Sales Associates
- [x] Internal Request Feature (Partner as Customer)
- [x] In-App Notification System with bell icon
- [x] SMS Notifications via Twilio (backend ready)
- [x] Grid Report with filterable/sortable performance data

### Phase 5 - Document Management (Feb 11, 2025)
- [x] Document Tags Master Data (admin-configurable)
- [x] Lead Document Upload with tags (Proposal, Contract, Invoice, Quotation)
- [x] Company Document Upload (Corporate Profile, Product Catalog, Brochure)

### Phase 6 - Email Templates (Feb 11, 2025)
- [x] Configurable Email Templates for 6 events
- [x] Template Variables Display with Copy/Insert buttons
- [x] Email Preview with sample data
- [x] Enable/Disable Toggle per template

### Phase 7 - Multi-User & Partner History (Feb 24, 2025)
- [x] **Customer User Management**:
  - Customers can add, edit, delete team members from their company
  - New "Team Members" menu in sidebar for customers
  - All team members get Customer role and same company_id
  
- [x] **Company Creation with Default User**:
  - When creating Customer type company, admin specifies default user details
  - Default user fields: name, email, phone, password (default: customer123)
  - User is auto-created with Customer role

- [x] **Internal Requests Separate Menu**:
  - "Internal Requests" menu item for Selling Partners only
  - Dedicated page to view and create service requests
  - Stats: Total Requests, Pending, Completed

- [x] **Lead Multi-Partner Assignment with History**:
  - `partner_history` array tracks all partner assignments
  - Each assignment records: partner_id, partner_name, assigned_at, assigned_by, removed_at
  - Super Admin sees "Partner Assignment History" section on Lead Detail
  - Current partner marked with "Current" badge
  - Removed partners show removal timestamp

## Prioritized Backlog

### P0 - Critical (Requires User Input)
- [ ] **SendGrid API Key**: Add `SENDGRID_API_KEY` and `SENDER_EMAIL` for email notifications
- [ ] **Twilio Credentials**: Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` for SMS

### P1 - High Priority
- [ ] Automated follow-up email reminders (cron job)
- [ ] Lead auto-routing based on partner sub-categories
- [ ] Dashboard date range filters

### P2 - Medium Priority  
- [ ] Dark mode toggle
- [ ] Lead activity timeline
- [ ] Real-time notifications (WebSocket)

### P3 - Nice to Have
- [ ] API documentation (Swagger)
- [ ] Audit logs
- [ ] Custom dashboard widgets

## Key API Endpoints

### Customer User Management
- `GET /api/customers/company-users` - List company users (Customer only)
- `POST /api/customers/company-users` - Create company user
- `PUT /api/customers/company-users/{id}` - Update company user
- `DELETE /api/customers/company-users/{id}` - Deactivate company user

### Internal Requests
- `GET /api/leads/internal-requests` - List internal service requests (Selling Partner only)

### Company Creation
- `POST /api/companies` - Create company (with optional default_user_* fields for customer type)

### Email Templates
- `GET /api/email-templates` - List all templates
- `PUT /api/email-templates/{event_type}` - Update template
- `POST /api/email-templates/{event_type}/preview` - Preview with sample data

## Test Credentials
- **Super Admin**: admin@vyapaarnetwork.com / admin123
- **Customer**: john@testco.com / test123 (Test Customer Co)

## Architecture
- **Frontend**: React 19 with Shadcn/UI, TailwindCSS, Recharts
- **Backend**: FastAPI with MongoDB (Motor async driver)
- **Authentication**: JWT tokens
- **File Storage**: Local uploads directory
- **Email**: SendGrid (configured, awaiting API key)
- **SMS**: Twilio (configured, awaiting credentials)

## Test Reports
- `/app/test_reports/iteration_6.json` - Email Templates tests
- `/app/test_reports/iteration_7.json` - Multi-User & Partner History tests (20/20 passed)
