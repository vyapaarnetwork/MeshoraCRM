import { useMemo } from 'react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './ui/sheet';
import { Button } from './ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';
import { ScrollArea } from './ui/scroll-area';
import { Badge } from './ui/badge';
import {
  Check, ExternalLink, FileText, UserPlus, RefreshCw, Trophy, XCircle, Ban,
  Snowflake, Briefcase, CheckCircle2, AtSign, CalendarClock, AlertCircle,
  DollarSign, FileSignature, Newspaper, ListChecks, Clock, Bell,
} from 'lucide-react';

const TYPE_ICON = {
  new_lead: FileText,
  lead_assigned: UserPlus,
  lead_status_changed: RefreshCw,
  lead_won: Trophy,
  lead_lost: XCircle,
  lead_disqualified: Ban,
  lead_dead: Snowflake,
  deal_room_invite: Briefcase,
  approval_requested: CheckCircle2,
  comment_mention: AtSign,
  milestone_due: CalendarClock,
  invoice_overdue: AlertCircle,
  payment_received: DollarSign,
  commercial_created: FileSignature,
  weekly_war_room_digest: Newspaper,
  monthly_won_digest: Newspaper,
  follow_up_reminder: Clock,
  follow_up_overdue: AlertCircle,
  task_assigned: ListChecks,
};

const TYPE_COLOR = {
  new_lead: 'text-blue-700 bg-blue-100 dark:bg-blue-950/40 dark:text-blue-300',
  lead_assigned: 'text-green-700 bg-green-100 dark:bg-green-950/40 dark:text-green-300',
  lead_status_changed: 'text-purple-700 bg-purple-100 dark:bg-purple-950/40 dark:text-purple-300',
  lead_won: 'text-emerald-700 bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-300',
  lead_lost: 'text-rose-700 bg-rose-100 dark:bg-rose-950/40 dark:text-rose-300',
  lead_disqualified: 'text-slate-700 bg-slate-100 dark:bg-slate-800 dark:text-slate-300',
  lead_dead: 'text-sky-700 bg-sky-100 dark:bg-sky-950/40 dark:text-sky-300',
  deal_room_invite: 'text-indigo-700 bg-indigo-100 dark:bg-indigo-950/40 dark:text-indigo-300',
  approval_requested: 'text-blue-700 bg-blue-100 dark:bg-blue-950/40 dark:text-blue-300',
  comment_mention: 'text-violet-700 bg-violet-100 dark:bg-violet-950/40 dark:text-violet-300',
  milestone_due: 'text-violet-700 bg-violet-100 dark:bg-violet-950/40 dark:text-violet-300',
  invoice_overdue: 'text-rose-700 bg-rose-100 dark:bg-rose-950/40 dark:text-rose-300',
  payment_received: 'text-emerald-700 bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-300',
  commercial_created: 'text-teal-700 bg-teal-100 dark:bg-teal-950/40 dark:text-teal-300',
  weekly_war_room_digest: 'text-orange-700 bg-orange-100 dark:bg-orange-950/40 dark:text-orange-300',
  monthly_won_digest: 'text-amber-700 bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300',
  follow_up_reminder: 'text-amber-700 bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300',
  follow_up_overdue: 'text-rose-700 bg-rose-100 dark:bg-rose-950/40 dark:text-rose-300',
  task_assigned: 'text-indigo-700 bg-indigo-100 dark:bg-indigo-950/40 dark:text-indigo-300',
};

// Category mapping per user-approved spec
const CATEGORIES = [
  { id: 'all',         label: 'All',         types: null },
  { id: 'leads',       label: 'Leads',       types: ['new_lead', 'lead_assigned', 'lead_status_changed'] },
  { id: 'deals',       label: 'Deals',       types: ['lead_won', 'lead_lost', 'lead_dead', 'lead_disqualified', 'deal_room_invite'] },
  { id: 'approvals',   label: 'Approvals',   types: ['approval_requested'] },
  { id: 'mentions',    label: 'Mentions',    types: ['comment_mention'] },
  { id: 'milestones',  label: 'Milestones',  types: ['milestone_due', 'invoice_overdue', 'payment_received', 'commercial_created'] },
  { id: 'digests',     label: 'Digests',     types: ['weekly_war_room_digest', 'monthly_won_digest'] },
];

const formatTimeAgo = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
};

