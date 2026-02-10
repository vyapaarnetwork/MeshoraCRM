# Vyapaar Network CRM - Product Requirements Document

## Original Problem Statement
Build a multi-tenant, role-based CRM application called Vyapaar Network CRM with 4 user roles (Selling Partner, Sales Associate, Customer, Super Admin), master data management, lead management with follow-ups and comments, transparent commission logic, role-specific dashboards, and comprehensive reports.

## User Personas
1. **Super Admin (Vyapaar Network Team)**: Full system access, manages all masters, users, leads, commissions, and reports
2. **Selling Partner**: Company that sells products/services, can have multiple users, views assigned leads and commission summary
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
- [x] Role-specific Dashboards:
  - Stats cards (total leads, won deals, revenue, commission)
  - Leads by Status pie chart
  - Leads by Category bar chart
  - Revenue trend line chart
- [x] Reports & Analytics:
  - Date range filters
  - Selling Partner performance reports
  - Sales Associate earnings reports
  - CSV export functionality
- [x] Admin Pages:
  - Users list with role filtering
  - Companies management
  - Categories management (Primary, Secondary, Lead Status)
  - Commission Templates management

### Phase 2 - Enhanced Features (Feb 10, 2025)
- [x] Profile Settings Page:
  - Update name and phone number
  - Change password functionality
  - Account details display
- [x] Lead Bulk Import:
  - CSV import with validation
  - Sample template download
  - Column reference with required/optional fields
  - Import result summary with error details
- [x] Enhanced Reporting & Commission Engine:
  - Vyapaar Revenue Report (Admin)
  - Detailed Partner Performance Reports
  - Deal-Level Commission Statement API
  - Commission Locking for Won deals

### Phase 3 - User Management & Lead State Improvements (Feb 10, 2025)
- [x] Customer-Only Self Registration:
  - Registration page restricted to customers only
  - Sales Associates and Selling Partners created by Admin only
  - Info banner explaining role restrictions
- [x] Admin User Creation:
  - Add User button on Users page (Admin only)
  - Create users of any role type
  - Company selection/creation for applicable roles
- [x] Draft Lead Status:
  - "Draft" status added to lead pipeline (order 0)
  - Leads without selling partner default to Draft
  - Auto-transition from Draft to New when partner assigned
  - Visual indicator in lead form
- [x] Partner Sub-categories:
  - Selling partners can have multiple service sub-categories
  - Checkbox selection grouped by primary category
  - Sub-categories displayed in Companies table
- [x] Follow-up "Pending With" Assignment:
  - Follow-ups can specify pending with "Customer" or "Selling Partner"
  - Visual indicator in follow-up list

## Prioritized Backlog

### P0 - Critical (Next Sprint)
- [ ] SendGrid API key configuration for email reminders

### P1 - High Priority
- [ ] Email templates for follow-up reminders
- [ ] Lead assignment workflow with auto-routing
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

## API Endpoints Summary
- `POST /api/auth/register` - Customer registration only
- `POST /api/auth/login` - User authentication
- `POST /api/users` - Admin creates user (any role)
- `GET /api/users` - List all users (Admin)
- `GET /api/leads` - List leads (role-filtered)
- `POST /api/leads` - Create lead (Draft if no partner)
- `PUT /api/leads/{id}` - Update lead (auto Draft→New on partner assign)
- `POST /api/leads/{id}/follow-ups` - Add follow-up with pending_with
- `GET /api/companies` - List companies with subcategories
- `POST /api/companies` - Create company with subcategory_ids
- `GET /api/master/lead-status` - Lead statuses including Draft
