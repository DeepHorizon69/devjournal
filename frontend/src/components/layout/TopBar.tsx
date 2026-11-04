import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { PanelLeft, PanelLeftClose, Menu, Search } from 'lucide-react';
import { useUIStore } from '../../store/useUIStore';
import { IconButton } from '../ui/IconButton';

const DOMAIN_LABELS: Record<string, string> = {
  networking: 'Networking',
  linux: 'Linux',
  programming: 'Programming',
  iot: 'IoT',
  cybersecurity: 'Cybersecurity',
  homelab: 'Homelab',
  mathematics: 'Mathematics',
};

export const TopBar: React.FC = () => {
  const {
    isSidebarCollapsed,
    toggleSidebar,
    setMobileDrawerOpen,
    setCommandPaletteOpen,
  } = useUIStore();
  const location = useLocation();

  const pathParts = location.pathname.split('/').filter(Boolean);

  const formatBreadcrumb = (part: string) => {
    if (part === 'notes') return 'All Notes';
    if (part === 'experiments') return 'Experiments';
    if (part === 'troubleshooting') return 'Troubleshooting';
    if (part === 'projects') return 'Projects';
    if (part === 'daily') return 'Daily Journal';
    if (part === 'settings') return 'Settings';
    if (part === 'search') return 'Search';
    if (part === 'domains') return 'Domains';
    const lower = part.toLowerCase();
    if (DOMAIN_LABELS[lower]) return DOMAIN_LABELS[lower];
    return part.charAt(0).toUpperCase() + part.slice(1);
  };

  return (
    <header className="h-11 border-b border-canvas-border bg-canvas-sidebar/60 backdrop-blur-sm px-4 flex items-center justify-between gap-4 shrink-0 select-none">
      {/* Left: Sidebar Toggle & Breadcrumb Context */}
      <div className="flex items-center gap-2.5 min-w-0">
        {/* Mobile Drawer Toggle (< 768px) */}
        <div className="md:hidden">
          <IconButton
            label="Open navigation menu"
            size="sm"
            icon={<Menu size={16} />}
            onClick={() => setMobileDrawerOpen(true)}
          />
        </div>

        {/* Desktop Sidebar Toggle (>= 768px) */}
        <div className="hidden md:block">
          <IconButton
            label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            shortcut="Ctrl+\"
            size="sm"
            icon={
              isSidebarCollapsed ? (
                <PanelLeft size={16} />
              ) : (
                <PanelLeftClose size={16} />
              )
            }
            onClick={toggleSidebar}
          />
        </div>

        <span className="h-3.5 w-[1px] bg-canvas-border shrink-0" aria-hidden="true" />

        {/* Breadcrumb Trail */}
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-text-secondary truncate">
          <Link
            to="/"
            className="hover:text-text-primary transition-colors duration-fast truncate"
          >
            Overview
          </Link>
          {pathParts.length > 0 && <span className="text-text-muted">/</span>}
          {pathParts.map((part, index) => {
            const isLast = index === pathParts.length - 1;
            const isDomainsRoot = part === 'domains' && pathParts.length > 1;
            const to = isDomainsRoot ? '/notes' : '/' + pathParts.slice(0, index + 1).join('/');
            return (
              <React.Fragment key={`${part}-${index}`}>
                {isLast ? (
                  <span className="font-medium text-text-primary truncate">
                    {formatBreadcrumb(part)}
                  </span>
                ) : (
                  <>
                    <Link
                      to={to}
                      className="hover:text-text-primary transition-colors duration-fast truncate"
                    >
                      {formatBreadcrumb(part)}
                    </Link>
                    <span className="text-text-muted">/</span>
                  </>
                )}
              </React.Fragment>
            );
          })}
        </nav>
      </div>

      {/* Right: Unified Global Quick Search Entry Point */}
      <div className="flex items-center gap-2 shrink-0">
        <button
          type="button"
          onClick={() => setCommandPaletteOpen(true)}
          aria-label="Global Quick Search (Ctrl+K)"
          className="flex items-center justify-between gap-3 h-7 px-2.5 text-xs text-text-secondary bg-canvas-surface hover:bg-canvas-elevated border border-canvas-border hover:border-canvas-borderHover rounded-md transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
        >
          <span className="flex items-center gap-1.5">
            <Search size={13} className="text-text-muted shrink-0" />
            <span className="hidden sm:inline">Quick Search...</span>
            <span className="sm:hidden">Search</span>
          </span>
          <kbd className="text-[10px] font-mono bg-canvas-app border border-canvas-border px-1.5 py-0.5 rounded text-text-muted leading-none">
            Ctrl+K
          </kbd>
        </button>
      </div>
    </header>
  );
};
