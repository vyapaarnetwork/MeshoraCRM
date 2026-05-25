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

### Phase 15 - Revenue Contracting Phase 3 — AI suggestions, PDF invoices, Kanban (Feb 24, 2026)
- [x] **AI milestone templates** — `POST /api/commercials/ai/suggest-milestones` uses **Gemini 3 Pro** via the Emergent LLM key + sample of recent past one-time deals as in-context examples. Returns 3-5 milestones with name, description, percentage, amount (auto-computed), delivery_date (offset from project start), delivery_offset_days. Sum-to-100 normalisation + last-row rounding correction. Frontend: "AI suggest" button on Milestones tab with confirm dialog before replacing existing milestones.
- [x] **Renewal probability score** — `GET /api/commercials/{id}/ai/renewal-probability` returns probability (0-1) + band + factor list. Heuristic-based (no LLM): auto_renewal, renewal_type, payment-history strength, overdue count, contract tenure. Frontend card on Overview tab with progress bar + factor list.
- [x] **Payment-delay risk score** — `GET /api/commercials/{id}/ai/payment-delay-risk` returns avg historical pay-lag + per-invoice risk score, band, factors. Heuristic-based. Frontend card on Overview tab showing top 4 risky invoices.
- [x] **Kanban view** — `GET /api/commercials/kanban` returns columns grouped by contract_status (active, renewal_due, renewed, on_hold, expired, cancelled) + one_time bucket. RBAC: selling partners see only their own. New page at `/commercials/kanban`, nav link added.
- [x] **PDF invoice generation** — `GET /api/commercials/{id}/invoices/{inv_id}/pdf` builds a clean A4 PDF with reportlab (brand header, billed-to, project, line items, paid/due amounts, notes). Frontend: Download-PDF icon button next to each invoice row.
- [x] **Testing** — testing_agent_v3_fork iteration_12: Phase 3 = **20/20 backend (100%)** including real LLM call, **100% frontend on requested flows**, all RBAC checks pass.

### Phase 16 - Backend refactor — extracted routers/commercials.py (Feb 24, 2026)
- [x] **Moved 1559 lines** from `server.py` → `routers/commercials.py`:
  - server.py: 6337 → **4782 lines** (-24.5%)
  - routers/commercials.py: **1601 lines** (clean module with its own enums, models, helpers, and `APIRouter()`)
- [x] **Dependency direction**: `server.py` imports `routers.commercials.router` AT THE BOTTOM (after all top-level globals are defined), so `routers/commercials.py` can safely `from server import db, get_current_user, UserRole, NotificationType, create_notification, UPLOAD_DIR, logger`.
- [x] **Mount**: `api_router.include_router(commercials_router)` keeps all existing route paths intact (`/api/commercials/...`).
- [x] **Smoke tested** all commercials endpoints post-extraction (List, Dashboard, Kanban, Analytics, Renewal scan, Reminder scan, AI suggest, PDF download) — all return 200 / valid responses. Lint clean.

