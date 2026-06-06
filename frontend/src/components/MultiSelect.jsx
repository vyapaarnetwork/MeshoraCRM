import { useState } from 'react';
import { Check, ChevronsUpDown, Filter, X } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from './ui/command';

/**
 * MultiSelect — checkbox-style multi-select with search.
 * Props:
 *  - options: [{ value: string, label: string, color?: string }]
 *  - value: string[] (selected values)
 *  - onChange: (string[]) => void
 *  - placeholder: e.g. "All Statuses"
 *  - allLabel: label shown when nothing is selected (default = placeholder)
 *  - testId
 */
const MultiSelect = ({
  options = [],
  value = [],
  onChange,
  placeholder = 'Select…',
  allLabel,
  testId = 'multi-select',
  iconLeft = true,
}) => {
  const [open, setOpen] = useState(false);

  const toggle = (v) => {
    const set = new Set(value);
    if (set.has(v)) set.delete(v);
    else set.add(v);
    onChange(Array.from(set));
  };

  const clear = (e) => {
    e.stopPropagation();
    onChange([]);
  };

  const display = value.length === 0
    ? (allLabel || placeholder)
    : value.length <= 2
      ? options.filter(o => value.includes(o.value)).map(o => o.label).join(', ')
      : `${value.length} selected`;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="justify-between w-full text-left font-normal"
          data-testid={testId}
        >
          <span className="flex items-center gap-2 truncate">
            {iconLeft && <Filter className="w-3.5 h-3.5 text-muted-foreground shrink-0" />}
            <span className={cn('truncate', value.length === 0 && 'text-muted-foreground')}>{display}</span>
          </span>
          <span className="flex items-center gap-1 shrink-0">
            {value.length > 0 && (
              <span
                role="button"
                tabIndex={0}
                onClick={clear}
                onKeyDown={(e) => { if (e.key === 'Enter') clear(e); }}
                className="p-0.5 rounded hover:bg-muted"
                data-testid={`${testId}-clear`}
              >
                <X className="w-3 h-3 text-muted-foreground" />
              </span>
            )}
            <ChevronsUpDown className="w-3.5 h-3.5 text-muted-foreground" />
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput placeholder={`Search ${placeholder.toLowerCase()}…`} data-testid={`${testId}-search`} />
          <CommandList>
            <CommandEmpty>No options.</CommandEmpty>
            <CommandGroup>
              {options.map((opt) => {
                const isSelected = value.includes(opt.value);
                return (
                  <CommandItem
                    key={opt.value}
                    value={opt.label}
                    onSelect={() => toggle(opt.value)}
                    data-testid={`${testId}-opt-${opt.value}`}
                    className="flex items-center gap-2 cursor-pointer"
                  >
                    <div className={cn(
                      'flex h-4 w-4 items-center justify-center rounded border',
                      isSelected ? 'bg-primary border-primary text-primary-foreground' : 'border-muted-foreground/40',
                    )}>
                      {isSelected && <Check className="h-3 w-3" />}
                    </div>
                    {opt.color && (
                      <span className="w-2 h-2 rounded-full" style={{ background: opt.color }} />
                    )}
                    <span className="flex-1 truncate">{opt.label}</span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};

export const MultiSelectChips = ({ options, value, onChange, testId = 'multi-chips' }) => (
  <div className="flex flex-wrap gap-1" data-testid={testId}>
    {options.filter(o => value.includes(o.value)).map(o => (
      <Badge
        key={o.value}
        variant="secondary"
        className="text-[10px]"
        onClick={() => onChange(value.filter(v => v !== o.value))}
      >
        {o.label} <X className="w-2.5 h-2.5 ml-1" />
      </Badge>
    ))}
  </div>
);

export default MultiSelect;
