import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { Tooltip } from './Tooltip';

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  shortcut?: string;
  tooltipSide?: 'top' | 'right' | 'bottom' | 'left';
  variant?: 'ghost' | 'surface' | 'danger' | 'active';
  size?: 'xs' | 'sm' | 'md';
  icon: React.ReactNode;
}

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      label,
      shortcut,
      tooltipSide = 'bottom',
      variant = 'ghost',
      size = 'sm',
      icon,
      className,
      disabled,
      type = 'button',
      ...props
    },
    ref
  ) => {
    const baseClasses =
      'inline-flex items-center justify-center rounded-md transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:opacity-50 disabled:pointer-events-none select-none shrink-0';

    const variants = {
      ghost: 'text-text-secondary hover:text-text-primary hover:bg-canvas-surface active:bg-canvas-elevated',
      surface:
        'bg-canvas-surface border border-canvas-border text-text-secondary hover:text-text-primary hover:bg-canvas-elevated hover:border-canvas-borderHover',
      active: 'bg-accent/15 text-accent border border-accent/30',
      danger: 'text-text-muted hover:text-status-danger hover:bg-status-danger/10',
    };

    const sizes = {
      xs: 'w-6 h-6',
      sm: 'w-7 h-7',
      md: 'w-8 h-8',
    };

    const buttonEl = (
      <button
        ref={ref}
        type={type}
        aria-label={label}
        disabled={disabled}
        className={twMerge(clsx(baseClasses, variants[variant], sizes[size], className))}
        {...props}
      >
        {icon}
      </button>
    );

    return (
      <Tooltip content={label} shortcut={shortcut} side={tooltipSide}>
        {buttonEl}
      </Tooltip>
    );
  }
);

IconButton.displayName = 'IconButton';
