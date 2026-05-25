import { HelpCircle, Sparkles } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';

/**
 * FeatureInfo — a small `?` icon that opens a popover with feature explanation.
 *
 * Usage:
 *   <FeatureInfo title="Lead Health Score">
 *     <p>Hot leads have recent activity and pending follow-ups...</p>
 *   </FeatureInfo>
 *
 * Or with structured props:
 *   <FeatureInfo
 *     title="AI Command Bar"
 *     description="Ask Meshora anything in natural language..."
 *     howTo="Press ⌘K (Mac) or Ctrl+K (Windows)..."
 *     tip="Try: 'Show me at-risk leads in healthcare'"
 *   />
 */
const FeatureInfo = ({
  title,
  description,
  howTo,
  tip,
  children,
  size = 'sm',
  ai = false,
  align = 'start',
  testId,
}) => {
  const iconSize = size === 'xs' ? 'w-3 h-3' : size === 'lg' ? 'w-5 h-5' : 'w-4 h-4';
  const Icon = ai ? Sparkles : HelpCircle;
  const iconColor = ai ? 'text-violet-500 hover:text-violet-600' : 'text-muted-foreground hover:text-foreground';

  return (
    <Popover>
      <PopoverTrigger
        asChild
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          aria-label={`Learn about ${title}`}
          className={`inline-flex items-center justify-center transition-colors ${iconColor} hover:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded-full`}
          data-testid={testId || `feature-info-${(title || 'item').toLowerCase().replace(/\s+/g, '-')}`}
        >
          <Icon className={iconSize} />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align={align}
        className="w-80 p-0 shadow-lg border-violet-200 dark:border-violet-900"
        sideOffset={6}
      >
        <div className="p-4 space-y-2">
          <div className="flex items-center gap-2">
            <span className={`p-1 rounded-md ${ai ? 'bg-gradient-to-br from-violet-500 to-indigo-500 text-white' : 'bg-violet-100 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300'}`}>
              <Icon className="w-3.5 h-3.5" />
            </span>
            <h4 className="text-sm font-semibold">{title}</h4>
          </div>
          {children ? (
            <div className="text-xs text-muted-foreground leading-relaxed space-y-1.5">{children}</div>
          ) : (
            <>
              {description && (
                <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
              )}
              {howTo && (
                <div className="text-xs text-muted-foreground leading-relaxed">
                  <span className="font-medium text-foreground">How to use:</span> {howTo}
                </div>
              )}
              {tip && (
                <div className="text-xs leading-relaxed mt-2 p-2 rounded-md bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-200 border border-amber-200 dark:border-amber-900/50">
                  💡 <span className="font-medium">Tip:</span> {tip}
                </div>
              )}
            </>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default FeatureInfo;