### Phase 17 - Login redesign + new Meshora brand mark (Feb 25, 2026)
- [x] **New SVG brand mark** — created `MeshoraLogo.jsx` with `MeshoraMark` (purple-violet gradient infinity/M loop) + `MeshoraLogo` (mark + wordmark with gradient text) + `MeshoraLogoOnDark` (mark + white wordmark for dark sidebars). Pure inline SVG, themeable, no raster assets.
- [x] **Login page redesign** — two-panel layout matching the user's mockup:
  - Left: dark gradient (#312E81 → #0F172A) with constellation pattern + glow blobs + `MeshoraLogoOnDark` at top + "Connect. Collaborate. Grow Together." hero + 3 feature chips (Stronger Connections / More Opportunities / Better Results) + copyright at bottom
  - Right: white/dark card with "Welcome back" heading, Email + Password inputs with leading icons, Remember-me + Forgot password row, gradient "Sign in" button with arrow, divider, disabled "Sign in with Google" placeholder, "Don't have an account? Create account" link, security card ("Secure. Reliable. Always.")
- [x] **Removed demo admin credentials box** from Login page
- [x] **Layout.jsx sidebar logo** swapped from raster `<img>` to the new `MeshoraLogoOnDark` SVG (desktop + mobile + collapsed states + mobile header)
- [x] **Mobile-friendly**: small Meshora mark + gradient wordmark in mobile login header; responsive at <lg breakpoints (left panel hides)

### Phase 19 — Revenue OS Phase 1: Activity Timeline + Health Score + Next Action + Smart Follow-ups + @mentions (Feb 25, 2026)
- [x] **Unified Activity Timeline** — `GET /api/leads/{id}/activity` aggregates lead creation + comments + follow-ups (scheduled & completed) + partner assignments (assigned/won/lost) + commercial activity into a single reverse-chronological feed. Frontend: new `ActivityTimeline.jsx` component on Lead Detail page with search + event-type filter + colored type badges + per-event icons.
- [x] **Lead Health Score** — `GET /api/leads/{id}/health` returns a heuristic 0-100 score + band (hot/warm/cold/at_risk) + factor list. Factors: recent activity, follow-up completion rate, overdue follow-ups (penalty), deal value tier. Frontend: `HealthScoreBadge` (header) + `HealthScoreCard` (sidebar with bar + factor breakdown).
- [x] **Next Action Widget** — rules-engine recommendation on every lead. Same endpoint returns `{label, reason, urgency, action_type, ref_id}`. Priority order: overdue follow-up > won-but-no-commercial > no pending follow-up > no partner > at-risk re-engage > touch-base. Frontend `NextActionCard.jsx` shows urgency-colored card with "Take action" button that wires to the correct handler (open follow-up form, complete follow-up, setup commercials, assign partner, scroll to comments).
- [x] **Smart Follow-up Management** — `PATCH /api/leads/{id}/follow-ups/{fid}/snooze` to reschedule pending follow-ups. Frontend: quick-preset buttons (Tomorrow / +3 days / Next week / +2 weeks / Next month) inside the schedule form AND in the snooze dropdown per row. Overdue follow-ups are highlighted in red with an "Overdue" pill and an alarm icon. Sorting: overdue → pending → completed.
- [x] **@mentions in comments** — backend regex parses `@username` tokens from comment content and resolves to active users by name OR email-local-part (case-insensitive prefix match); emits `lead_mention` in-app notification to each matched user. Frontend: new `CommentInputWithMentions.jsx` shows a live autocomplete dropdown when user types `@`; supports keyboard nav (↑↓ Enter Tab Esc). Mentioned `@` tokens render in violet inside the rendered comment body.
- [x] New `NotificationType.LEAD_MENTION = "lead_mention"` enum value.
- [x] **Testing** — backend smoke-tested via curl: health endpoint returns 75/hot for active lead, activity endpoint aggregates 2 events for a fresh lead, @Finance + @Ops mention notifications successfully delivered to vyapaar_finance & vyapaar_ops users.
- [x] **Health column + filter on Leads list page** (Feb 25, 2026) — new lightweight batch endpoint `GET /api/leads/health-summary` returns `{results: [{id, health: {score, band, days_inactive}, next_action: {label, urgency}}]}` for all visible leads (role-scoped query). Leads.jsx merges health data client-side and renders a sortable Health column with `HealthScoreBadge size="sm"` per row. Added a Health filter dropdown (All / 🚨 At Risk / ❄️ Cold / ☀️ Warm / 🔥 Hot) + "Clear filters" button. Verified end-to-end: 75 total leads → 44 hot / 31 at_risk distribution, "At Risk" filter narrows table to 31 rows.

### Phase 19.5 — Revenue OS Phase 1 Quick Wins: Tasks + Threaded Comments + Dashboard Digest (Feb 25, 2026)
- [x] **Threaded comments** — `CommentCreate` model gains `parent_comment_id`; `CommentResponse` returns it. Frontend `CommentsCard.jsx` builds a thread tree (recursive `CommentItem`), shows a "Reply" button per comment (max depth 3), threads are rendered with indentation + left border + `CornerDownRight` indicator. `LeadDetail.handleReplyComment` posts the reply with `parent_comment_id`.
- [x] **Tasks (separate from follow-ups)** — new `tasks` Mongo collection. Endpoints: `POST /api/tasks`, `GET /api/tasks?lead_id=…&mine=true&status=…`, `PATCH /api/tasks/{id}`, `DELETE /api/tasks/{id}`. Model fields: title, description, assignee_id (defaults to creator), lead_id, commercial_id, due_date, priority (low/medium/high), status (todo/in_progress/done), created_by, completed_at. When a task is assigned to a different user, a `task_assigned` in-app notification is emitted. Frontend `TasksCard.jsx` renders on Lead Detail with inline create form (title, description, assignee, priority, due date), per-row status toggle (checkbox), status dropdown menu, and delete. Sorted: todo → in_progress → done, then by due date.
- [x] **Dashboard digest widget** — new `GET /api/dashboard/digest` returns `{leads: {total, hot, warm, cold, at_risk, gone_cold_this_week}, follow_ups: {overdue, today}, mentions: {unread}, tasks: {open, overdue}}` for the current user (role-scoped). Frontend `DashboardDigest.jsx` shows 4 clickable accent-colored tiles (Overdue Follow-ups, At-Risk Leads, Unread Mentions, My Open Tasks) with rose/amber/violet/sky/slate accents, plus a "Lead health distribution" gradient bar. Mounted at the top of `/dashboard` page. Tile clicks navigate to /leads or /notifications.
- [x] New `NotificationType.TASK_ASSIGNED = "task_assigned"` enum value.
- [x] **Verified end-to-end** — created a task via curl (id returned, assignee resolved, status transitions to in_progress); posted a threaded reply (parent_comment_id stored); dashboard digest endpoint returns full counts (3 overdue follow-ups, 31 at-risk, 0 mentions, 3 tasks). Frontend Playwright smoke tested: digest tile + reply buttons + Tasks form all render.

### Phase 20 — AI Meeting Summaries (Feb 25, 2026)
- [x] **`POST /api/leads/{id}/ai/meeting-summary`** — accepts `raw_notes` (up to 25K chars), `meeting_date`, `auto_create_tasks` boolean. Calls Gemini 3 Pro via `emergentintegrations` SDK with a strict-JSON system prompt extracting: summary, risks, opportunities, next_steps, action_items, sentiment (positive/neutral/negative/mixed), key_stakeholders.
- [x] **Storage** — the structured summary is persisted both as a comment with embedded `meeting_summary` payload (so it shows in the unified Activity Timeline and CommentsCard) AND in a new top-level `lead.meeting_summaries[]` array for history retrieval.
- [x] **Auto-task creation** — when `auto_create_tasks=true`, each action item becomes a real Task in the `tasks` collection with `source="ai_meeting_summary"`, mapped priority (low/medium/high), and computed `due_date = today + due_in_days`. Returned `created_task_ids` count is shown in the dialog.
- [x] **`GET /api/leads/{id}/ai/meeting-summaries`** — paginated history endpoint returning all summaries for a lead (newest first).
- [x] **Frontend `AIMeetingSummaryDialog.jsx`** — full-featured modal with date picker, large textarea (with char counter / max 25K), "Auto-create tasks from action items" checkbox, gradient violet→indigo submit CTA labelled "Analyzing… (~10s)" during the LLM call. Result view renders summary card with sentiment badge, color-coded sections (Risks/Opportunities/Next Steps), Key stakeholder chips, and a list of extracted action items with a "X task(s) created" emerald badge.
- [x] **Lead Detail integration** — new "AI Summary" button (sparkle icon, violet outline) in the lead detail header next to Edit Lead. On success, both the lead and health/activity feeds are refreshed.
- [x] **Rich rendering in comments** — `MeetingSummaryRender` sub-component inside CommentsCard detects the `meeting_summary` field on a comment and renders a gradient violet→indigo card with sentiment badge + bulleted Risks/Opportunities/Next steps lists inline, so the summary stays beautiful inside the threaded comment view.
- [x] **Verified live with Gemini** — sent a sample Acme Corp note ("Met with Priya from finance team … Ravi worried about Okta SSO … 250 sales reps expansion") and Gemini correctly extracted 3 risks, 1 opportunity, 3 next steps, 2 action items, 3 stakeholders (Priya, Ravi, CISO) with positive sentiment. 2 tasks auto-created on lead.

### Phase 21 — Revenue Intelligence + Stakeholders + Smart Notifications Engine (Feb 25, 2026)
- [x] **Revenue Intelligence dashboard** — new `GET /api/dashboard/revenue-intelligence?start_date=&end_date=` returning role-scoped: KPIs (total_pipeline, weighted_pipeline using `_STATUS_PROBABILITY` heuristic map, won_value, won_count, avg_deal_size, win_rate, at_risk_value, MRR/ARR from recurring commercials by billing_cycle, total_leads), pipeline_by_stage (with colors), top_partners (won_revenue + conversion), forecast (3-month weighted spread), win_rate_trend (last 6 months), health_value_distribution. Frontend `/revenue-intelligence` page renders 8 gradient KPI cards + 4 recharts (BarChart pipeline-by-stage, PieChart pipeline-value-by-health, LineChart win-rate-trend, AreaChart revenue-forecast) + top-partners ranked list. Date range filter (From/To/Apply). Accessible to admin/ops/finance/selling-partner.
- [x] **Stakeholder Relationship Mapping** — new `lead.stakeholders[]` embedded array. Endpoints: `GET/POST /api/leads/{id}/stakeholders`, `PATCH/DELETE /api/leads/{id}/stakeholders/{sid}`. Validation on `role_type` (decision_maker, influencer, technical_evaluator, finance_approver, blocker, champion, end_user, other) and `engagement` (supportive/neutral/resistant/unknown). Frontend `StakeholderCard.jsx` on Lead Detail: role icon (Crown/ShieldCheck/Wrench/$/Ban/Star/User), role badge + engagement badge, title, email, phone, notes, edit/remove dropdown, full create/edit dialog.
- [x] **Smart Notifications Engine** — new `POST /api/notifications/run-rules` admin endpoint. Three rules implemented with `dedup_key` deduplication so re-runs don't spam:
  - **R1** Lead quiet 10+ days → notifies lead owner + active partners
  - **R2** Lead in 'Proposal' stage + overdue follow-up → notifies owner + active partners
  - **R3** High-value lead (≥₹10L) at-risk → notifies all admins/ops
  - First run fired **34 notifications** across the 75 existing leads (verified).
- [x] **New NotificationType values**: `RULE_LEAD_INACTIVE`, `RULE_PROPOSAL_PENDING`, `RULE_HIGH_VALUE_AT_RISK`.
- [x] **"Run Smart Rules" button** on Revenue Intelligence page (admin/ops only) shows toast with fired count.
- [x] **Sidebar nav** — new "Revenue Intelligence" link with `TrendingUp` icon for super_admin / vyapaar_ops / vyapaar_finance / selling_partner.
- [x] **ProtectedRoute `/revenue-intelligence`** allows admin-like roles + selling_partner.





### Phase 18 - New Vyapaar Roles + Register redesign + Component decomposition (Feb 25, 2026)
- [x] **Two new UserRole enum values** — `vyapaar_ops` ("Vyapaar Operations") and `vyapaar_finance` ("Vyapaar Finance") added to backend `UserRole` enum and surfaced in Users.jsx role dropdown + role filter. Updated `getRoleLabel` / `getRoleColor` in `utils/api.js` with appropriate labels and color badges (indigo for Ops, amber for Finance).
- [x] **Role → permissions mapping in `get_current_user`** (server.py:508-545):
  - `vyapaar_ops` → sets `is_vyapaar_ops=True` (existing flag system: full app access except user/company/category CREATE)
  - `vyapaar_finance` → sets `is_finance=True` + `is_vyapaar_ops=True` (read everything) + new `is_finance_only_role=True` flag
  - `is_finance_only_role` users get a 403 block on any POST/PUT/PATCH/DELETE outside `/api/commercials`, `/api/notifications`, `/api/auth` (centralized middleware-style check)
- [x] **`/api/auth/me` returns un-elevated role + flags derived from the user's actual stored role** so frontend can distinguish ops vs finance vs super_admin properly without seeing synthetic elevation values
- [x] **AuthContext exposes** `isVyapaarFinance` + `canEditLeadsCompanies` (true for admin and ops, false for finance)
- [x] **Sidebar nav** (`Layout.jsx`) — `ADMIN_ROLES` now includes `vyapaar_ops` and `vyapaar_finance` so they see Users / Companies / Categories / Partner Mappings / Commission / Document Tags / Email Templates / Grid Report
- [x] **`ProtectedRoute`** in `App.js` — when `allowedRoles` includes `super_admin`, both `vyapaar_ops` and `vyapaar_finance` are also allowed (read-everything semantics)
- [x] **Register.jsx redesign** — fully rewritten to mirror Login.jsx 2-panel layout: dark gradient left panel with constellation pattern + `MeshoraLogoOnDark` + "Join the Meshora Network" hero + 3 feature chips (Quick Setup / Verified Partners / Scale Faster); right panel has icon-prefixed input fields, gradient submit, and security card
- [x] **MeshoraLogo pulse animation** — `MeshoraMark` now has a subtle scale-pulse on the central knot dot (2.8s ease-in-out) + alternating fade on the sparkle dots. Respects `prefers-reduced-motion`. New `animated` prop (default `true`) to toggle.
- [x] **`Companies.jsx` decomposed** (763 lines → ~280 line orchestrator + 3 sub-components):
  - `pages/companies/CompanyTable.jsx` — table rendering
  - `pages/companies/CompanyFormDialog.jsx` — Add/Edit dialog with SubcategoryPicker + DefaultUserSection
  - `pages/companies/CompanyDocumentsDialog.jsx` — documents viewing dialog
- [x] **`LeadDetail.jsx` decomposed** (872 lines → ~290 line orchestrator + 5 sub-components):
  - `pages/leadDetail/LeadOverviewCards.jsx` — LeadOverviewCard + CustomerInfoCard + CommissionBreakdownCard
  - `pages/leadDetail/CommentsCard.jsx`
  - `pages/leadDetail/AssignedPartners.jsx` — AssignedPartnersCard + AssignPartnerDialog
  - `pages/leadDetail/FollowUpsCard.jsx`
  - `pages/leadDetail/DocumentsCard.jsx`
  - Wires `canEditLeadsCompanies` so Vyapaar Operations users see admin-level lead controls (Edit Lead, Assigned Partners management)
- [x] **Testing** — backend pytest 27/28 (96.4%, single failure was a test-script payload mismatch on `/comments`, not a server bug). Frontend Playwright smoke verified Login, Register, Companies, LeadDetail, Users pages all render correctly for both new role accounts.
- [x] **Role context banner** (`RoleContextBanner.jsx`) — when a `vyapaar_ops` or `vyapaar_finance` user logs in, a subtle full-width banner appears under the top header showing "You're viewing as Vyapaar Operations / Finance" with their permission summary. Indigo accent for Ops, amber accent for Finance. Dismissible per session via `sessionStorage`. Respects dark mode.

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
- **Vyapaar Operations**: ops_test@meshora.com / ops123456
- **Vyapaar Finance**: fin_test@meshora.com / fin123456

## Prioritized Backlog

### P0 - Critical (Requires User Input)
- [ ] **SendGrid API Key**: For email notifications
- [ ] **Twilio Credentials**: For SMS notifications

### P1 - High Priority
- [ ] Automated follow-up email reminders
- [ ] Lead auto-routing by partner categories
- [x] Dashboard date range filters (Feb 24, 2026)
- [x] **Refactor `server.py` (6300+ lines) → extract `routers/commercials.py`** (1559 lines moved; server.py now 4782 lines; Feb 24, 2026)
- [ ] Fix 32 React Hook dependency warnings (deferred — features prioritized)
- [ ] **Extract `routers/leads.py`** from server.py (~20 lead endpoints scattered in server.py; deferred to a future session per risk-vs-value tradeoff)
- [x] **Commercials Phase 2** — renewal pipeline auto-creation, analytics page (MRR/ARR/churn/forecast), drag-drop milestone reorder, audit/activity search+filter, is_finance/is_delivery role flags (Feb 24, 2026)
- [x] **Commercials Phase 2.5 — In-app reminders** (Feb 24, 2026): in-app notifications for milestone-due, billing-due, invoice-overdue, renewal-window with dedup. SendGrid/Twilio hooks scaffolded — pending API keys to activate.
- [x] **Commercials Phase 3** — AI milestone templates (Gemini 3 Pro), renewal probability, payment-delay risk, Kanban view, PDF invoice generation (Feb 24, 2026)
- [ ] **Commercials Phase 2.6 — Email + SMS activation**: drop SendGrid + Twilio keys into `.env` and uncomment the hooks in `_emit_commercial_reminder` to enable real email/SMS sending.

### P2 - Medium Priority
- [x] Dark mode toggle (Feb 24, 2026)
- [ ] Real-time notifications (WebSocket)
- [x] **Refactor `Companies.jsx` (687 lines) and `LeadDetail.jsx` (843 lines)** into smaller sub-components (Feb 25, 2026 — Phase 18)
- [ ] **Move JWT from localStorage → HttpOnly cookies** (security-critical; deferred per user request — too risky for this session)

## Test Reports
- `/app/test_reports/iteration_7.json` - Customer User Management tests
- `/app/test_reports/iteration_8.json` - Multi-Partner Assignment tests (100% pass)
