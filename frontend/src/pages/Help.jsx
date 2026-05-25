import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import {
  Sparkles, Users, MessageSquare, TrendingUp, Trophy, Search, Link2, ShieldCheck,
  Activity, Brain, FileText, CheckCircle2, BookOpen, Command, Bell, Target,
  Mail, BarChart3, Heart, ClipboardList, Building2, AtSign, Settings, Map,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const CATEGORIES = [
  {
    id: 'ai',
    label: 'AI-Powered Features',
    icon: Brain,
    color: 'from-violet-500 to-indigo-500',
    items: [
      {
        title: 'AI Command Bar',
        icon: Command,
        shortcut: 'Cmd+K / Ctrl+K',
        description: 'Ask Meshora anything in natural language. Type queries like "show me at-risk leads in healthcare" or "deals worth more than 1 lakh" and the AI converts them into the right filter for you.',
        examples: [
          '"Show me hot leads inactive for 5 days"',
          '"Deals in healthcare worth more than 50000"',
          '"Top performing partners"',
          '"At-risk leads that need follow-up"',
        ],
        whyItHelps: 'Skip the filter modal — just describe what you need. The AI grounds itself with your actual statuses, categories, and partner names so results match your data.',
        roles: ['super_admin', 'selling_partner', 'sales_associate', 'vyapaar_ops', 'vyapaar_finance'],
      },
      {
        title: 'AI Deal Risk Analysis',
        icon: ShieldCheck,
        description: 'Click the "Analyze Risk" button on any lead detail page. The AI reviews recent activity, days since last contact, status velocity, and stakeholder coverage to surface what could derail this deal.',
        whyItHelps: 'Catches subtle warning signs before they become lost deals — and tells you exactly what to fix next.',
        roles: ['super_admin', 'selling_partner', 'vyapaar_ops'],
      },
      {
        title: 'AI Follow-up Assistant',
        icon: MessageSquare,
        description: 'Generates the next best follow-up message based on lead context, stage, and history. Customizes tone (formal/friendly/urgent) and produces an email/WhatsApp-ready draft.',
        whyItHelps: 'Eliminates blank-page paralysis when chasing 30+ leads a day.',
        roles: ['super_admin', 'selling_partner', 'sales_associate'],
      },
      {
        title: 'AI Meeting Summaries',
        icon: FileText,
        description: 'Paste meeting notes into the AI Summary dialog on a lead — get a structured summary with key decisions, action items, and a suggested next step.',
        whyItHelps: 'Turns 15 minutes of post-meeting cleanup into 10 seconds.',
        roles: ['super_admin', 'selling_partner', 'sales_associate'],
      },
      {
        title: 'AI Partner Coaching',
        icon: Trophy,
        description: 'In Partner Intelligence, click "AI Coach" on any partner. Gemini analyzes their win/loss patterns and recommends strengths to lean into, weaknesses to address, and a training topic for next quarter.',
        whyItHelps: 'Personalized 1:1 coaching at scale — no need to manually review every partner.',
        roles: ['super_admin', 'vyapaar_ops'],
      },
    ],
  },
  {
    id: 'collab',
    label: 'Collaborative Deal Rooms',
    icon: Users,
    color: 'from-emerald-500 to-teal-500',
    items: [
      {
        title: 'Deal Room',
        icon: Users,
        description: 'A shared workspace per lead where the customer, selling partner, and Meshora team see the same activity, approvals, and documents. Open it from the lead detail page.',
        howTo: 'On any lead, click "Open Deal Room" in the Deal Room card. The customer (matched by email) instantly gets a stripped, focused view. Internal data (deal value, commission) stays private to your team.',
        whyItHelps: 'Closes the loop between sales and customer — no more lost email threads, mystery approvals, or duplicated questions.',
        roles: ['super_admin', 'selling_partner', 'vyapaar_ops', 'customer'],
      },
      {
        title: 'Approval Requests',
        icon: CheckCircle2,
        description: 'Inside the Deal Room, request formal sign-offs from the customer, the selling partner, or anyone. Each approval has a title, optional due date, and Approve/Reject buttons gated by the assignee role.',
        whyItHelps: 'Replaces "did you sign off?" emails with a single source of truth — every decision time-stamped and attributed.',
        roles: ['super_admin', 'selling_partner', 'vyapaar_ops', 'customer'],
      },
      {
        title: 'Magic Link Invitations',
        icon: Link2,
        description: 'Invite people who don\'t have a Meshora account — e.g. customer CFO, legal counsel. Generates a secure, expiring link they can open in any browser to join the Deal Room.',
        howTo: 'In the Deal Room, click "Invite Stakeholder". Set their name, email, permissions (view / comment / approve), and expiry (default 14 days). Copy the link or open your email client.',
        whyItHelps: 'Removes friction for executive stakeholders who would never create yet another login.',
        roles: ['super_admin', 'selling_partner', 'vyapaar_ops'],
      },
      {
        title: 'Stakeholder Mapping',
        icon: Map,
        description: 'On each lead, capture the buying-committee members — champion, decision-maker, blocker, etc. — with role, sentiment, and notes.',
        whyItHelps: 'Big enterprise deals are won and lost on relationship coverage. This makes the human map explicit.',
        roles: ['super_admin', 'selling_partner', 'sales_associate'],
      },
      {
        title: '@Mentions in Comments',
        icon: AtSign,
        description: 'Type @ in any comment box to mention a teammate. They get an in-app notification and the comment is highlighted for them.',
        whyItHelps: 'Cleaner than CC-ing on every email — and the context stays attached to the lead, not buried in inboxes.',
        roles: ['super_admin', 'selling_partner', 'sales_associate', 'vyapaar_ops'],
      },
    ],
  },
  {
    id: 'revenue',
    label: 'Revenue Intelligence',
    icon: TrendingUp,
    color: 'from-amber-500 to-orange-500',
    items: [
      {
        title: 'Lead Health Score',
        icon: Heart,
        description: 'Every lead gets an auto-computed health band — Hot, Warm, Cold, or At-Risk — based on recency of activity, overdue follow-ups, stakeholder coverage, and stage velocity. Visible as a column on the Leads page.',
        whyItHelps: 'Tells you in one glance which 30 of your 300 leads need attention today.',
        roles: ['super_admin', 'selling_partner', 'sales_associate'],
      },
      {
        title: 'Revenue Intelligence Dashboard',
        icon: BarChart3,
        description: 'Trended revenue, conversion-rate funnel, win/loss by stage, partner contribution, and category mix — all in one dashboard. Filterable by date range.',
        whyItHelps: 'Replaces the spreadsheet exports your finance team used to build manually every Monday.',
        roles: ['super_admin', 'selling_partner', 'vyapaar_ops', 'vyapaar_finance'],
      },
      {
        title: 'Predictive Revenue Forecasting',
        icon: Sparkles,
        description: 'Hybrid statistical (linear regression + EMA) + pipeline-weighted forecast for the next 3 / 6 / 9 / 12 months. Each open deal gets a per-deal probability based on stage × health × recency, projecting expected close month.',
        howTo: 'Open "Predictive Forecast" from the sidebar. Pick a horizon. The chart shows historical actuals as bars, forecast as a dashed line with a confidence band. Below: month-by-month breakdown + top-20 closures expected in the next 90 days.',
        whyItHelps: 'Boardroom-ready numbers + an AI executive summary in one click.',
        roles: ['super_admin', 'selling_partner', 'vyapaar_ops', 'vyapaar_finance'],
      },
      {
        title: 'Partner Intelligence',
        icon: Trophy,
        description: 'Leaderboard of selling partners scored on composite (revenue + win-rate + speed + engagement). Plus referral conversion ratios, commission analytics, category specialization, and 6-month activity heatmap.',
        whyItHelps: 'Pinpoints your top 20% partners (and the ones who need coaching) without reading 50 individual reports.',
        roles: ['super_admin', 'vyapaar_ops', 'vyapaar_finance'],
      },
    ],
  },
  {
    id: 'ops',
    label: 'Workflow & Operations',
    icon: ClipboardList,
    color: 'from-sky-500 to-cyan-500',
    items: [
      {
        title: 'Unified Activity Timeline',
        icon: Activity,
        description: 'On each lead, a single chronological feed of every status change, comment, follow-up, document upload, partner assignment, and approval — colour-coded by event type.',
        whyItHelps: 'No more switching tabs to reconstruct "what happened on this deal?".',
        roles: ['super_admin', 'selling_partner', 'sales_associate', 'vyapaar_ops'],
      },
      {
        title: 'Smart Follow-up Management',
        icon: Bell,
        description: 'Mark follow-ups as pending or complete. Overdue ones surface on the dashboard\'s Daily Pulse and contribute to the lead\'s health band.',
        whyItHelps: 'No deal forgotten in a pipeline of 200+.',
        roles: ['super_admin', 'selling_partner', 'sales_associate'],
      },
      {
        title: 'Next Action Widget',
        icon: Target,
        description: 'Each lead suggests the single highest-impact next move based on stage, last activity, and missing data.',
        whyItHelps: 'Decision fatigue → done. Open lead, do the thing, close lead.',
        roles: ['super_admin', 'selling_partner', 'sales_associate'],
      },
      {
        title: 'Internal Tasks',
        icon: ClipboardList,
        description: 'Create per-lead tasks assigned to teammates with due dates. Separate from customer-facing follow-ups.',
        whyItHelps: 'Track internal handoffs (legal review, finance approval) without polluting the customer thread.',
        roles: ['super_admin', 'selling_partner', 'sales_associate', 'vyapaar_ops'],
      },
      {
        title: 'Smart Notifications',
        icon: Bell,
        description: 'In-app notifications fire on @mentions, overdue follow-ups, deal-room messages, and approval responses. Bell icon in the topbar shows unread count.',
        whyItHelps: 'You hear about the things that matter — without inbox spam.',
        roles: ['super_admin', 'selling_partner', 'sales_associate', 'vyapaar_ops', 'customer'],
      },
    ],
  },
  {
    id: 'core',
    label: 'Core CRM',
    icon: Building2,
    color: 'from-slate-500 to-slate-700',
    items: [
      {
        title: 'Roles & Permissions',
        icon: ShieldCheck,
        description: 'Six roles: Super Admin, Selling Partner, Sales Associate, Customer, Vyapaar Ops, Vyapaar Finance. Each sees a tailored sidebar and only the data they own or are assigned to.',
        roles: ['super_admin'],
      },
      {
        title: 'Commercials Module',
        icon: FileText,
        description: 'Per-lead commercial workspace — one-time or recurring contracts, milestones, invoices, billing cycle, contract dates. Drives revenue dashboards.',
        roles: ['super_admin', 'selling_partner', 'vyapaar_ops', 'vyapaar_finance'],
      },
      {
        title: 'Companies & Partner Mappings',
        icon: Building2,
        description: 'Manage your customer/partner companies and define which partners can sell which categories. Lead assignment uses these mappings to suggest the right partner.',
        roles: ['super_admin', 'vyapaar_ops'],
      },
      {
        title: 'Commission Engine',
        icon: Settings,
        description: 'Configurable commission split between platform, selling partner, and sales associate. Per-lead override supported.',
        roles: ['super_admin', 'vyapaar_finance'],
      },
    ],
  },
];

const Help = () => {
  const { user } = useAuth();
  const [query, setQuery] = useState('');
  const role = user?.role;

  const isVisibleForRole = (item) => {
    if (!item.roles || item.roles.length === 0) return true;
    if (!role) return false;
    return item.roles.includes(role) || (user?.is_vyapaar_ops && item.roles.includes('vyapaar_ops'));
  };

  const matchesQuery = (item) => {
    if (!query.trim()) return true;
    const q = query.toLowerCase();
    return (
      item.title.toLowerCase().includes(q) ||
      (item.description || '').toLowerCase().includes(q) ||
      (item.whyItHelps || '').toLowerCase().includes(q) ||
      (item.howTo || '').toLowerCase().includes(q)
    );
  };

  return (
    <div className="space-y-6" data-testid="help-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2">
          <BookOpen className="w-7 h-7 text-violet-600" />
          Help & Feature Guide
        </h1>
        <p className="text-muted-foreground mt-1 max-w-2xl">
          Everything Meshora can do, organized by what you're trying to accomplish. Look for the
          <span className="inline-flex items-center gap-1 mx-1 px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-950/40 text-violet-700 dark:text-violet-300 text-xs font-medium">
            <Sparkles className="w-3 h-3" /> ?
          </span>
          icon throughout the app for in-context tips.
        </p>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search features (e.g. 'deal room', 'forecast')…"
          className="pl-9"
          data-testid="help-search-input"
        />
      </div>

      {/* Categories */}
      {CATEGORIES.map((cat) => {
        const visibleItems = cat.items.filter((i) => isVisibleForRole(i) && matchesQuery(i));
        if (visibleItems.length === 0) return null;
        const CatIcon = cat.icon;
        return (
          <section key={cat.id} className="space-y-3" data-testid={`help-section-${cat.id}`}>
            <div className="flex items-center gap-3">
              <span className={`p-2 rounded-md bg-gradient-to-br ${cat.color} text-white`}>
                <CatIcon className="w-5 h-5" />
              </span>
              <h2 className="text-lg font-semibold">{cat.label}</h2>
              <Badge variant="outline" className="text-[10px]">{visibleItems.length}</Badge>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {visibleItems.map((item) => {
                const Icon = item.icon;
                return (
                  <Card key={item.title} className="hover:shadow-md transition-shadow" data-testid={`help-item-${item.title.toLowerCase().replace(/\s+/g, '-')}`}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4 text-muted-foreground" />
                        <CardTitle className="text-base">{item.title}</CardTitle>
                        {item.shortcut && (
                          <kbd className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-muted border font-mono">{item.shortcut}</kbd>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
                      {item.howTo && (
                        <div className="text-xs leading-relaxed p-2 rounded-md bg-sky-50 dark:bg-sky-950/30 text-sky-800 dark:text-sky-200 border border-sky-200 dark:border-sky-900/50">
                          <span className="font-semibold">How to use:</span> {item.howTo}
                        </div>
                      )}
                      {item.examples && item.examples.length > 0 && (
                        <div className="space-y-1">
                          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Try these</p>
                          <ul className="space-y-0.5">
                            {item.examples.map((ex, i) => (
                              <li key={i} className="text-xs text-muted-foreground italic">• {ex}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {item.whyItHelps && (
                        <div className="text-xs leading-relaxed p-2 rounded-md bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-900/50">
                          ✨ <span className="font-semibold">Why it helps:</span> {item.whyItHelps}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </section>
        );
      })}

      {/* Footer */}
      <Card className="bg-gradient-to-br from-violet-50 to-indigo-50 dark:from-violet-950/40 dark:to-indigo-950/40 border-violet-200 dark:border-violet-900">
        <CardContent className="py-5 text-center">
          <div className="flex items-center justify-center gap-2 mb-1.5">
            <Mail className="w-4 h-4 text-violet-600" />
            <span className="text-sm font-medium">Need more help?</span>
          </div>
          <p className="text-xs text-muted-foreground">Press <kbd className="px-1.5 py-0.5 rounded bg-white dark:bg-slate-900 border font-mono text-[10px]">⌘K</kbd> to ask Meshora directly, or contact your Meshora admin.</p>
        </CardContent>
      </Card>
    </div>
  );
};

export default Help;
