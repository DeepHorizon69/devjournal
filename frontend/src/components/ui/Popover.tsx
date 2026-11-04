import React, { useState, useRef, useEffect } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface PopoverProps {
  trigger: React.ReactElement<{ onClick?: (e: React.MouseEvent) => void }>;
  children: React.ReactNode | ((close: () => void) => React.ReactNode);
  align?: 'left' | 'right';
  className?: string;
}

export const Popover: React.FC<PopoverProps> = ({
  trigger,
  children,
  align = 'left',
  className,
}) => {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative inline-flex">
      {React.cloneElement(trigger, {
        onClick: (e: React.MouseEvent) => {
          trigger.props.onClick?.(e);
          setOpen((prev) => !prev);
        },
      })}

      {open && (
        <div
          className={twMerge(
            clsx(
              'absolute top-full mt-1.5 z-40 min-w-[180px] rounded-lg bg-canvas-elevated border border-canvas-border p-2 shadow-xl transition-all duration-fast',
              align === 'right' ? 'right-0' : 'left-0',
              className
            )
          )}
        >
          {typeof children === 'function' ? children(() => setOpen(false)) : children}
        </div>
      )}
    </div>
  );
};
