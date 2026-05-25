import { useState } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Checkbox } from './ui/checkbox';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from './ui/dialog';
import {
  Sparkles, Loader2, AlertTriangle, Lightbulb, ArrowRight, Users2, ListChecks, CheckCircle2,
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const SENTIMENT_STYLES = {
  positive: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300',
  neutral: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  negative: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
  mixed: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
};

const AIMeetingSummaryDialog = ({ open, onOpenChange, leadId, onSuccess }) => {
  const [rawNotes, setRawNotes] = useState('');
  const [meetingDate, setMeetingDate] = useState(new Date().toISOString().slice(0, 10));
  const [autoTasks, setAutoTasks] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const reset = () => { setRawNotes(''); setResult(null); };

  const handleClose = (open) => {
    if (!open) reset();
    onOpenChange(open);
  };

  const handleSubmit = async () => {
    if (!rawNotes.trim()) return toast.error('Please paste meeting notes');
    if (rawNotes.length < 20) return toast.error('Notes are too short. Add a bit more context.');
    setLoading(true);
    setResult(null);
    try {
      const res = await api.post(`/leads/${leadId}/ai/meeting-summary`, {
        raw_notes: rawNotes,
        meeting_date: meetingDate,
        auto_create_tasks: autoTasks,
      });
      setResult(res.data);
      toast.success(`Summary ready · ${res.data.created_task_ids?.length || 0} task(s) created`);
      onSuccess?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'AI summary failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="p-1.5 rounded-md bg-gradient-to-br from-violet-500 to-indigo-500 text-white">
              <Sparkles className="w-4 h-4" />
            </span>
            AI Meeting Summary
          </DialogTitle>
          <DialogDescription>
            Paste raw meeting notes, a call transcript, or voice transcript. Gemini will extract a summary,
            risks, opportunities, next steps, and action items. Action items can auto-become tasks.
          </DialogDescription>
        </DialogHeader>

        {!result && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Meeting date</Label>
              <Input
                type="date"
                value={meetingDate}
                onChange={(e) => setMeetingDate(e.target.value)}
                disabled={loading}
                data-testid="ai-meeting-date-input"
              />
            </div>
            <div className="space-y-2">
              <Label>Raw notes / transcript</Label>
              <Textarea
                value={rawNotes}
                onChange={(e) => setRawNotes(e.target.value)}
                placeholder="e.g. Met with Priya from Acme finance. They want to expand from 5-user pilot to 250 sales reps. CTO Ravi worried about Okta SSO timing. Sentiment was positive. Asked us to send proposal by Friday…"
                rows={10}
                disabled={loading}
                className="resize-none font-mono text-sm"
                data-testid="ai-meeting-notes-input"
              />
              <p className="text-xs text-muted-foreground">
                {rawNotes.length} / 25,000 characters
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="auto-tasks"
                checked={autoTasks}
                onCheckedChange={setAutoTasks}
                data-testid="ai-auto-tasks-checkbox"
              />
              <Label htmlFor="auto-tasks" className="cursor-pointer text-sm">
                Auto-create tasks from action items
              </Label>
            </div>
          </div>
        )}

        {result && <ResultView result={result.summary} createdTaskCount={result.created_task_ids?.length || 0} />}

        <DialogFooter>
          {!result ? (
            <>
              <Button variant="outline" onClick={() => handleClose(false)} disabled={loading}>Cancel</Button>
              <Button
                onClick={handleSubmit}
                disabled={loading || rawNotes.length < 20}
                data-testid="ai-meeting-submit-btn"
                className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700"
              >
                {loading ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Analyzing… (~10s)</>
                ) : (
                  <><Sparkles className="w-4 h-4 mr-2" />Generate Summary</>
                )}
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={reset} data-testid="ai-meeting-new-btn">Generate another</Button>
              <Button onClick={() => handleClose(false)} data-testid="ai-meeting-close-btn">Done</Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const ResultView = ({ result, createdTaskCount }) => (
  <div className="space-y-4" data-testid="ai-meeting-result">
    <div className="rounded-lg border bg-gradient-to-br from-violet-50 to-indigo-50 dark:from-violet-950/40 dark:to-indigo-950/40 p-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold flex items-center gap-1.5">
          <Sparkles className="w-4 h-4 text-violet-600 dark:text-violet-400" />
          Summary
        </h4>
        <Badge className={`text-[10px] ${SENTIMENT_STYLES[result.sentiment] || SENTIMENT_STYLES.neutral}`}>
          {result.sentiment}
        </Badge>
      </div>
      <p className="text-sm leading-relaxed">{result.summary}</p>
    </div>

    {result.risks?.length > 0 && (
      <Section icon={AlertTriangle} iconCls="text-rose-600 dark:text-rose-400" title="Risks" items={result.risks} testId="ai-risks" />
    )}
    {result.opportunities?.length > 0 && (
      <Section icon={Lightbulb} iconCls="text-amber-600 dark:text-amber-400" title="Opportunities" items={result.opportunities} testId="ai-opportunities" />
    )}
    {result.next_steps?.length > 0 && (
      <Section icon={ArrowRight} iconCls="text-sky-600 dark:text-sky-400" title="Next Steps" items={result.next_steps} testId="ai-next-steps" />
    )}

    {result.key_stakeholders?.length > 0 && (
      <div className="space-y-2">
        <h4 className="text-sm font-semibold flex items-center gap-1.5">
          <Users2 className="w-4 h-4 text-violet-600" />
          Key stakeholders
        </h4>
        <div className="flex flex-wrap gap-1.5">
          {result.key_stakeholders.map((s, i) => (
            <Badge key={i} variant="outline" className="text-xs" data-testid={`ai-stakeholder-${i}`}>
              {s.name}{s.role_hint ? ` · ${s.role_hint}` : ''}
            </Badge>
          ))}
        </div>
      </div>
    )}

    {result.action_items?.length > 0 && (
      <div className="space-y-2">
        <h4 className="text-sm font-semibold flex items-center gap-1.5">
          <ListChecks className="w-4 h-4 text-emerald-600" />
          Action items
          {createdTaskCount > 0 && (
            <Badge className="ml-auto text-[10px] bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
              <CheckCircle2 className="w-3 h-3 mr-1" />
              {createdTaskCount} task(s) created
            </Badge>
          )}
        </h4>
        <ul className="space-y-1.5">
          {result.action_items.map((a, i) => (
            <li key={i} className="text-sm flex items-start gap-2 p-2 rounded-md bg-muted/40">
              <span className="font-semibold text-emerald-600 dark:text-emerald-400">{i + 1}.</span>
              <div className="flex-1">
                <div className="font-medium">{a.title}</div>
                <div className="text-xs text-muted-foreground flex gap-2 mt-0.5">
                  {a.owner_hint && <span>👤 {a.owner_hint}</span>}
                  {a.priority && <span>· {a.priority}</span>}
                  {a.due_in_days != null && <span>· due in {a.due_in_days}d</span>}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    )}
  </div>
);

const Section = ({ icon: Icon, iconCls, title, items, testId }) => (
  <div className="space-y-1.5">
    <h4 className="text-sm font-semibold flex items-center gap-1.5">
      <Icon className={`w-4 h-4 ${iconCls}`} />
      {title}
    </h4>
    <ul className="space-y-1 text-sm">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 pl-1" data-testid={`${testId}-${i}`}>
          <span className="text-muted-foreground">•</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  </div>
);

export default AIMeetingSummaryDialog;
