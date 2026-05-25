/**
 * Meshora brand mark — purple-violet gradient infinity/M loop + wordmark.
 * Inline SVG so it scales perfectly and themes via currentColor for the wordmark.
 */

export const MeshoraMark = ({ size = 40, className = '' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 64 64"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="meshora-grad" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#6366F1" />
        <stop offset="0.5" stopColor="#8B5CF6" />
        <stop offset="1" stopColor="#A855F7" />
      </linearGradient>
    </defs>
    {/* Sparkle dots */}
    <circle cx="6" cy="10" r="1.4" fill="url(#meshora-grad)" opacity="0.7" />
    <circle cx="58" cy="54" r="1.2" fill="url(#meshora-grad)" opacity="0.6" />
    {/* Infinity/M loop — two overlapping circles forming the M with a knot */}
    <path
      d="M20 18 C 10 18, 6 28, 12 38 C 18 48, 28 48, 32 38 L 32 38 C 36 48, 46 48, 52 38 C 58 28, 54 18, 44 18 C 38 18, 34 24, 32 30 C 30 24, 26 18, 20 18 Z"
      stroke="url(#meshora-grad)"
      strokeWidth="4.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    />
    {/* Central knot dot */}
    <circle cx="32" cy="32" r="2.6" fill="url(#meshora-grad)" />
  </svg>
);

export const MeshoraLogo = ({ size = 40, showTagline = true, className = '' }) => (
  <div className={`flex items-center gap-3 ${className}`} data-testid="meshora-logo">
    <MeshoraMark size={size} />
    <div className="leading-tight">
      <div
        className="font-bold tracking-tight"
        style={{
          fontSize: `${size * 0.65}px`,
          background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A855F7 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
        }}
      >
        Meshora
      </div>
      {showTagline && (
        <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground mt-0.5">
          Collaboration That Converts
        </div>
      )}
    </div>
  </div>
);

/** Variant for dark backgrounds (sidebar): wordmark goes white instead of gradient text. */
export const MeshoraLogoOnDark = ({ size = 40, showTagline = true, className = '' }) => (
  <div className={`flex items-center gap-3 ${className}`} data-testid="meshora-logo-dark">
    <MeshoraMark size={size} />
    <div className="leading-tight">
      <div className="font-bold tracking-tight text-white" style={{ fontSize: `${size * 0.65}px` }}>
        Meshora
      </div>
      {showTagline && (
        <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400 mt-0.5">
          Collaboration That Converts
        </div>
      )}
    </div>
  </div>
);

export default MeshoraLogo;
