import React, { useEffect } from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { X } from 'lucide-react';
import { IconButton } from './IconButton';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  maxWidth = 'md',
  className,
}) => {
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const widths = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
      className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] px-4"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/65 backdrop-blur-[2px] transition-opacity"
        onClick={onClose}
      />

      {/* Dialog panel */}
      <div
        className={twMerge(
          clsx(
            'relative z-10 w-full rounded-xl bg-canvas-sidebar border border-canvas-border shadow-2xl overflow-hidden',
            widths[maxWidth],
            className
          )
        )}
      >
        {title && (
          <div className="flex items-start justify-between gap-4 px-5 py-3.5 border-b border-canvas-border bg-canvas-surface/40">
            <div>
              <h2
                id="modal-title"
                className="text-sm font-semibold text-text-primary tracking-tight"
              >
                {title}
              </h2>
              {description && (
                <p className="text-xs text-text-secondary mt-0.5">{description}</p>
              )}
            </div>
            <IconButton
              label="Close modal"
              shortcut="Esc"
              size="xs"
              icon={<X size={15} />}
              onClick={onClose}
            />
          </div>
        )}

        <div className="p-5">{children}</div>

        {footer && (
          <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-canvas-border bg-canvas-surface/40">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};
