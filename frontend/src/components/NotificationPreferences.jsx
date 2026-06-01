import { useEffect, useState } from 'react';
import { Bell, Loader2 } from 'lucide-react';
import { Switch } from './ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import api from '../utils/api';

/**
 * Notification preference toggles.
 * Pass `value` (dict of {type_key: bool}) and `onChange` to control externally,
 * OR omit them and the component fetches the current user's prefs and saves
 * directly via PUT /profile (self-mode).
 *
 * Props:
 *   - value, onChange (controlled mode)
 *   - selfMode: boolean — when true, auto-saves to /profile on toggle
 *   - testIdPrefix
 */
export const NotificationPreferences = ({
  value,
  onChange,
  selfMode = false,
  initialFromUser = null,
  testIdPrefix = 'notif-pref',
}) => {
  const [types, setTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [local, setLocal] = useState(value || initialFromUser || {});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get('/notifications/types');
        if (!cancelled) setTypes(res.data || []);
      } catch (e) {
        // Silently ignore — UI will show empty list.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (value !== undefined) setLocal(value || {});
  }, [value]);

  const isOn = (key) => {
    if (local && Object.prototype.hasOwnProperty.call(local, key)) return !!local[key];
    return true; // default: enabled
  };

  const toggle = async (key) => {
    const next = { ...(local || {}), [key]: !isOn(key) };
    setLocal(next);
    if (onChange) onChange(next);
    if (selfMode) {
      setSaving(true);
      try {
        await api.put('/profile', { notification_preferences: next });
      } catch (e) {
        // Revert on failure
        setLocal(local);
        if (onChange) onChange(local);
      } finally {
        setSaving(false);
      }
    }
  };

  return (
    <Card data-testid={`${testIdPrefix}-card`}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bell className="w-5 h-5 text-primary" />
          Email Notifications
          {saving && <Loader2 className="w-4 h-4 animate-spin opacity-60" />}
        </CardTitle>
        <CardDescription>
          Choose which events trigger an email to {selfMode ? 'you' : 'this user'}.
          New preferences apply immediately.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading && (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
        {!loading && types.length === 0 && (
          <p className="text-sm text-muted-foreground">No notification types configured.</p>
        )}
        {types.map((t) => (
          <div
            key={t.key}
            className="flex items-start justify-between gap-4 py-2 border-b last:border-b-0"
            data-testid={`${testIdPrefix}-row-${t.key}`}
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{t.label}</p>
              {t.description && (
                <p className="text-xs text-muted-foreground">{t.description}</p>
              )}
            </div>
            <Switch
              checked={isOn(t.key)}
              onCheckedChange={() => toggle(t.key)}
              data-testid={`${testIdPrefix}-switch-${t.key}`}
            />
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

export default NotificationPreferences;
