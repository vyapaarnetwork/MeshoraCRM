import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, DialogContent } from './ui/dialog';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import {
  Sparkles, Loader2, Search, Command, ArrowRight, Lightbulb, AlertTriangle,
  Flame, Sun, Snowflake,
} from 'lucide-react';
import api, { formatCurrency } from '../utils/api';
import { toast } from 'sonner';

const BAND_BADGE = {
  hot: { icon: Flame, cls: 'bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-300' },
  warm: { icon: Sun, cls: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300' },
  cold: { icon: Snowflake, cls: 'bg-sky-100 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300' },
  at_risk: { icon: AlertTriangle, cls: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300' },
};

const SAMPLE_QUERIES = [
  'Show me at-risk leads',
  'Hot leads worth more than 1 lakh',
  'Inactive leads over 10 days',
  'Won deals this month',
  'Leads in proposal stage',
];

const CommandBar = ({ open, onOpenChange }) => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery('');
      setResponse(null);
    }
  }, [open]);

  const run = useCallback(async (q) => {
    if (!q.trim()) return;
    setLoading(true);
    setResponse(null);
    try {
      const r = await api.post('/ai/command', { query: q });
      setResponse(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'AI query failed');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleKey = (e) => {
    if (e.key === 'Enter' && query.trim()) run(query);
  };

  const openLead = (id) => {
    onOpenChange(false);
    navigate(`/leads/${id}`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl p-0 gap-0 overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 border-b">
          <span className="p-1.5 rounded-md bg-gradient-to-br from-violet-500 to-indigo-500 text-white">
            <Sparkles className="w-4 h-4" />
          </span>
          <Input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask Meshora anything… e.g. 'show me at-risk leads worth more than 1 lakh'"
            className="flex-1 border-0 shadow-none focus-visible:ring-0 text-base"
            disabled={loading}
            data-testid="command-bar-input"
          />
          {loading && <Loader2 className="w-4 h-4 animate-spin text-violet-600" />}
          <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded border bg-muted text-[10px] uppercase tracking-wider text-muted-foreground">
            <Command className="w-3 h-3" /> K
          </kbd>
        </div>

        <div className="max-h-[60vh] overflow-y-auto p-3" data-testid="command-bar-results">
          {!response && !loading && (
            <div className="space-y-3">
              <div className="text-xs text-muted-foreground px-1">Try these:</div>
              <div className="space-y-1">
                {SAMPLE_QUERIES.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => { setQuery(s); run(s); }}
                    className="w-full text-left px-3 py-2 rounded-md hover:bg-accent text-sm flex items-center gap-2 group"
                    data-testid={`sample-query-${s.slice(0, 10).replace(/\s/g, '-')}`}
                  >
                    <Search className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="flex-1">{s}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {response && (
            <div className="space-y-3">
              {response.summary && (
                <div className="px-2 py-2 rounded-md bg-violet-50 dark:bg-violet-950/40 text-sm text-violet-900 dark:text-violet-200">
                  <span className="font-semibold">AI:</span> {response.summary}
                </div>
              )}

              {response.results.length === 0 ? (
                <div className="text-center py-8 text-sm text-muted-foreground">
                  No leads match this query.
                </div>
              ) : (
                <div className="space-y-1">
                  <div className="text-xs text-muted-foreground px-1">{response.count} result(s)</div>
                  {response.results.map((r) => {
                    const bm = BAND_BADGE[r.health?.band] || BAND_BADGE.cold;
                    const Icon = bm.icon;
                    return (
                      <button
                        key={r.id}
                        type="button"
                        onClick={() => openLead(r.id)}
                        className="w-full text-left p-2 rounded-md hover:bg-accent flex items-center gap-3"
                        data-testid={`result-row-${r.id}`}
                      >
                        <div className={`shrink-0 p-1.5 rounded ${bm.cls}`}>
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm truncate">{r.title}</span>
                            <Badge className="text-[10px]" style={{ backgroundColor: `${r.status_color}20`, color: r.status_color }}>
                              {r.status_name}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground truncate">
                            {r.customer_name} @ {r.customer_company || '—'}
                            {r.primary_category_name ? ` · ${r.primary_category_name}` : ''}
                            {r.selling_partner_name ? ` · partner ${r.selling_partner_name}` : ''}
                          </div>
                        </div>
                        <div className="text-xs font-semibold tabular-nums shrink-0">{formatCurrency(r.deal_value)}</div>
                      </button>
                    );
                  })}
                </div>
              )}

              {response.suggested_followups?.length > 0 && (
                <div className="border-t pt-3 px-1">
                  <div className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                    <Lightbulb className="w-3 h-3" /> Try next:
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {response.suggested_followups.map((f, i) => (
                      <Button
                        key={i}
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs"
                        onClick={() => { setQuery(f); run(f); }}
                        data-testid={`followup-${i}`}
                      >
                        {f}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="px-4 py-2 border-t bg-muted/30 text-[11px] text-muted-foreground flex items-center justify-between">
          <span>Powered by Gemini · queries are role-scoped</span>
          <kbd className="px-1.5 py-0.5 rounded bg-muted">ESC</kbd>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default CommandBar;
