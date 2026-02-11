# Vyapaar Network CRM - Product Requirements Document

## Original Problem Statement
Build a multi-tenant, role-based CRM application called Vyapaar Network CRM with 4 user roles (Selling Partner, Sales Associate, Customer, Super Admin), master data management, lead management with follow-ups and comments, transparent commission logic, role-specific dashboards, and comprehensive reports.

## User Personas
1. **Super Admin (Vyapaar Network Team)**: Full system access, manages all masters, users, leads, commissions, reports, email templates, and grid analytics
2. **Selling Partner**: Company that sells products/services, can refer leads, request internal services, views assigned leads and commission summary
3. **Sales Associate**: Independent individual who brings leads, earns perpetual commission, can refer leads
4. **Customer**: Company/individual looking for vendors, can submit and track lead requests

## What's Been Implemented

### Phase 1-3 - MVP + Enhancements (Feb 9-10, 2025)
- [x] JWT authentication with 4 user roles
- [x] Master Data Management (Categories, Lead Status, Commission Templates)
- [x] Lead Management with follow-ups and comments
- [x] Commission calculation with transparent breakdown
- [x] Role-specific Dashboards
- [x] Reports & Analytics with CSV export
- [x] Profile Settings Page
- [x] Lead Bulk Import with CSV template
- [x] Customer-Only Self Registration
- [x] Admin User Creation/Edit/Delete
- [x] Draft Lead Status with auto-transition
- [x] Partner Sub-categories
- [x] Follow-up "Pending With" Assignment

### Phase 4 - Lead Referral, Notifications & Grid Report (Feb 10, 2025)
- [x] Lead Referral for Selling Partners and Sales Associates
- [x] Internal Request Feature (Partner as Customer)
- [x] In-App Notification System with bell icon
- [x] SMS Notifications via Twilio (backend ready, awaiting credentials)
- [x] Grid Report with filterable/sortable performance data
- [x] Reusable SortableTable component

### Phase 5 - Document Management (Feb 11, 2025)
- [x] Document Tags Master Data (admin-configurable tags for leads/companies)
- [x] Lead Document Upload with tags (Proposal, Contract, Invoice, Quotation)
- [x] Company Document Upload (Corporate Profile, Product Catalog, Brochure)
- [x] Document view, download, and delete functionality

### Phase 6 - Email Templates (Feb 11, 2025)
- [x] **Configurable Email Templates**: Super Admin can edit email templates for 6 events:
  - New Lead Created
  - Lead Assigned to Partner
  - Lead Status Changed
  - Lead Won (Deal Closed)
  - Lead Lost
  - Follow-up Reminder
- [x] **Template Variables Display**: Shows available placeholders with descriptions
  - Variables like `{{lead_title}}`, `{{customer_name}}`, `{{partner_name}}`, `{{deal_value}}`
  - Copy and Insert buttons for each variable
- [x] **Email Preview**: Preview templates with sample data before saving
- [x] **Enable/Disable Toggle**: Turn individual email notifications on/off
- [x] **Reset to Default**: Restore any template to its original content
- [x] **HTML Support**: Rich formatting in email body

## Prioritized Backlog

### P0 - Critical (Requires User Input)
- [ ] **SendGrid API Key**: Add `SENDGRID_API_KEY` and `SENDER_EMAIL` to backend/.env for email notifications
- [ ] **Twilio Credentials**: Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` for SMS

### P1 - High Priority
- [ ] Automated follow-up email reminders (cron job to check upcoming follow-ups)
- [ ] Lead auto-routing based on partner sub-categories
- [ ] Dashboard date range filters

### P2 - Medium Priority  
- [ ] Dark mode toggle
- [ ] Lead activity timeline
- [ ] Real-time notifications (WebSocket)
- [ ] Advanced search with multiple filters

### P3 - Nice to Have
- [ ] API documentation (Swagger)
- [ ] Audit logs
- [ ] Mobile-responsive improvements
- [ ] Custom dashboard widgets

## Refactoring Needed
- **Critical**: Backend monolith (server.py is 2900+ lines) should be split into modular routers
- **High**: N+1 query issues in data aggregation endpoints should use MongoDB $lookup

## Test Credentials
- **Super Admin**: admin@vyapaarnetwork.com / admin123

## Key API Endpoints

### Email Templates
- `GET /api/email-templates` - List all 6 templates
- `GET /api/email-templates/{event_type}` - Get specific template
- `PUT /api/email-templates/{event_type}` - Update template (subject, body, is_enabled)
- `POST /api/email-templates/{event_type}/preview` - Preview with sample data
- `POST /api/email-templates/{event_type}/reset` - Reset to default
- `GET /api/email-templates/variables/{event_type}` - Get available variables

### Document Tags Master Data
- `GET /api/master/document-tags` - List all tags
- `POST /api/master/document-tags` - Create new tag
- `PUT /api/master/document-tags/{id}` - Update tag
- `DELETE /api/master/document-tags/{id}` - Delete tag

### Document Upload
- `POST /api/documents/upload` - Upload document
- `GET /api/documents/entity/{entity_type}/{entity_id}` - Get documents
- `GET /api/documents/{id}/download` - Download document
- `DELETE /api/documents/{id}` - Delete document

### Notifications
- `GET /api/notifications` - Get user's notifications
- `PUT /api/notifications/{id}/read` - Mark as read
- `PUT /api/notifications/mark-all-read` - Mark all as read

## Environment Variables Required

```env
# Backend (.env)
MONGO_URL=mongodb://...
DB_NAME=vyapaar_crm

# SendGrid (Required for email notifications)
SENDGRID_API_KEY=your_api_key
SENDER_EMAIL=noreply@vyapaarnetwork.com

# Twilio SMS (Optional)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

## Architecture
- **Frontend**: React 19 with Shadcn/UI, TailwindCSS, Recharts
- **Backend**: FastAPI with MongoDB (Motor async driver)
- **Authentication**: JWT tokens
- **File Storage**: Local uploads directory (/app/backend/uploads)
- **Email**: SendGrid (configured, awaiting API key)
- **SMS**: Twilio (configured, awaiting credentials)

## Test Reports
- `/app/test_reports/iteration_5.json` - Document Management tests
- `/app/test_reports/iteration_6.json` - Email Templates tests (25 tests, 100% pass)