const NotificationsPanel = ({ open, onOpenChange, notifications, unreadCount, onNotificationClick, onMarkAllRead }) => {
  // Group by category for counts
  const counts = useMemo(() => {
    const c = { all: 0 };
    CATEGORIES.forEach(cat => { if (cat.id !== 'all') c[cat.id] = 0; });
    notifications.forEach((n) => {
      if (!n.is_read) c.all += 1;
      const cat = CATEGORIES.find(x => x.types && x.types.includes(n.type));
      if (cat && !n.is_read) c[cat.id] = (c[cat.id] || 0) + 1;
    });
    return c;
  }, [notifications]);

  const filterByCategory = (catId) => {
    const cat = CATEGORIES.find(c => c.id === catId);
    if (!cat || !cat.types) return notifications;
    return notifications.filter(n => cat.types.includes(n.type));
  };

  const renderCard = (n) => {
    const Icon = TYPE_ICON[n.type] || Bell;
    const colorCls = TYPE_COLOR[n.type] || 'text-slate-700 bg-slate-100';
    return (
      <button
        key={n.id}
        type="button"
        onClick={() => onNotificationClick(n)}
        data-testid={`notif-card-${n.id}`}
        className={`group relative flex items-start gap-3 p-4 rounded-xl border text-left transition-all hover:shadow-sm hover:border-violet-300 dark:hover:border-violet-700 ${
          n.is_read ? 'bg-card border-border' : 'bg-violet-50 dark:bg-violet-950/30 border-violet-200 dark:border-violet-900'
        }`}
      >
        <div className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${colorCls}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className={`text-sm truncate ${!n.is_read ? 'font-semibold' : 'font-medium'}`}>{n.title}</p>
            {!n.is_read && <span className="shrink-0 w-2 h-2 rounded-full bg-violet-500" />}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.message}</p>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70 mt-1.5">
            {formatTimeAgo(n.created_at)}
          </p>
        </div>
        {(n.lead_id || n.commercial_id) && (
          <ExternalLink className="w-3.5 h-3.5 text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
        )}
      </button>
    );
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[560px] md:max-w-[640px] lg:max-w-[720px] p-0 flex flex-col"
        data-testid="notifications-sheet"
      >
        <SheetHeader className="px-5 py-4 border-b">
          <div className="flex items-center justify-between">
            <SheetTitle className="flex items-center gap-2">
              <Bell className="w-5 h-5 text-violet-600" />
              Notifications
              {unreadCount > 0 && (
                <Badge variant="secondary" className="ml-2 bg-violet-100 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300">
                  {unreadCount} unread
                </Badge>
              )}
            </SheetTitle>
            {unreadCount > 0 && (
              <Button variant="ghost" size="sm" onClick={onMarkAllRead} data-testid="mark-all-read-btn" className="text-xs">
                <Check className="w-3 h-3 mr-1" /> Mark all read
              </Button>
            )}
          </div>
        </SheetHeader>

        <Tabs defaultValue="all" className="flex-1 flex flex-col overflow-hidden">
          <div className="px-5 pt-3 border-b">
            <TabsList className="bg-transparent gap-1 h-auto flex-wrap p-0 justify-start">
              {CATEGORIES.map((cat) => (
                <TabsTrigger
                  key={cat.id}
                  value={cat.id}
                  data-testid={`notif-tab-${cat.id}`}
                  className="data-[state=active]:bg-violet-100 data-[state=active]:text-violet-700 dark:data-[state=active]:bg-violet-950/40 dark:data-[state=active]:text-violet-300 px-3 py-1.5 rounded-md text-xs"
                >
                  {cat.label}
                  {counts[cat.id] > 0 && (
                    <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] text-[10px] font-bold rounded-full bg-rose-500 text-white px-1">
                      {counts[cat.id] > 9 ? '9+' : counts[cat.id]}
                    </span>
                  )}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>

          {CATEGORIES.map((cat) => {
            const items = filterByCategory(cat.id);
            return (
              <TabsContent
                key={cat.id}
                value={cat.id}
                className="flex-1 overflow-hidden m-0 p-0 data-[state=active]:flex data-[state=active]:flex-col"
              >
                <ScrollArea className="flex-1 px-5 py-4">
                  {items.length === 0 ? (
                    <div className="py-12 text-center text-sm text-muted-foreground">
                      <Bell className="w-10 h-10 mx-auto opacity-30 mb-2" />
                      No notifications in this category yet.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {items.map(renderCard)}
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>
            );
          })}
        </Tabs>
      </SheetContent>
    </Sheet>
  );
};

export default NotificationsPanel;
