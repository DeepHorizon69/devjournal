import React from 'react';
import { create } from 'zustand';
import { clsx } from 'clsx';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export type ToastVariant = 'success' | 'error' | 'info';

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastState {
  toasts: ToastItem[];
  addToast: (toast: Omit<ToastItem, 'id'>) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (toast) => {
    const id = Math.random().toString(36).slice(2, 9);
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }));
    }, 3500);
  },
  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
    >
      {toasts.map((toast) => {
        const variant = toast.variant || 'info';
        const iconMap = {
          success: <CheckCircle2 size={15} className="text-status-success shrink-0" />,
          error: <AlertCircle size={15} className="text-status-danger shrink-0" />,
          info: <Info size={15} className="text-accent shrink-0" />,
        };

        return (
          <div
            key={toast.id}
            role="status"
            className={clsx(
              'pointer-events-auto flex items-start justify-between gap-3 rounded-lg bg-canvas-elevated border border-canvas-border px-3.5 py-2.5 shadow-xl text-xs'
            )}
          >
            <div className="flex items-start gap-2.5 min-w-0">
              <span className="mt-0.5">{iconMap[variant]}</span>
              <div className="min-w-0">
                <p className="font-medium text-text-primary">{toast.title}</p>
                {toast.description && (
                  <p className="text-text-secondary mt-0.5 leading-relaxed">
                    {toast.description}
                  </p>
                )}
              </div>
            </div>
            <button
              type="button"
              onClick={() => removeToast(toast.id)}
              aria-label="Dismiss notification"
              className="text-text-muted hover:text-text-primary p-0.5 rounded"
            >
              <X size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
};
