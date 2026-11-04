import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ children, className, interactive = false, padding = 'md', ...props }, ref) => {
    const paddings = {
      none: '',
      sm: 'p-3',
      md: 'p-4',
      lg: 'p-5',
    };

    return (
      <div
        ref={ref}
        className={twMerge(
          clsx(
            'rounded-lg bg-canvas-surface border border-canvas-border transition-colors duration-fast',
            interactive &&
              'cursor-pointer hover:bg-canvas-elevated hover:border-canvas-borderHover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60',
            paddings[padding],
            className
          )
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';
