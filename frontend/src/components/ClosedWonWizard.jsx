import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Briefcase, Repeat, CheckCircle2 } from 'lucide-react';
import api from '../utils/api';
import { toast } from 'sonner';

const ClosedWonWizard = ({ open, onOpenChange, lead, existingCommercial = null }) => {
  const navigate = useNavigate();
  const [type, setType] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleStart = async () => {
    if (existingCommercial) {
      navigate(`/commercials/${existingCommercial.id}`);
      onOpenChange(false);
      return;
    }
    if (!type) return;
    setSubmitting(true);
    try {
      const res = await api.post('/commercials', {
        lead_id: lead.id,
        type,
        currency: 'INR',
      });
      toast.success('Commercials initialized');
      onOpenChange(false);
      navigate(`/commercials/${res.data.id}`);
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Failed to create commercials';
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]" data-testid="closed-won-wizard">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-6 h-6 text-green-500" />
            <DialogTitle>Deal Closed Won — Set Up Commercials</DialogTitle>
          </div>
          <DialogDescription>
            {existingCommercial
              ? `Commercials already exist for "${lead?.title}". Open the workspace to continue setup.`
              : `Configure the post-sales commercial structure for "${lead?.title}". This step locks in milestones, billing schedules, and renewal terms.`}
          </DialogDescription>
        </DialogHeader>

        {!existingCommercial && (
          <div className="grid sm:grid-cols-2 gap-3 mt-2">
            <button
              type="button"
              onClick={() => setType('one_time')}
              className={`text-left p-4 rounded-lg border-2 transition-all ${
                type === 'one_time' ? 'border-primary bg-primary/5 ring-2 ring-primary/20' : 'border-border hover:border-primary/40'
              }`}
              data-testid="wizard-type-one-time"
            >
              <Briefcase className="w-5 h-5 text-primary mb-2" />
              <div className="font-semibold">One-Time Project</div>
              <div className="text-xs text-muted-foreground mt-1">
                Fixed-scope engagement billed via milestones. Suits SOW-based deliveries.
              </div>
            </button>
            <button
              type="button"
              onClick={() => setType('recurring')}
              className={`text-left p-4 rounded-lg border-2 transition-all ${
                type === 'recurring' ? 'border-primary bg-primary/5 ring-2 ring-primary/20' : 'border-border hover:border-primary/40'
              }`}
              data-testid="wizard-type-recurring"
            >
              <Repeat className="w-5 h-5 text-primary mb-2" />
              <div className="font-semibold">Recurring Contract</div>
              <div className="text-xs text-muted-foreground mt-1">
                Subscription / retainer with periodic billing & renewal management.
              </div>
            </button>
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} data-testid="wizard-cancel">
            {existingCommercial ? 'Close' : 'Not now'}
          </Button>
          <Button
            onClick={handleStart}
            disabled={!existingCommercial && (!type || submitting)}
            data-testid="wizard-continue"
          >
            {existingCommercial ? 'Open commercials' : (submitting ? 'Creating…' : 'Continue')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ClosedWonWizard;
