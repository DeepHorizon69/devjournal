import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'surface' | 'ghost' | 'danger';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      className,
      variant = 'primary',
      size = 'md',
      icon,
      trailingIcon,
      loading = false,
      disabled,
      type = 'button',
      ...props
    },
    ref
  ) => {
    const baseClasses =
      'inline-flex items-center justify-center font-medium rounded-md transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 active:translate-y-[0.5px] disabled:opacity-50 disabled:pointer-events-none select-none shrink-0';

    const variants = {
      primary:
        'bg-accent text-canvas-app hover:bg-accent-hover active:bg-accent font-semibold',
      secondary:
        'bg-canvas-surface border border-canvas-border text-text-primary hover:bg-canvas-elevated hover:border-canvas-borderHover active:bg-canvas-surface',
      surface:
        'bg-canvas-elevated border border-canvas-border text-text-primary hover:border-accent/40 hover:bg-canvas-elevated/90',
      ghost:
        'text-text-secondary hover:text-text-primary hover:bg-canvas-surface active:bg-canvas-elevated',
      danger:
        'bg-status-danger/10 text-status-danger border border-status-danger/25 hover:bg-status-danger/20',
    };

    const sizes = {
      xs: 'text-xs px-2 py-1 h-7 gap-1.5',
      sm: 'text-xs px-2.5 py-1.5 h-8 gap-1.5',
      md: 'text-[13px] px-3 py-1.5 h-8 gap-2',
      lg: 'text-sm px-4 py-2 h-10 gap-2',
    };

    return (
      <button
        ref={ref}
        type={type}
        className={twMerge(clsx(baseClasses, variants[variant], sizes[size], className))}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? (
          <Loader2 size={14} className="animate-spin shrink-0" />
        ) : (
          icon && <span className="shrink-0 flex items-center">{icon}</span>
        )}
        {children && <span className="truncate">{children}</span>}
        {trailingIcon && !loading && (
          <span className="shrink-0 flex items-center">{trailingIcon}</span>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
