import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/tabs';
import {
  Sparkles, Brain, ShieldAlert, Lightbulb, Loader2, AlertOctagon, MessageCircle,
  Phone, Mail, Calendar, Hash, Copy, CheckCircle2, RefreshCw, TrendingDown, Users2,
} from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const RISK_STYLES = {
  low: { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-900', bar: 'from-emerald-500 to-teal-500', label: 'Low Risk' },
  medium: { cls: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-900', bar: 'from-amber-500 to-orange-500', label: 'Medium Risk' },
  high: { cls: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-900', bar: 'from-rose-500 to-pink-500', label: 'High Risk' },
  critical: { cls: 'bg-red-50 text-red-700 border-red-300 dark:bg-red-950/50 dark:text-red-300 dark:border-red-900', bar: 'from-red-600 to-rose-600', label: 'Critical' },
};
const SEVERITY_CLS = {
  low: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  medium: 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300',
  high: 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300',
};
const CHANNEL_ICON = { email: Mail, call: Phone, whatsapp: MessageCircle, meeting: Calendar, slack: Hash };

const AIInsightsCard = ({ leadId, initialRisk }) => {
  const [activeTab, setActiveTab] = useState('risk');
  const [risk, setRisk] = useState(initialRisk || null);
  const [suggestion, setSuggestion] = useState(null);
  const [loadingRisk, setLoadingRisk] = useState(false);
  const [loadingSugg, setLoadingSugg] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => { setRisk(initialRisk || null); }, [initialRisk]);

  const runRisk = async () => {
    setLoadingRisk(true);
    try {
      const r = await api.post(`/leads/${leadId}/ai/risk-analysis`);
      setRisk(r.data);
      toast.success(`AI risk: ${r.data.risk_level} (${r.data.risk_score}/100)`);
    } catch (e) { toast.error(e.response?.data?.detail || 'Risk analysis failed'); }
    finally { setLoadingRisk(false); }
  };
  const runSugg = async () => {
    setLoadingSugg(true);
    try {
      const r = await api.post(`/leads/${leadId}/ai/follow-up-suggestion`);
      setSuggestion(r.data);
      toast.success('Follow-up suggestion ready');
    } catch (e) { toast.error(e.response?.data?.detail || 'Suggestion failed'); }
    finally { setLoadingSugg(false); }
  };

  const copyStarter = () => {
    if (!suggestion?.conversation_starter) return;
    navigator.clipboard.writeText(suggestion.conversation_starter);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
    toast.success('Copied to clipboard');
  };

  return (
    <Card data-testid="ai-insights-card" className="border-violet-200 dark:border-violet-900">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <span className="p-1.5 rounded-md bg-gradient-to-br from-violet-500 to-indigo-500 text-white">
                <Brain className="w-4 h-4" />
              </span>
              AI Insights
            </CardTitle>
            <CardDescription>Deal risk analysis and tailored follow-up recommendations</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-2 mb-4">
            <TabsTrigger value="risk" data-testid="ai-tab-risk">
              <ShieldAlert className="w-3.5 h-3.5 mr-1.5" />Risk
            </TabsTrigger>
            <TabsTrigger value="suggestion" data-testid="ai-tab-suggestion">
              <Lightbulb className="w-3.5 h-3.5 mr-1.5" />Next Move
            </TabsTrigger>
          </TabsList>

          {/* RISK TAB */}
          <TabsContent value="risk">
            {!risk && (
              <EmptyAI
                title="AI Deal Risk Analysis"
                description="Analyzes inactivity, stakeholder gaps, meeting sentiment, deal value tier, and follow-up health."
                onRun={runRisk}
                loading={loadingRisk}
                testId="ai-run-risk-btn"
              />
            )}
            {risk && <RiskView risk={risk} onRefresh={runRisk} refreshing={loadingRisk} />}
          </TabsContent>

          {/* SUGGESTION TAB */}
          <TabsContent value="suggestion">
            {!suggestion && (
              <EmptyAI
                title="AI Follow-up Assistant"
                description="Suggests the optimal next action, timing, channel, and a ready-to-send conversation starter."
                onRun={runSugg}
                loading={loadingSugg}
                testId="ai-run-suggestion-btn"
              />
            )}
            {suggestion && (
              <SuggestionView
                s={suggestion}
                onRefresh={runSugg}
                refreshing={loadingSugg}
                onCopy={copyStarter}
                copied={copied}
              />
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};

const EmptyAI = ({ title, description, onRun, loading, testId }) => (
  <div className="text-center py-6 px-4">
    <div className="w-12 h-12 mx-auto mb-3 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-500 text-white flex items-center justify-center">
      <Sparkles className="w-6 h-6" />
    </div>
    <h4 className="font-semibold mb-1">{title}</h4>
    <p className="text-xs text-muted-foreground max-w-sm mx-auto mb-4">{description}</p>
    <Button
      onClick={onRun}
      disabled={loading}
      data-testid={testId}
      className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700"
    >
      {loading ? (
        <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Analyzing… (~10s)</>
      ) : (
        <><Sparkles className="w-4 h-4 mr-2" />Run AI Analysis</>
      )}
    </Button>
  </div>
);

const RiskView = ({ risk, onRefresh, refreshing }) => {
  const rs = RISK_STYLES[risk.risk_level] || RISK_STYLES.medium;
  return (
    <div className="space-y-4" data-testid="ai-risk-result">
      <div className={`rounded-lg border p-3 ${rs.cls}`}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <AlertOctagon className="w-4 h-4" />
            <span className="font-semibold text-sm">{rs.label} · {risk.risk_score}/100</span>
          </div>
          <span className="text-xs opacity-80">Confidence {risk.confidence}%</span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden bg-white/40 dark:bg-black/30">
          <div className={`h-full bg-gradient-to-r ${rs.bar}`} style={{ width: `${risk.risk_score}%` }} />
        </div>
        <div className="flex items-center justify-between mt-2 text-xs">
          <span className="flex items-center gap-1"><TrendingDown className="w-3 h-3" />Closure probability: <strong>{risk.closure_probability}%</strong></span>
        </div>
      </div>

      {risk.top_risk_factors?.length > 0 && (
        <RiskSection title="Top risk factors" icon={ShieldAlert} iconCls="text-rose-600">
          <ul className="space-y-1.5">
            {risk.top_risk_factors.map((f, i) => (
              <li key={i} className="text-sm flex items-start gap-2" data-testid={`risk-factor-${i}`}>
                <Badge className={`text-[10px] mt-0.5 ${SEVERITY_CLS[f.severity] || SEVERITY_CLS.medium}`}>{f.severity}</Badge>
                <div className="flex-1">
                  <div className="font-medium">{f.factor}</div>
                  {f.evidence && <div className="text-xs text-muted-foreground">{f.evidence}</div>}
                </div>
              </li>
            ))}
          </ul>
        </RiskSection>
      )}

      {risk.stakeholder_gaps?.length > 0 && (
        <RiskSection title="Stakeholder gaps" icon={Users2} iconCls="text-amber-600">
          <ul className="space-y-0.5 text-sm">
            {risk.stakeholder_gaps.map((g, i) => <li key={i}>· {g}</li>)}
          </ul>
        </RiskSection>
      )}

      {risk.recommended_mitigations?.length > 0 && (
        <RiskSection title="Recommended mitigations" icon={Lightbulb} iconCls="text-sky-600">
          <ul className="space-y-1 text-sm">
            {risk.recommended_mitigations.map((m, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-sky-600 font-bold mt-0.5">{i + 1}.</span>
                <span>{m}</span>
              </li>
            ))}
          </ul>
        </RiskSection>
      )}

      <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-3">
        <span>Last analyzed by {risk.generated_by} · {new Date(risk.generated_at).toLocaleString()}</span>
        <Button size="sm" variant="ghost" onClick={onRefresh} disabled={refreshing} className="h-7" data-testid="ai-refresh-risk-btn">
          {refreshing ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <RefreshCw className="w-3 h-3 mr-1" />}
          Re-analyze
        </Button>
      </div>
    </div>
  );
};

const SuggestionView = ({ s, onRefresh, refreshing, onCopy, copied }) => {
  const Icon = CHANNEL_ICON[s.channel] || Mail;
  return (
    <div className="space-y-4" data-testid="ai-suggestion-result">
      <div className="rounded-lg border bg-gradient-to-br from-violet-50 to-indigo-50 dark:from-violet-950/40 dark:to-indigo-950/40 p-3 space-y-2">
        <div className="flex items-start gap-2">
          <Icon className="w-4 h-4 mt-0.5 text-violet-600" />
          <div className="flex-1">
            <div className="font-semibold text-sm">{s.recommended_action}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{s.rationale}</div>
            <div className="flex flex-wrap gap-2 mt-2 text-xs">
              <Badge className="bg-violet-100 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300">
                via {s.channel}
              </Badge>
              <Badge variant="outline">
                {s.suggested_timing?.when || 'soon'}
                {s.suggested_timing?.reason ? ` · ${s.suggested_timing.reason}` : ''}
              </Badge>
              <Badge variant="outline">Confidence {s.confidence}%</Badge>
            </div>
          </div>
        </div>
      </div>

      {s.conversation_starter && (
        <RiskSection title="Conversation starter" icon={MessageCircle} iconCls="text-emerald-600"
          right={
            <Button size="sm" variant="ghost" onClick={onCopy} className="h-7" data-testid="ai-copy-starter-btn">
              {copied ? <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
              {copied ? 'Copied' : 'Copy'}
            </Button>
          }>
          <div className="text-sm whitespace-pre-wrap bg-muted/40 rounded-md p-3 border" data-testid="ai-conversation-starter">
            {s.conversation_starter}
          </div>
        </RiskSection>
      )}

      {s.proposal_recommendation && (
        <RiskSection title="Proposal recommendation" icon={Lightbulb} iconCls="text-amber-600">
          <p className="text-sm">{s.proposal_recommendation}</p>
        </RiskSection>
      )}

      {s.questions_to_ask?.length > 0 && (
        <RiskSection title="Questions to ask" icon={MessageCircle} iconCls="text-sky-600">
          <ul className="space-y-1 text-sm">
            {s.questions_to_ask.map((q, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-sky-600 font-bold mt-0.5">?</span>
                <span>{q}</span>
              </li>
            ))}
          </ul>
        </RiskSection>
      )}

      {s.stakeholders_to_loop_in?.length > 0 && (
        <RiskSection title="Loop in" icon={Users2} iconCls="text-violet-600">
          <div className="flex flex-wrap gap-1.5">
            {s.stakeholders_to_loop_in.map((p, i) => (
              <Badge key={i} variant="outline" className="text-xs">{p}</Badge>
            ))}
          </div>
        </RiskSection>
      )}

      <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-3">
        <span>by {s.generated_by} · {new Date(s.generated_at).toLocaleString()}</span>
        <Button size="sm" variant="ghost" onClick={onRefresh} disabled={refreshing} className="h-7" data-testid="ai-refresh-suggestion-btn">
          {refreshing ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <RefreshCw className="w-3 h-3 mr-1" />}
          Regenerate
        </Button>
      </div>
    </div>
  );
};

const RiskSection = ({ icon: Icon, iconCls, title, children, right }) => (
  <div className="space-y-1.5">
    <div className="flex items-center justify-between">
      <h4 className="text-sm font-semibold flex items-center gap-1.5">
        <Icon className={`w-4 h-4 ${iconCls}`} />
        {title}
      </h4>
      {right}
    </div>
    {children}
  </div>
);

export default AIInsightsCard;
