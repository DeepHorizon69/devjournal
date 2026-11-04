import React from 'react';
import { Search, X } from 'lucide-react';
import { Input, InputProps } from './Input';

export interface SearchInputProps extends Omit<InputProps, 'leadingIcon'> {
  onClear?: () => void;
  shortcut?: string;
}

export const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
  ({ value, onClear, shortcut, inputSize = 'md', ...props }, ref) => {
    const hasValue = Boolean(value && String(value).length > 0);

    return (
      <Input
        ref={ref}
        type="search"
        value={value}
        inputSize={inputSize}
        leadingIcon={<Search size={14} />}
        trailingElement={
          hasValue && onClear ? (
            <button
              type="button"
              onClick={onClear}
              aria-label="Clear search"
              className="p-0.5 text-text-muted hover:text-text-primary rounded transition-colors"
            >
              <X size={13} />
            </button>
          ) : shortcut ? (
            <kbd className="pointer-events-none rounded bg-canvas-app px-1.5 py-0.5 font-mono text-[10px] text-text-muted border border-canvas-border">
              {shortcut}
            </kbd>
          ) : undefined
        }
        {...props}
      />
    );
  }
);

SearchInput.displayName = 'SearchInput';
