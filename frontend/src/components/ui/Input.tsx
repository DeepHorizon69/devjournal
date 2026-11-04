import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  leadingIcon?: React.ReactNode;
  trailingElement?: React.ReactNode;
  inputSize?: 'sm' | 'md';
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      leadingIcon,
      trailingElement,
      inputSize = 'md',
      className,
      id,
      ...props
    },
    ref
  ) => {
    const sizeClasses = {
      sm: 'h-7 text-xs px-2.5',
      md: 'h-8 text-[13px] px-3',
    };

    return (
      <div className="flex flex-col gap-1 w-full">
        {label && (
          <label
            htmlFor={id}
            className="text-xs font-medium text-text-secondary select-none"
          >
            {label}
          </label>
        )}
        <div className="relative flex items-center w-full">
          {leadingIcon && (
            <span className="pointer-events-none absolute left-2.5 text-text-muted flex items-center">
              {leadingIcon}
            </span>
          )}
          <input
            ref={ref}
            id={id}
            className={twMerge(
              clsx(
                'w-full rounded-md bg-canvas-surface border border-canvas-border text-text-primary placeholder:text-text-muted transition-colors duration-fast focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/40 disabled:opacity-50 disabled:cursor-not-allowed',
                sizeClasses[inputSize],
                leadingIcon && 'pl-8',
                trailingElement && 'pr-8',
                error && 'border-status-danger focus:border-status-danger focus:ring-status-danger/40',
                className
              )
            )}
            {...props}
          />
          {trailingElement && (
            <div className="absolute right-2 flex items-center">{trailingElement}</div>
          )}
        </div>
        {error && <span className="text-[11px] text-status-danger">{error}</span>}
      </div>
    );
  }
);

Input.displayName = 'Input';
