import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'muted' | 'accent' | 'success' | 'warning' | 'danger' | 'domain';
  size?: 'sm' | 'md';
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  className,
  variant = 'default',
  size = 'sm',
  dot = false,
  ...props
}) => {
  const baseClasses =
    'inline-flex items-center gap-1.5 font-medium rounded border select-none shrink-0';

  const variants = {
    default: 'bg-canvas-surface text-text-secondary border-canvas-border',
    muted: 'bg-canvas-app/80 text-text-muted border-canvas-border/70',
    accent: 'bg-accent/10 text-accent border-accent/25',
    success: 'bg-status-success/10 text-status-success border-status-success/25',
    warning: 'bg-status-warning/10 text-status-warning border-status-warning/25',
    danger: 'bg-status-danger/10 text-status-danger border-status-danger/25',
    domain: 'bg-canvas-elevated/80 text-text-secondary border-canvas-border',
  };

  const dotColors = {
    default: 'bg-text-secondary',
    muted: 'bg-text-muted',
    accent: 'bg-accent',
    success: 'bg-status-success',
    warning: 'bg-status-warning',
    danger: 'bg-status-danger',
    domain: 'bg-accent',
  };

  const sizes = {
    sm: 'text-[11px] px-1.5 py-0.5 leading-none',
    md: 'text-xs px-2 py-0.5 leading-tight',
  };

  return (
    <span
      className={twMerge(clsx(baseClasses, variants[variant], sizes[size], className))}
      {...props}
    >
      {dot && <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', dotColors[variant])} />}
      {children}
    </span>
  );
};
