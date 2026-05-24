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
- [x] `GET /api/master/partner-mappings` lists all SP companies + current subcategory_ids + `active_user_count`
- [x] `POST /api/master/partner-subcategory-toggle` atomic add/remove ($addToSet / $pull)
- [x] Sidebar nav entry added (admin only)

### Phase 9 - SP "No Users" Gap Closure (Dec 2025)
- [x] **Auto-create default Selling Partner user** when creating a selling-partner company (mirrors customer flow). Companies.jsx now shows "Default Selling Partner User" section + validation; `create_company` backend extended.
- [x] **"⚠ No users" badge** on Partner Mappings (list + matrix) for SP companies with 0 active SP users — they would never appear in lead dropdowns.
- [x] **Inline "Add User" dialog** in Partner Mappings rows + matrix cells; creates an SP user under that company via `POST /api/users` and refreshes counts.
- [x] **LeadForm "No partners" copy clarified** — explicitly mentions either no company mapping OR no active SP user on the mapped companies, with a deep link to `/partner-mappings`.

### Phase 10 - Dashboard Health Check Widget (Dec 2025)
- [x] **New admin-only Dashboard widget** surfaces configuration & workflow gaps proactively
- [x] **5 checks** (sorted critical → warning → info):
  - SP companies with no active users (warning)
  - SP companies with no sub-category mapping (warning)
  - Sub-categories with no partner mapped (info)
  - Leads stuck in Draft > 7 days (critical)
  - Active leads with no partner for > 3 days (warning)
- [x] **`GET /api/dashboard/health-check`** endpoint, single bulk aggregation per check, examples list per item, "Fix" deep links to the relevant admin page
- [x] **"All systems healthy"** empty state when there are zero issues

### Phase 11 - Meshora Rebranding, Dark Mode & Dashboard Date Filters (Feb 24, 2026)
- [x] **Meshora rebranding** — replaced Vyapaar logos with new Meshora artifacts:
  - `LOGO_DARK_BG_URL` (white text on black) → sidebar (always dark) & dark-mode mobile header
  - `LOGO_LIGHT_BG_URL` (dark text on white) → light-mode mobile header
  - Page title updated to "Meshora — Collaboration That Converts"
- [x] **"Powered by Vyapaar Network" footer** — visible at the bottom of both desktop sidebar (expanded + collapsed) and mobile drawer, with small Vyapaar logo
- [x] **Dark mode toggle** — new `ThemeContext.jsx` provider, Sun/Moon icon in topbar, persisted to `localStorage`, applies `dark` class to `<html>`; Tailwind dark variants applied to header
- [x] **Dashboard date filters** — 5 presets (All time, Today, Last 7d, Last 30d, This month) + manual From/To `<Input type="date">` + Clear button; wired to `GET /api/dashboard/stats?start_date=&end_date=` (end_date promoted to `YYYY-MM-DDT23:59:59` for inclusive day)

### Phase 12 - Revenue Contracting & Delivery Management — MVP (Feb 24, 2026)
- [x] **Closed-Won wizard** (`ClosedWonWizard.jsx`) — opens via "Set Up Commercials" button on Lead Detail (admin only) AND auto-triggers when lead status `is_won=true` and no commercial exists yet. Lets admin pick **One-Time Project** or **Recurring Contract**, creates `commercial` doc and navigates to `/commercials/:id`.
- [x] **Lead status `is_won` flag** added to `LeadStatus` master (Create/Response models + startup backfill that marks existing "Won" status as `is_won=true`). `LeadResponse.status_is_won` exposed.
- [x] **Commercial Detail page** (`/commercials/:id`) with tabs:
  - **Overview** — full setup form (currency, total/contract value, dates, owners, billing contact, renewal options, notes); Save + "Regenerate billing schedule" for recurring
  - **Milestones** (one-time) — table with add/remove, up/down reorder, auto-percent ↔ amount calc, live validation banner (amounts must equal project value, % must total 100), per-row status select, timeline visualization, "Raise invoice" shortcut
  - **Billing Schedule** (recurring) — auto-generated periods table with Raise-invoice per row; regenerate button
  - **Invoices & Payments** — list both sides; record payment dialog auto-updates invoice/milestone/billing status (paid → milestone payment_received, billing → paid)
  - **Documents** — upload (proposal/SOW/contract/invoice/other), download, delete
  - **Activity** — chronological log of every commercial event
