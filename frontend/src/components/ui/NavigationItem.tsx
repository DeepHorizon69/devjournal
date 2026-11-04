import React from 'react';
import { NavLink } from 'react-router-dom';
import { clsx } from 'clsx';
import { LucideIcon } from 'lucide-react';
import { Tooltip } from './Tooltip';

export interface NavigationItemProps {
  name: string;
  to: string;
  icon: LucideIcon;
  count?: number;
  end?: boolean;
  collapsed?: boolean;
  onClick?: () => void;
}

export const NavigationItem: React.FC<NavigationItemProps> = ({
  name,
  to,
  icon: Icon,
  count,
  end = false,
  collapsed = false,
  onClick,
}) => {
  const linkEl = (
    <NavLink
      to={to}
      end={end}
      aria-label={name}
      onClick={onClick}
      className={({ isActive }) =>
        clsx(
          'group relative flex items-center h-[30px] rounded-md text-[13px] font-medium transition-colors duration-fast select-none overflow-hidden',
          collapsed
            ? 'justify-center w-9 mx-auto px-0 shrink-0'
            : 'justify-between px-2.5 w-full',
          isActive
            ? 'bg-accent/10 text-text-primary before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-[2px] before:rounded-full before:bg-accent'
            : 'text-text-secondary hover:text-text-primary hover:bg-canvas-surface/80'
        )
      }
    >
      {({ isActive }) => (
        <>
          <div
            className={clsx(
              'flex items-center',
              collapsed ? 'justify-center w-full' : 'gap-2.5 min-w-0 flex-1'
            )}
          >
            <Icon
              size={16}
              className={clsx(
                'shrink-0 transition-colors duration-fast',
                isActive ? 'text-accent' : 'text-text-muted group-hover:text-text-secondary'
              )}
            />
            {!collapsed && <span className="truncate">{name}</span>}
          </div>

          {!collapsed && count !== undefined && count > 0 && (
            <span
              className={clsx(
                'text-[11px] font-mono px-1.5 py-0.5 rounded leading-none transition-colors shrink-0 ml-2',
                isActive
                  ? 'text-accent bg-accent/10'
                  : 'text-text-muted group-hover:text-text-secondary'
              )}
            >
              {count}
            </span>
          )}
        </>
      )}
    </NavLink>
  );

  if (collapsed) {
    const tooltipText = count !== undefined && count > 0 ? `${name} (${count})` : name;
    return (
      <div className="flex justify-center w-full">
        <Tooltip content={tooltipText} side="right">
          {linkEl}
        </Tooltip>
      </div>
    );
  }

  return linkEl;
};
