import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Textarea } from '../../components/ui/textarea';
import { Calendar } from '../../components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '../../components/ui/popover';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import {
  CalendarIcon, Plus, Check, Clock, UserCheck,
} from 'lucide-react';
import { format } from 'date-fns';
import { formatDate } from '../../utils/api';

export const FollowUpsCard = ({
  followUps = [],
  showFollowUpForm,
  setShowFollowUpForm,
  newFollowUp,
  setNewFollowUp,
  onAdd,
  onComplete,
}) => (
  <Card data-testid="followups-section">
    <CardHeader>
      <div className="flex items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <CalendarIcon className="w-5 h-5 text-primary" />
          Follow-ups
        </CardTitle>
        <Button
          size="sm" variant="outline"
          onClick={() => setShowFollowUpForm(!showFollowUpForm)}
          data-testid="add-followup-btn"
        >
          <Plus className="w-4 h-4" />
        </Button>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      {showFollowUpForm && (
        <div className="p-4 border rounded-lg space-y-3 bg-muted/50 animate-scale-in">
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="w-full justify-start">
                <CalendarIcon className="w-4 h-4 mr-2" />
                {newFollowUp.date ? format(newFollowUp.date, 'PPP') : 'Pick a date'}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="single"
                selected={newFollowUp.date}
                onSelect={(date) => setNewFollowUp({ ...newFollowUp, date })}
                disabled={(date) => date < new Date()}
              />
            </PopoverContent>
          </Popover>
          <Select
            value={newFollowUp.pending_with}
            onValueChange={(v) => setNewFollowUp({ ...newFollowUp, pending_with: v })}
          >
            <SelectTrigger data-testid="pending-with-select">
              <SelectValue placeholder="Pending with (optional)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="customer">Customer</SelectItem>
              <SelectItem value="selling_partner">Selling Partner</SelectItem>
            </SelectContent>
          </Select>
          <Textarea
            placeholder="Notes (optional)"
            value={newFollowUp.notes}
            onChange={(e) => setNewFollowUp({ ...newFollowUp, notes: e.target.value })}
            rows={2}
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={onAdd} data-testid="save-followup-btn">Schedule</Button>
            <Button size="sm" variant="outline" onClick={() => setShowFollowUpForm(false)}>Cancel</Button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {followUps.length > 0 ? (
          followUps.map((f) => (
            <div
              key={f.id}
              className={`p-3 border rounded-lg ${f.is_completed ? 'bg-muted/50' : 'bg-white'}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {f.is_completed
                    ? <Check className="w-4 h-4 text-green-600" />
                    : <Clock className="w-4 h-4 text-orange-500" />}
                  <span className={`font-medium text-sm ${f.is_completed ? 'line-through text-muted-foreground' : ''}`}>
                    {formatDate(f.scheduled_date)}
                  </span>
                </div>
                {!f.is_completed && (
                  <Button
                    size="sm" variant="ghost"
                    onClick={() => onComplete(f.id)}
                    data-testid={`complete-followup-${f.id}`}
                  >
                    <Check className="w-4 h-4" />
                  </Button>
                )}
              </div>
              {f.pending_with && (
                <div className="flex items-center gap-1 text-xs text-blue-600 mt-1">
                  <UserCheck className="w-3 h-3" />
                  Pending with: {f.pending_with === 'customer' ? 'Customer' : 'Selling Partner'}
                </div>
              )}
              {f.notes && <p className="text-xs text-muted-foreground mt-1">{f.notes}</p>}
              {f.is_completed && f.completed_at && (
                <p className="text-xs text-green-600 mt-1">
                  Completed on {formatDate(f.completed_at)}
                </p>
              )}
            </div>
          ))
        ) : (
          <p className="text-center text-muted-foreground py-4 text-sm">
            No follow-ups scheduled
          </p>
        )}
      </div>
    </CardContent>
  </Card>
);

export default FollowUpsCard;
