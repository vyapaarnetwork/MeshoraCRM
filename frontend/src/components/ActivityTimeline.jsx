import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Avatar, AvatarFallback } from './ui/avatar';
import { Badge } from './ui/badge';
import {
  History, Sparkles, MessageSquare, Calendar, CheckCircle, UserPlus, Trophy,
  UserMinus, Briefcase, Search, Filter,
} from 'lucide-react';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from './ui/select';
import { formatDateTime } from '../utils/api';

const ICON_MAP = {
  Sparkles, MessageSquare, Calendar, CheckCircle, UserPlus, Trophy, UserMinus, Briefcase,
};

const TYPE_LABELS = {
  lead_created: { label: 'Created', color: 'bg-violet-100 text-violet-700 dark:bg-violet-950/60 dark:text-violet-300' },
  comment: { label: 'Comment', color: 'bg-sky-100 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300' },
  followup_scheduled: { label: 'Follow-up', color: 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300' },
  followup_completed: { label: 'Completed', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300' },
  partner_assigned: { label: 'Partner', color: 'bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300' },
  partner_won: { label: 'Won', color: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300' },
  partner_lost: { label: 'Lost', color: 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300' },
};

const ActivityTimeline = ({ activities = [] }) => {
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('all');

  const filtered = useMemo(() => {
    return activities.filter((a) => {
      if (filterType !== 'all') {
        if (filterType === 'commercial' && !a.type.startsWith('commercial_')) return false;
        if (filterType !== 'commercial' && a.type !== filterType) return false;
      }
      if (search) {
        const q = search.toLowerCase();
        return (
          (a.title || '').toLowerCase().includes(q) ||
          (a.description || '').toLowerCase().includes(q) ||
          (a.user_name || '').toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [activities, search, filterType]);

  return (
    <Card data-testid="activity-timeline-card">
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="flex items-center gap-2">
            <History className="w-5 h-5 text-primary" />
            Activity Timeline ({activities.length})
          </CardTitle>
          <div className="flex gap-2 w-full sm:w-auto">
            <div className="relative flex-1 sm:w-48">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <Input
                placeholder="Search…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8 pl-8 text-sm"
                data-testid="activity-search"
              />
            </div>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="h-8 w-36 text-sm" data-testid="activity-filter">
                <Filter className="w-3.5 h-3.5 mr-1" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All events</SelectItem>
                <SelectItem value="comment">Comments</SelectItem>
                <SelectItem value="followup_scheduled">Follow-ups</SelectItem>
                <SelectItem value="followup_completed">Completed</SelectItem>
                <SelectItem value="partner_assigned">Partner changes</SelectItem>
                <SelectItem value="commercial">Commercials</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground text-sm">
            <History className="w-10 h-10 mx-auto opacity-30 mb-2" />
            No activity matches the current filter.
          </div>
        ) : (
          <ol className="relative border-l border-slate-200 dark:border-slate-800 ml-3 space-y-4">
            {filtered.map((a) => {
              const Icon = ICON_MAP[a.icon] || Sparkles;
              const typeKey = a.type?.startsWith('commercial_') ? 'commercial' : a.type;
              const typeMeta = TYPE_LABELS[a.type] || TYPE_LABELS[typeKey] || {
                label: (a.type || 'event').replace(/_/g, ' '),
                color: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
              };
              return (
                <li key={a.id} className="ml-4 relative">
                  <span className="absolute -left-[26px] top-1 flex items-center justify-center w-5 h-5 rounded-full bg-background border border-slate-200 dark:border-slate-700">
                    <Icon className="w-3 h-3 text-slate-500 dark:text-slate-400" />
                  </span>
                  <div className="flex items-start gap-3">
                    {a.user_name && (
                      <Avatar className="h-7 w-7 mt-0.5">
                        <AvatarFallback className="text-[10px] bg-primary text-white">
                          {a.user_name.charAt(0)}
                        </AvatarFallback>
                      </Avatar>
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-0.5">
                        <Badge className={`text-[10px] uppercase tracking-wider ${typeMeta.color}`}>
                          {typeMeta.label}
                        </Badge>
                        <span className="text-sm font-medium">{a.title}</span>
                        <span className="text-xs text-muted-foreground">
                          {formatDateTime(a.timestamp)}
                        </span>
                      </div>
                      {a.description && (
                        <p className="text-sm text-muted-foreground break-words">{a.description}</p>
                      )}
                      {a.user_name && (
                        <p className="text-xs text-muted-foreground mt-0.5">by {a.user_name}</p>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  );
};

export default ActivityTimeline;
