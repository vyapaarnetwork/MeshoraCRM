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
- SendGrid email integration for follow-up reminders

## Architecture
- **Frontend**: React 19 with Shadcn/UI, TailwindCSS, Recharts
- **Backend**: FastAPI with MongoDB (Motor async driver)
- **Authentication**: JWT tokens
- **Email**: SendGrid (configured, requires API key)
- **Styling**: Manrope + Inter fonts, Blue (#4169E1) + Red (#DC143C) brand colors

## What's Been Implemented (Feb 9, 2025)

### Phase 1 - MVP Complete
- [x] User registration for all 4 roles with company creation
- [x] JWT authentication with login/logout
- [x] Role-based access control in frontend and backend
- [x] Master Data Management:
  - Primary Categories (HR, IT, Marketing, Finance, Compliance)
  - Secondary Categories mapped to primary
  - Lead Statuses (New, Qualified, Proposal, Negotiation, Won, Lost, On Hold)
  - Commission Templates (Standard 15%, Premium 12%, High Value 10%)
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

## Prioritized Backlog

### P0 - Critical (Next Sprint)
- [ ] SendGrid API key configuration for email reminders
- [ ] Profile settings page with password change

### P1 - High Priority
- [ ] Email templates for follow-up reminders
- [ ] Lead assignment workflow
- [ ] Bulk lead import from CSV
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

## Next Tasks
1. Provide SendGrid API key to enable email reminders
2. Implement profile settings page
3. Add email templates for different notification types
4. Enhance reporting with more visualization options
