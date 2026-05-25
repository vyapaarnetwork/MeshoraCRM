import { useState } from 'react';
import { Shield, Wallet, X } from 'lucide-react';

/**
 * Subtle context banner shown when a Vyapaar Operations or Vyapaar Finance user is logged in.
 * Helps team members confirm their RBAC context and discover permission boundaries.
 * Dismissible per-session via sessionStorage.
 */
const RoleContextBanner = ({ role }) => {
  const storageKey = `meshora.roleBanner.dismissed.${role}`;
  const [dismissed, setDismissed] = useState(
    typeof window !== 'undefined' && sessionStorage.getItem(storageKey) === '1'
  );

  if (dismissed) return null;

  const config = {
    vyapaar_ops: {
      label: 'Vyapaar Operations',
      tagline: 'Full access to leads, companies & commercials. Master data and user management are admin-only.',
      icon: Shield,
      // Indigo accent — operations
      bg: 'bg-indigo-50 dark:bg-indigo-950/40',
      border: 'border-indigo-200 dark:border-indigo-900',
      iconWrap: 'bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300',
      text: 'text-indigo-900 dark:text-indigo-100',
      muted: 'text-indigo-700/80 dark:text-indigo-300/80',
    },
    vyapaar_finance: {
      label: 'Vyapaar Finance',
      tagline: 'Read-only across leads, companies & users. Full write access inside the Commercials module.',
      icon: Wallet,
      // Amber accent — finance
      bg: 'bg-amber-50 dark:bg-amber-950/40',
      border: 'border-amber-200 dark:border-amber-900',
      iconWrap: 'bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300',
      text: 'text-amber-900 dark:text-amber-100',
      muted: 'text-amber-800/80 dark:text-amber-200/80',
    },
  }[role];

  if (!config) return null;
  const Icon = config.icon;

  const handleDismiss = () => {
    sessionStorage.setItem(storageKey, '1');
    setDismissed(true);
  };

  return (
    <div
      className={`flex items-center gap-3 px-4 py-2.5 border-b ${config.bg} ${config.border}`}
      data-testid={`role-banner-${role}`}
      role="status"
      aria-live="polite"
    >
      <div className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${config.iconWrap}`}>
        <Icon className="w-3.5 h-3.5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-semibold ${config.text}`}>
          You're viewing as {config.label}
        </div>
        <div className={`text-xs ${config.muted} truncate`}>
          {config.tagline}
        </div>
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        className={`shrink-0 p-1 rounded-md hover:bg-black/5 dark:hover:bg-white/10 transition-colors ${config.muted}`}
        aria-label="Dismiss role banner"
        data-testid={`role-banner-${role}-dismiss-btn`}
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};

export default RoleContextBanner;
