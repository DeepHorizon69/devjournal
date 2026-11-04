import React from 'react';
import { clsx } from 'clsx';
import { Popover } from './Popover';

export interface DropdownItem {
  label: string;
  icon?: React.ReactNode;
  shortcut?: string;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

export interface DropdownProps {
  trigger: React.ReactElement<{ onClick?: (e: React.MouseEvent) => void }>;
  items: DropdownItem[];
  align?: 'left' | 'right';
}

export const Dropdown: React.FC<DropdownProps> = ({
  trigger,
  items,
  align = 'right',
}) => {
  return (
    <Popover trigger={trigger} align={align} className="p-1 min-w-[168px]">
      {(close) => (
        <div role="menu" className="flex flex-col gap-0.5">
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                item.onClick();
                close();
              }}
              className={clsx(
                'flex items-center justify-between gap-3 w-full px-2.5 py-1.5 rounded text-xs font-medium text-left transition-colors duration-fast disabled:opacity-50',
                item.danger
                  ? 'text-status-danger hover:bg-status-danger/15'
                  : 'text-text-secondary hover:text-text-primary hover:bg-canvas-surface'
              )}
            >
              <span className="flex items-center gap-2 truncate">
                {item.icon && <span className="shrink-0">{item.icon}</span>}
                <span className="truncate">{item.label}</span>
              </span>
              {item.shortcut && (
                <kbd className="text-[10px] font-mono text-text-muted">
                  {item.shortcut}
                </kbd>
              )}
            </button>
          ))}
        </div>
      )}
    </Popover>
  );
};
