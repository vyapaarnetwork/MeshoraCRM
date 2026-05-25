import { useState, useEffect, useRef } from 'react';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Send } from 'lucide-react';
import api from '../utils/api';

/**
 * Comment input with @mention autocomplete.
 * - Detects '@' character, fetches users matching the trailing query.
 * - Up/Down/Enter to select; Esc to close.
 */
const CommentInputWithMentions = ({ value, onChange, onSubmit, submitting, placeholder = 'Add a comment… use @ to mention' }) => {
  const [users, setUsers] = useState([]);
  const [mentionState, setMentionState] = useState({ active: false, query: '', start: -1, highlight: 0 });
  const inputRef = useRef(null);

  // Lazy-load user list once
  useEffect(() => {
    let cancelled = false;
    api.get('/users').then((r) => {
      if (!cancelled) setUsers(r.data || []);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const detectMention = (text, caretPos) => {
    // Walk back from caret to find an '@' not preceded by alphanumeric
    let i = caretPos - 1;
    while (i >= 0 && /[\w.\-]/.test(text[i])) i--;
    if (i >= 0 && text[i] === '@' && (i === 0 || /\s/.test(text[i - 1]))) {
      return { start: i, query: text.slice(i + 1, caretPos) };
    }
    return null;
  };

  const handleChange = (e) => {
    const newValue = e.target.value;
    onChange(newValue);
    const caret = e.target.selectionStart || newValue.length;
    const m = detectMention(newValue, caret);
    if (m) {
      setMentionState({ active: true, query: m.query, start: m.start, highlight: 0 });
    } else {
      setMentionState((s) => (s.active ? { ...s, active: false } : s));
    }
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

  const insertMention = (user) => {
    const handle = (user.name || user.email).split(/\s+/)[0].replace(/[^a-zA-Z0-9.\-_]/g, '');
    const before = value.slice(0, mentionState.start);
    // Find end of current mention token after the @
    const afterStart = mentionState.start + 1 + (mentionState.query || '').length;
    const after = value.slice(afterStart);
    const newVal = `${before}@${handle} ${after}`;
    onChange(newVal);
    setMentionState({ active: false, query: '', start: -1, highlight: 0 });
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleKeyDown = (e) => {
    if (!mentionState.active || filtered.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setMentionState((s) => ({ ...s, highlight: (s.highlight + 1) % filtered.length }));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setMentionState((s) => ({ ...s, highlight: (s.highlight - 1 + filtered.length) % filtered.length }));
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      insertMention(filtered[mentionState.highlight]);
    } else if (e.key === 'Escape') {
      setMentionState((s) => ({ ...s, active: false }));
    }
  };

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); if (value.trim() && !submitting) onSubmit(e); }}
      className="relative flex gap-2"
      data-testid="comment-form"
    >
      <div className="flex-1 relative">
        <Input
          ref={inputRef}
          placeholder={placeholder}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={submitting}
          data-testid="comment-input"
        />
        {mentionState.active && filtered.length > 0 && (
          <div
            className="absolute left-0 right-0 bottom-full mb-1 z-50 bg-popover border rounded-md shadow-lg overflow-hidden"
            data-testid="mention-dropdown"
          >
            {filtered.map((u, i) => (
              <button
                key={u.id}
                type="button"
                className={`w-full text-left px-3 py-1.5 text-sm flex items-center gap-2 ${
                  i === mentionState.highlight ? 'bg-accent text-accent-foreground' : 'hover:bg-accent'
                }`}
                onMouseDown={(e) => { e.preventDefault(); insertMention(u); }}
                data-testid={`mention-option-${u.id}`}
              >
                <span className="w-5 h-5 rounded-full bg-primary text-white text-[10px] flex items-center justify-center font-semibold">
                  {(u.name || '?').charAt(0).toUpperCase()}
                </span>
                <span className="truncate">
                  <span className="font-medium">{u.name}</span>
                  <span className="text-xs text-muted-foreground ml-2">{u.email}</span>
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
      <Button
        type="submit"
        disabled={submitting || !value.trim()}
        data-testid="submit-comment-btn"
      >
        <Send className="w-4 h-4" />
      </Button>
    </form>
  );
};

export default CommentInputWithMentions;