- [x] **Commercials List** (`/commercials`) — card grid with type filter + search; admin sees all, selling partner sees only their leads.
- [x] **Dashboard widget** (`CommercialsWidget.jsx`) — admin-only snapshot: One-time projects count + value + realized + overdue invoices + upcoming milestones; Recurring active subs + MRR + ARR + Renewals(60d) with deep links.
- [x] **Backend API**:
  - `POST/GET/PATCH /api/commercials`, `GET /api/commercials/by-lead/{lead_id}`
  - `PUT /api/commercials/{id}/milestones` with hard validation
  - `PATCH /api/commercials/{id}/milestones/{mid}` status updates
  - `POST /api/commercials/{id}/regenerate-billing` (recurring only; rejects one_time)
  - `POST/GET/PATCH /api/commercials/{id}/invoices` (auto-links to milestone/billing schedule)
  - `POST/GET /api/commercials/{id}/payments` (full payment → invoice paid + milestone payment_received)
  - `POST/GET/DELETE /api/commercials/{id}/documents` + `/download`
  - `GET /api/commercials/{id}/activity`
  - `GET /api/commercials/dashboard` (MRR, ARR, upcoming renewals, project metrics)
- [x] **RBAC**: Admin = full. Selling Partner = read-only on own leads' commercials. Sales Associate / Customer = 403.
- [x] **Billing schedule generator** — monthly / quarterly / half-yearly / annual, clamps to last day of month, capped at 240 periods.
- [x] **Activity logging** — every state change (create / update / milestone change / invoice raise / payment / document upload+delete) recorded with user + timestamp.
- [x] **Currency** — single field per contract (INR default, USD/EUR/GBP supported), no FX conversion.

### Phase 13 - Revenue Contracting Phase 2 (Feb 24, 2026)
- [x] **Renewal pipeline auto-creation** — `POST /api/commercials/run-renewal-scan` scans every recurring contract whose `contract_end_date - renewal_notice_days ≤ today`. For each match without an existing renewal lead, it:
  - ensures a `Renewal` lead status exists (auto-seeded)
  - auto-creates a Lead with `status=Renewal`, copying customer + partners + categories from the original
  - sets `commercial.contract_status='renewal_due'` and `commercial.renewal_lead_id=<new_lead_id>`
  - logs `renewal_lead_created` activity event
  - **Idempotent** — re-runs do not duplicate
  - Auto-triggered silently on Dashboard widget mount, plus a manual button on the Analytics page
  - "Renewal pipeline" link added to commercial detail header when linked
- [x] **Revenue Analytics page** (`/commercials/analytics`) — admin/finance/delivery:
  - KPIs: Current MRR, ARR, Active contracts, Churn (this month), 90-day forecast
  - MRR & ARR area trend (configurable 6/12/24/36 month window)
  - Contract flow (new vs churned per month)
  - Revenue mix pie (one-time vs recurring lifetime)
  - Revenue collected vs invoiced bars
  - 90-day forecast breakdown (pending invoices + recurring billings + project milestones)
  - Powered by new `GET /api/commercials/analytics?months=N` endpoint
- [x] **Drag-drop milestone reorder** — milestone rows are now draggable (`GripVertical` handle + HTML5 drag/drop); arrow buttons retained for fine control
- [x] **Activity / Audit log enhancement** — search box + event-type filter on the Activity tab; metadata expandable inline (`<details>` block); event-type badge on each entry
- [x] **`is_finance` / `is_delivery` user role flags** — added to UserBase/Response, AdminUserCreate/Update, Users page admin dialog ("Commercials Permissions" section). Wired through `auth/me`, `auth/login`, `GET /users`, `POST /users`, `PUT /users/{id}`. Both flags grant full commercials write access (parallel to admin); navigation auto-shows "Commercials" + "Revenue Analytics" for finance/delivery users regardless of base role.
- [x] **AuthContext** exposes `isFinance`, `isDelivery`, `canAccessCommercials`, `canWriteCommercials`.
- [x] **Testing** — testing_agent_v3_fork iteration_10: backend 100% (50/50 tests), frontend ~98%. No critical issues. Two polish fixes applied post-test (improved renewal-scan toast wording, added `minHeight` to Recharts containers).
- ⏭ **Deferred to Phase 2.5** (per user request): SendGrid milestone-due / invoice-overdue / renewal reminder emails, Twilio SMS reminders, AI suggestions, PDF invoice generation, kanban view.

