import React, { useState, useRef, useLayoutEffect, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface TooltipProps {
  content: React.ReactNode;
  shortcut?: string;
  side?: 'top' | 'right' | 'bottom' | 'left';
  disabled?: boolean;
  children: React.ReactElement;
  className?: string;
}

interface Coords {
  top: number;
  left: number;
}

export const Tooltip: React.FC<TooltipProps> = ({
  content,
  shortcut,
  side = 'top',
  disabled = false,
  children,
  className,
}) => {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState<Coords>({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const updatePosition = () => {
    const triggerEl = triggerRef.current;
    if (!triggerEl) return;

    const rect = triggerEl.getBoundingClientRect();
    const tooltipEl = tooltipRef.current;
    const tipWidth = tooltipEl ? tooltipEl.offsetWidth : 120;
    const tipHeight = tooltipEl ? tooltipEl.offsetHeight : 28;
    const gap = 8;
    const viewportPadding = 8;

    let top = 0;
    let left = 0;

    if (side === 'right') {
      top = rect.top + rect.height / 2 - tipHeight / 2;
      const asideEl = triggerEl.closest('aside');
      const baseRight = asideEl
        ? Math.max(rect.right, asideEl.getBoundingClientRect().right)
        : rect.right;
      left = baseRight + gap;
    } else if (side === 'left') {
      top = rect.top + rect.height / 2 - tipHeight / 2;
      left = rect.left - tipWidth - gap;
    } else if (side === 'bottom') {
      top = rect.bottom + gap;
      left = rect.left + rect.width / 2 - tipWidth / 2;
    } else {
      // top
      top = rect.top - tipHeight - gap;
      left = rect.left + rect.width / 2 - tipWidth / 2;
    }

    // Clamp within viewport boundaries so tooltips are never clipped off-screen
    const maxLeft = Math.max(viewportPadding, window.innerWidth - tipWidth - viewportPadding);
    const maxTop = Math.max(viewportPadding, window.innerHeight - tipHeight - viewportPadding);

    left = Math.min(Math.max(viewportPadding, left), maxLeft);
    top = Math.min(Math.max(viewportPadding, top), maxTop);

    setCoords({ top, left });
  };

  useLayoutEffect(() => {
    if (visible) {
      updatePosition();
    }
  }, [visible, side, content, shortcut]);

  useEffect(() => {
    if (!visible) return;
    const handleScrollOrResize = () => updatePosition();
    window.addEventListener('scroll', handleScrollOrResize, true);
    window.addEventListener('resize', handleScrollOrResize);
    return () => {
      window.removeEventListener('scroll', handleScrollOrResize, true);
      window.removeEventListener('resize', handleScrollOrResize);
    };
  }, [visible]);

  if (disabled || !content) {
    return children;
  }

  const tooltipNode = visible ? (
    <div
      ref={tooltipRef}
      role="tooltip"
      style={{
        position: 'fixed',
        top: `${coords.top}px`,
        left: `${coords.left}px`,
        zIndex: 9999,
      }}
      className={twMerge(
        clsx(
          'pointer-events-none flex items-center gap-1.5 whitespace-nowrap rounded-md bg-canvas-elevated px-2.5 py-1 text-xs font-medium text-text-primary border border-canvas-borderHover shadow-lg transition-opacity duration-fast',
          className
        )
      )}
    >
      <span>{content}</span>
      {shortcut && (
        <kbd className="rounded bg-canvas-app px-1 py-0.5 font-mono text-[10px] text-text-muted border border-canvas-border">
          {shortcut}
        </kbd>
      )}
    </div>
  ) : null;

  return (
    <div
      ref={triggerRef}
      className="inline-flex items-center justify-center"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {typeof document !== 'undefined' && tooltipNode
        ? createPortal(tooltipNode, document.body)
        : tooltipNode}
    </div>
  );
};
