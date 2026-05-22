# Vyapaar Network CRM - Product Requirements Document

## Original Problem Statement
Build a multi-tenant, role-based CRM application called Vyapaar Network CRM with 4 user roles (Selling Partner, Sales Associate, Customer, Super Admin), master data management, lead management with follow-ups and comments, transparent commission logic, role-specific dashboards, and comprehensive reports.

## User Personas
1. **Super Admin (Vyapaar Network Team)**: Full system access, manages all masters, users, leads, commissions, reports, email templates, and grid analytics
2. **Selling Partner**: Company that sells products/services, can refer leads, request internal services, views assigned leads
3. **Sales Associate**: Independent individual who brings leads, earns perpetual commission, can refer leads
4. **Customer**: Company/individual looking for vendors, can submit leads and manage company team members

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
- [x] In-App Notification System with bell icon
- [x] SMS Notifications via Twilio (backend ready)
- [x] Grid Report with filterable/sortable performance data

### Phase 5 - Document Management (Feb 11, 2025)
- [x] Document Tags Master Data (admin-configurable)
- [x] Lead Document Upload with tags
- [x] Company Document Upload

### Phase 6 - Email Templates (Feb 11, 2025)
- [x] Configurable Email Templates for 6 events
- [x] Template Variables Display
- [x] Email Preview with sample data

### Phase 7 - Multi-User & Internal Requests (Feb 24, 2025)
- [x] **Customer User Management**: Customers can add/edit/delete team members
- [x] **Company Creation with Default User**: Admin specifies default user for customer companies
- [x] **Internal Requests Separate Menu**: Dedicated page for Selling Partners

### Phase 8 - Multi-Partner Lead Assignment (Feb 24, 2025)
- [x] **Concurrent Partner Assignment**: 
  - Leads can be assigned to MULTIPLE selling partners simultaneously
  - All assigned partners work on the lead concurrently
  - Each assignment has status: `active`, `won`, or `lost`
  
- [x] **Winner Selection**:
  - Admin marks one partner as winner when deal closes
  - Winner gets `status: won` with `won_at` timestamp
  - Other active partners automatically get `status: lost` with `lost_at` timestamp
  - `selling_partner_id` is set to the winning partner
  
- [x] **Partner Removal**:
  - Admin can remove partners (mark as lost) before deal closes
  - Removed partners can be re-activated later
  
- [x] **UI Updates**:
### Phase 6 - Multi-Partner Concurrent Assignment (Feb 24, 2025)
  - "Assigned Partners (X active)" section on Lead Detail
  - Status badges: Winner (green), Active (blue), Lost (red)
  - "Assign Partner" button to add more partners
  - "Mark Won" and "Remove" buttons for active partners

### Phase 7 - Dependent Dropdowns in Add Lead (Dec 2025)
- [x] Category → Sub-category → Selling Partner cascading dropdowns on `/leads/new`
- [x] `GET /api/users/selling-partners?subcategory_id=...` filters by company-to-subcategory mapping
- [x] `UserResponse.subcategory_ids` now exposed (inherited from selling-partner's company)
- [x] Auto-clears downstream selections when upstream changes; SP dropdown disabled until sub-category picked
- [x] Edit Lead: existing partner remains visible even if company is no longer mapped (`[not mapped]` hint)

### Phase 8 - Partner Mappings Admin Utility (Dec 2025)
- [x] New admin page `/partner-mappings` with two views:
  - **By Sub-category** (default): pick a sub-category, toggle each partner company
  - **Matrix**: companies × sub-categories grid, grouped by primary category, sticky headers, per-column bulk map/clear, primary-category & company-search filters
- [x] `GET /api/master/partner-mappings` lists all SP companies + current subcategory_ids
- [x] `POST /api/master/partner-subcategory-toggle` atomic add/remove ($addToSet / $pull)
- [x] Sidebar nav entry added (admin only)

## Key API Endpoints

### Multi-Partner Assignment
- `POST /api/leads/{id}/assign-partner` - Assign additional partner to lead
- `POST /api/leads/{id}/mark-partner-won` - Mark partner as winner (others become lost)
- `POST /api/leads/{id}/remove-partner` - Remove partner (mark as lost)

### Customer User Management
- `GET /api/customers/company-users` - List company users
- `POST /api/customers/company-users` - Create company user
- `PUT/DELETE /api/customers/company-users/{id}` - Update/Delete user

### Internal Requests
- `GET /api/leads/internal-requests` - List internal service requests (Selling Partner)

## Data Models

### Partner Assignment (in Lead)
```json
{
  "assigned_partners": [
    {
      "partner_id": "uuid",
      "partner_name": "Partner Name",
      "assigned_at": "2025-02-24T10:00:00Z",
      "assigned_by": "admin_user_id",
      "assigned_by_name": "Super Admin",
      "status": "active|won|lost",
      "won_at": "2025-02-24T12:00:00Z",
      "lost_at": null,
      "notes": "Assignment notes"
    }
  ],
  "active_partners_count": 2,
  "selling_partner_id": "winner_partner_id"
}
```

## Test Credentials
- **Super Admin**: admin@vyapaarnetwork.com / admin123
- **Customer**: john@testco.com / test123

## Prioritized Backlog

### P0 - Critical (Requires User Input)
- [ ] **SendGrid API Key**: For email notifications
- [ ] **Twilio Credentials**: For SMS notifications

### P1 - High Priority
- [ ] Automated follow-up email reminders
- [ ] Lead auto-routing by partner categories
- [ ] Dashboard date range filters

### P2 - Medium Priority
- [ ] Dark mode toggle
- [ ] Real-time notifications (WebSocket)

## Test Reports
- `/app/test_reports/iteration_7.json` - Customer User Management tests
- `/app/test_reports/iteration_8.json` - Multi-Partner Assignment tests (100% pass)
