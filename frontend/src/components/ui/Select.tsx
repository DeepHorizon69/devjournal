import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { ChevronDown } from 'lucide-react';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  label?: string;
  options: SelectOption[];
  selectSize?: 'sm' | 'md';
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, options, selectSize = 'md', className, id, ...props }, ref) => {
    const sizeClasses = {
      sm: 'h-7 text-xs pl-2.5 pr-7',
      md: 'h-8 text-[13px] pl-3 pr-8',
    };

    return (
      <div className="inline-flex flex-col gap-1">
        {label && (
          <label
            htmlFor={id}
            className="text-xs font-medium text-text-secondary select-none"
          >
            {label}
          </label>
        )}
        <div className="relative inline-flex items-center">
          <select
            ref={ref}
            id={id}
            className={twMerge(
              clsx(
                'appearance-none rounded-md bg-canvas-surface border border-canvas-border text-text-primary transition-colors duration-fast hover:border-canvas-borderHover focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/40 disabled:opacity-50 cursor-pointer',
                sizeClasses[selectSize],
                className
              )
            )}
            {...props}
          >
            {options.map((opt) => (
              <option
                key={opt.value}
                value={opt.value}
                className="bg-canvas-elevated text-text-primary"
              >
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown
            size={13}
            className="pointer-events-none absolute right-2 text-text-muted"
          />
        </div>
      </div>
    );
  }
);

Select.displayName = 'Select';