### Phase 14 - Revenue Contracting Phase 2.5 — In-app reminders (Feb 24, 2026)
- [x] **POST /api/commercials/run-reminder-scan** — scans all commercials and emits in-app notifications for:
  - Milestones due within `milestone_lead_days` (default 3) — `commercial_milestone_due`
  - Invoices past their `due_date` and still unpaid — `commercial_invoice_overdue` (re-pings once per day until paid)
  - Recurring billings due within `milestone_lead_days` — `commercial_billing_due`
  - Contracts inside their renewal-notice window — `commercial_renewal_window`
- [x] **Dedup**: 20-hour window per `(user_id, type, commercial_id, data.dedup_key)`. Dedup keys include the entity id + due date so re-runs on the same day are safely no-ops.
- [x] **Recipients**: union of all owner fields on the commercial (project_owner, delivery_spoc, billing_contact, account_manager, contract_owner, created_by) + all active super-admins.
- [x] **NotificationType** extended with 4 new values: `commercial_milestone_due`, `commercial_billing_due`, `commercial_invoice_overdue`, `commercial_renewal_window`.
- [x] **NotificationResponse.commercial_id** now surfaces for all notifications (None for legacy, populated for commercial-*).
- [x] **Layout.jsx topbar dropdown** — clicking a commercial_* notification deep-links to `/commercials/:id`; icon mapping (Briefcase amber for milestone/billing, red for invoice overdue, blue for renewal window).
- [x] **"Send reminders" button** on the Revenue Analytics page (admin/finance/delivery).
- [x] **CommercialsWidget** silently triggers both `run-renewal-scan` and `run-reminder-scan` on mount.
- [x] **Email + SMS placeholders** — `_emit_commercial_reminder` has clearly commented hooks to drop in `send_email(...)` / `send_sms(...)` calls when keys are configured later. No mocking; in-app only by design.
- [x] **Testing** — testing_agent_v3_fork iteration_11: Phase 2.5 = 10/10 (100%); combined Phase 1+2+2.5 = 59/60 (98.3%, 1 transient timeout). Frontend ~95%, all flows green.

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
- [x] Dashboard date range filters (Feb 24, 2026)
- [ ] Refactor `server.py` (5750+ lines → modular routers; commercials slice is largest contained candidate)
- [ ] Fix 32 React Hook dependency warnings
- [x] **Commercials Phase 2** — renewal pipeline auto-creation, analytics page (MRR/ARR/churn/forecast), drag-drop milestone reorder, audit/activity search+filter, is_finance/is_delivery role flags (Feb 24, 2026)
- [x] **Commercials Phase 2.5 — In-app reminders** (Feb 24, 2026): in-app notifications for milestone-due, billing-due, invoice-overdue, renewal-window with dedup. SendGrid/Twilio hooks scaffolded — pending API keys to activate.
- [ ] **Commercials Phase 2.6 — Email + SMS activation**: drop SendGrid + Twilio keys into `.env` and uncomment the hooks in `_emit_commercial_reminder` to enable real email/SMS sending.

### P2 - Medium Priority
- [x] Dark mode toggle (Feb 24, 2026)
- [ ] Real-time notifications (WebSocket)
- [ ] Refactor large React components (Companies.jsx 687 lines, LeadDetail.jsx 713 lines)
- [ ] Move JWT from localStorage to HttpOnly cookies
- [ ] **Commercials Phase 3** — AI suggestions (suggested milestone structures from past deals, renewal probability, payment delay risk), PDF invoice generation, kanban view

## Test Reports
- `/app/test_reports/iteration_7.json` - Customer User Management tests
- `/app/test_reports/iteration_8.json` - Multi-Partner Assignment tests (100% pass)
