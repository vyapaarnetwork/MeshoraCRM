import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import {
  Users, Plus, Trophy, UserCheck, UserMinus,
} from 'lucide-react';
import { formatDate } from '../../utils/api';
import SearchableUserSelect from '../../components/SearchableUserSelect';

const StatusIcon = ({ status }) => {
  if (status === 'won') return <Trophy className="w-4 h-4 text-green-600" />;
  if (status === 'lost') return <UserMinus className="w-4 h-4 text-red-600" />;
  return <UserCheck className="w-4 h-4 text-blue-600" />;
};

export const AssignedPartnersCard = ({ lead, onAssignClick, onMarkWon, onRemove }) => (
  <Card data-testid="assigned-partners-section">
    <CardHeader>
      <div className="flex items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Users className="w-5 h-5 text-primary" />
          Assigned Partners ({lead.active_partners_count || 0} active)
        </CardTitle>
        <Button size="sm" onClick={onAssignClick} data-testid="assign-partner-btn">
          <Plus className="w-4 h-4 mr-1" />
          Assign Partner
        </Button>
      </div>
    </CardHeader>
    <CardContent>
      {lead.assigned_partners && lead.assigned_partners.length > 0 ? (
        <div className="space-y-3">
          {lead.assigned_partners.map((a) => (
            <div
              key={`${a.partner_id}-${a.assigned_at || ''}`}
              className="flex items-start gap-3 p-3 bg-muted rounded-lg"
            >
              <div className={`p-2 rounded-full ${
                a.status === 'won' ? 'bg-green-100' :
                a.status === 'lost' ? 'bg-red-100' : 'bg-blue-100'
              }`}>
                <StatusIcon status={a.status} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{a.partner_name || 'Unknown Partner'}</span>
                  <Badge
                    variant={a.status === 'won' ? 'default' : a.status === 'lost' ? 'secondary' : 'outline'}
                    className={`text-xs ${
                      a.status === 'won' ? 'bg-green-100 text-green-700' :
                      a.status === 'lost' ? 'bg-red-100 text-red-700' :
                      'bg-blue-100 text-blue-700'
                    }`}
                  >
                    {a.status === 'won' ? 'Winner' : a.status === 'lost' ? 'Lost' : 'Active'}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  Assigned by {a.assigned_by_name} on {formatDate(a.assigned_at)}
                </p>
                {a.won_at && (
                  <p className="text-sm text-green-600 mt-1">Won on {formatDate(a.won_at)}</p>
                )}
                {a.lost_at && (
                  <p className="text-sm text-red-600 mt-1">Lost on {formatDate(a.lost_at)}</p>
                )}
                {a.notes && (
                  <p className="text-xs text-muted-foreground mt-1 italic">{a.notes}</p>
                )}
                {a.status === 'active' && (
                  <div className="flex gap-2 mt-2">
                    <Button
                      size="sm" variant="outline"
                      className="text-green-600 hover:text-green-700"
                      onClick={() => onMarkWon(a.partner_id)}
                    >
                      <Trophy className="w-3 h-3 mr-1" />
                      Mark Won
                    </Button>
                    <Button
                      size="sm" variant="outline"
                      className="text-red-600 hover:text-red-700"
                      onClick={() => onRemove(a.partner_id)}
                    >
                      <UserMinus className="w-3 h-3 mr-1" />
                      Remove
                    </Button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-6">
          <Users className="w-10 h-10 mx-auto text-muted-foreground/50 mb-2" />
          <p className="text-muted-foreground text-sm">No partners assigned yet</p>
          <Button size="sm" variant="outline" className="mt-2" onClick={onAssignClick}>
            Assign First Partner
          </Button>
        </div>
      )}
    </CardContent>
  </Card>
);

export const AssignPartnerDialog = ({
  open, onOpenChange, partners, selectedPartnerId, setSelectedPartnerId, lead, onConfirm,
}) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Users className="w-5 h-5" />
          Assign Partner to Lead
        </DialogTitle>
        <DialogDescription>
          Select a selling partner to assign to this lead. Multiple partners can work on the same lead concurrently.
        </DialogDescription>
      </DialogHeader>
      <div className="py-4">
        <SearchableUserSelect
          value={selectedPartnerId || ''}
          onChange={setSelectedPartnerId}
          users={partners.filter(p => !lead?.assigned_partners?.some(ap => ap.partner_id === p.id && ap.status === 'active'))}
          placeholder="Search and select partner..."
          emptyText="No partners available to assign."
          testId="partner-select"
          secondaryRender={(p) => p.company_name || 'No Company'}
        />
        {lead?.assigned_partners?.filter(p => p.status === 'active').length > 0 && (
          <p className="text-sm text-muted-foreground mt-3">
            Currently {lead.assigned_partners.filter(p => p.status === 'active').length} partner(s) actively working on this lead.
          </p>
        )}
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
        <Button onClick={onConfirm} data-testid="confirm-assign-btn">Assign Partner</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);
