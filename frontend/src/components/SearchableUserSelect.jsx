import { useState } from 'react';
import { Check, ChevronsUpDown, X, User as UserIcon } from 'lucide-react';
import { Button } from './ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from './ui/command';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { cn } from '../lib/utils';

/**
 * Reusable searchable dropdown for picking a user.
 * Type-ahead filtering, secondary line (role / company / email), and a clear button.
 *
 * Props:
 *  - value: selected user id (string | null)
 *  - onChange: (newId) => void
 *  - users: [{ id, name, email?, role?, company_name?, ...rest }]
 *  - placeholder, label, disabled, allowClear, testId, secondaryRender (optional)
 */
export const SearchableUserSelect = ({
  value,
  onChange,
  users = [],
  placeholder = 'Select user...',
  emptyText = 'No users found.',
  disabled = false,
  allowClear = true,
  testId = 'user-search-select',
  secondaryRender,
  className = '',
}) => {
  const [open, setOpen] = useState(false);
  const selected = users.find((u) => u.id === value) || null;

  const renderSecondary = (u) => {
    if (typeof secondaryRender === 'function') return secondaryRender(u);
    const parts = [];
    if (u.role) {
      const labelMap = {
        super_admin: 'Super Admin',
        selling_partner: 'Selling Partner',
        sales_associate: 'Sales Associate',
        customer: 'Customer',
        vyapaar_ops: 'Vyapaar Ops',
        vyapaar_finance: 'Vyapaar Finance',
      };
      parts.push(labelMap[u.role] || u.role);
    }
    if (u.company_name) parts.push(u.company_name);
    if (!parts.length && u.email) parts.push(u.email);
    return parts.join(' · ');
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          data-testid={testId}
          className={cn(
            'w-full justify-between font-normal',
            !selected && 'text-muted-foreground',
            className
          )}
        >
          <span className="flex items-center gap-2 truncate text-left">
            <UserIcon className="w-4 h-4 shrink-0 opacity-60" />
            <span className="truncate">
              {selected ? selected.name : placeholder}
            </span>
          </span>
          <span className="flex items-center gap-1">
            {selected && allowClear && !disabled && (
              <span
                role="button"
                tabIndex={0}
                onClick={(e) => {
                  e.stopPropagation();
                  onChange('');
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.stopPropagation();
                    onChange('');
                  }
                }}
                className="rounded-sm p-0.5 hover:bg-muted"
                data-testid={`${testId}-clear`}
              >
                <X className="w-3.5 h-3.5 opacity-60" />
              </span>
            )}
            <ChevronsUpDown className="w-4 h-4 shrink-0 opacity-50" />
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] p-0"
        align="start"
      >
        <Command
          filter={(itemValue, search) => {
            // itemValue contains all searchable text; cmdk's lowercases both.
            return itemValue.toLowerCase().includes(search.toLowerCase()) ? 1 : 0;
          }}
        >
          <CommandInput
            placeholder="Type to search..."
            data-testid={`${testId}-input`}
          />
          <CommandList>
            <CommandEmpty>{emptyText}</CommandEmpty>
            <CommandGroup>
              {users.map((u) => {
                const secondary = renderSecondary(u);
                const haystack = [u.name, u.email, secondary]
                  .filter(Boolean)
                  .join(' ');
                return (
                  <CommandItem
                    key={u.id}
                    value={`${haystack} ${u.id}`}
                    onSelect={() => {
                      onChange(u.id);
                      setOpen(false);
                    }}
                    data-testid={`${testId}-option-${u.id}`}
                  >
                    <Check
                      className={cn(
                        'mr-2 h-4 w-4',
                        value === u.id ? 'opacity-100' : 'opacity-0'
                      )}
                    />
                    <div className="flex flex-col min-w-0">
                      <span className="truncate">{u.name}</span>
                      {secondary && (
                        <span className="text-xs text-muted-foreground truncate">
                          {secondary}
                        </span>
                      )}
                    </div>
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

export default SearchableUserSelect;
