import { useState, useRef, useEffect } from 'react';
import { Textarea } from './ui/textarea';

/**
 * Phase 36 — Multi-line description input with @mention autocomplete.
 * - Detects '@' character, fetches users matching the trailing query.
 * - Up/Down/Enter to select; Esc to close.
 * - Backend (_parse_mentions) treats anything matching @[a-zA-Z][\w.\-]+ as a
 *   handle and fires email + in-app notification to the matched user.
 */
const MentionTextarea = ({
  value,
  onChange,
  users = [],
  rows = 3,
  placeholder = 'Type @ to mention a teammate…',
  testId = 'mention-textarea',
}) => {
  const [mentionState, setMentionState] = useState({ active: false, query: '', start: -1, highlight: 0 });
  const ref = useRef(null);
  const [caret, setCaret] = useState(null);

  const detect = (text, caretPos) => {
    let i = caretPos - 1;
    while (i >= 0 && /[\w.\-]/.test(text[i])) i--;
    if (i >= 0 && text[i] === '@' && (i === 0 || /\s/.test(text[i - 1]))) {
      return { start: i, query: text.slice(i + 1, caretPos) };
    }
    return null;
  };

  const handleChange = (e) => {
    const v = e.target.value;
    onChange(v);
    const pos = e.target.selectionStart ?? v.length;
    setCaret(pos);
    const m = detect(v, pos);
    if (m) setMentionState({ active: true, query: m.query, start: m.start, highlight: 0 });
    else if (mentionState.active) setMentionState((s) => ({ ...s, active: false }));
  };

  const filtered = mentionState.active
    ? users
        .filter((u) => u.is_active !== false)
        .filter((u) => {
          const q = (mentionState.query || '').toLowerCase();
          if (!q) return true;
          return (
            (u.name || '').toLowerCase().startsWith(q) ||
            (u.email || '').toLowerCase().startsWith(q)
          );
        })
        .slice(0, 6)
    : [];

  const insert = (user) => {
    const handle = (user.name || user.email).split(/\s+/)[0].replace(/[^a-zA-Z0-9.\-_]/g, '');
    const before = value.slice(0, mentionState.start);
    const afterStart = mentionState.start + 1 + (mentionState.query || '').length;
    const after = value.slice(afterStart);
    const newVal = `${before}@${handle} ${after}`;
    onChange(newVal);
    setMentionState({ active: false, query: '', start: -1, highlight: 0 });
    setTimeout(() => {
      ref.current?.focus();
      const newCaret = before.length + 1 + handle.length + 1;
      try { ref.current?.setSelectionRange(newCaret, newCaret); } catch (e) { /* noop */ }
    }, 0);
  };

  const handleKey = (e) => {
    if (!mentionState.active || filtered.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setMentionState((s) => ({ ...s, highlight: (s.highlight + 1) % filtered.length }));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setMentionState((s) => ({ ...s, highlight: (s.highlight - 1 + filtered.length) % filtered.length }));
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      insert(filtered[mentionState.highlight]);
    } else if (e.key === 'Escape') {
      setMentionState((s) => ({ ...s, active: false }));
    }
  };

  // Compute dropdown position (anchored under the caret line — simple: just under textarea)
  return (
    <div className="relative" data-testid={`${testId}-wrapper`}>
      <Textarea
        ref={ref}
        rows={rows}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKey}
        onSelect={(e) => setCaret(e.target.selectionStart)}
        placeholder={placeholder}
        data-testid={testId}
      />
      {mentionState.active && filtered.length > 0 && (
        <div
          className="absolute left-0 top-full z-50 mt-1 w-72 max-w-full bg-popover border rounded-md shadow-lg overflow-hidden"
          data-testid="mention-dropdown"
        >
          {filtered.map((u, i) => (
            <button
              key={u.id}
              type="button"
              className={`w-full text-left px-3 py-1.5 text-sm flex items-center gap-2 ${
                i === mentionState.highlight ? 'bg-accent text-accent-foreground' : 'hover:bg-accent'
              }`}
              onMouseDown={(e) => { e.preventDefault(); insert(u); }}
              data-testid={`mention-option-${u.id}`}
            >
              <span className="w-5 h-5 rounded-full bg-violet-600 text-white text-[10px] flex items-center justify-center font-semibold">
                {(u.name || '?').charAt(0).toUpperCase()}
              </span>
              <span className="truncate flex-1">
                <span className="font-medium">{u.name}</span>
                <span className="text-xs text-muted-foreground ml-2">{u.email}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default MentionTextarea;
