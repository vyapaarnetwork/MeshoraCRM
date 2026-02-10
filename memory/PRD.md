# Vyapaar Network CRM - Product Requirements Document

## Original Problem Statement
Build a multi-tenant, role-based CRM application called Vyapaar Network CRM with 4 user roles (Selling Partner, Sales Associate, Customer, Super Admin), master data management, lead management with follow-ups and comments, transparent commission logic, role-specific dashboards, and comprehensive reports.

## User Personas
1. **Super Admin (Vyapaar Network Team)**: Full system access, manages all masters, users, leads, commissions, reports, and grid analytics
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
- [x] **Lead Referral for Both Roles**:
  - Selling Partners AND Sales Associates can now create lead referrals
  - Referrals saved with referred_by_partner_id or referred_by_associate_id
  - All referrals start in Draft status until admin assigns a partner
  
- [x] **Internal Request Feature (Selling Partners)**:
  - Selling Partners can request services from other partners
  - "Internal Request" button with is_internal_request flag
  - Pre-fills partner's details as the customer
  - Separate tab view for internal requests vs external referrals

- [x] **Notifications System**:
  - Bell icon in header with unread count badge
  - Dropdown showing recent notifications
  - Notification types: new_lead, lead_assigned, lead_status_change, new_referral
  - Click notification to navigate to lead detail
  - "Mark all as read" functionality
  - Auto-created on lead creation, assignment, and referral submission

- [x] **SMS Notifications (Twilio)**:
  - Integration code ready for Twilio SMS
  - Sends SMS when lead is assigned to partner
  - Notifies both assigned partner and super admins
  - Gracefully handles missing credentials (logs warning, doesn't fail)

- [x] **Grid Report Page (Super Admin)**:
  - Comprehensive performance dashboard
  - Summary stats: Total Leads, Won/Lost Deals, Deal Value, Vyapaar Commission, Partner Revenue
  - Partner Performance Summary table with conversion rates
  - Detailed Lead Grid with all deal data
  - Filters: Date range, Partner, Category, Status
  - Export to CSV functionality

- [x] **Sortable/Filterable Tables**:
  - Reusable SortableTable component
  - Click column header to sort (asc/desc)
  - Sort indicator shows current direction
  - Global search across all columns
  - Pagination with page navigation

## Prioritized Backlog

### P0 - Critical (Requires User Input)
- [ ] **Twilio SMS Credentials**: Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER to backend/.env
- [ ] **SendGrid API Key**: Configure for email reminders

### P1 - High Priority
- [ ] Email templates for follow-up reminders
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

## Test Credentials
- **Super Admin**: admin@vyapaarnetwork.com / admin123
- **Selling Partner**: partner1@test.com / test123

## Key API Endpoints

### Lead Referral
- `POST /api/leads/referral` - Create referral (both partners and associates)
- `GET /api/leads/my-referrals` - List user's referrals

### Notifications
- `GET /api/notifications` - Get user's notifications
- `GET /api/notifications/unread-count` - Get unread count
- `PUT /api/notifications/{id}/read` - Mark as read
- `PUT /api/notifications/mark-all-read` - Mark all as read

### Grid Report
- `GET /api/reports/grid-performance` - Get performance data with filters

## Environment Variables Required

```env
# Backend (.env)
MONGO_URL=mongodb://...
DB_NAME=vyapaar_crm

# Twilio SMS (Optional - for SMS notifications)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# SendGrid (Optional - for email reminders)
SENDGRID_API_KEY=your_api_key
SENDER_EMAIL=noreply@vyapaarnetwork.com
```

## Architecture
- **Frontend**: React 19 with Shadcn/UI, TailwindCSS, Recharts
- **Backend**: FastAPI with MongoDB (Motor async driver)
- **Authentication**: JWT tokens
- **SMS**: Twilio (configured, awaiting credentials)
- **Email**: SendGrid (configured, awaiting credentials)
