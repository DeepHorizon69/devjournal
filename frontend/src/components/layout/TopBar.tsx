import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { PanelLeftClose, PanelLeftOpen, Search } from 'lucide-react';
import { useUIStore } from '../../store/useUIStore';

export const TopBar: React.FC = () => {
  const { isSidebarCollapsed, toggleSidebar, setCommandPaletteOpen } = useUIStore();
  const location = useLocation();

  // Generate simple breadcrumbs from path
  const pathParts = location.pathname.split('/').filter(Boolean);

  const formatBreadcrumb = (part: string) => {
    if (part === 'notes') return 'All Notes';
    if (part === 'experiments') return 'Experiments';
    if (part === 'troubleshooting') return 'Troubleshooting';
    if (part === 'projects') return 'Projects';
    if (part === 'daily') return 'Daily Journal';
    if (part === 'settings') return 'Settings';
    if (part === 'search') return 'Search';
    if (part === 'domains') return 'Knowledge Domains';
    return part.charAt(0).toUpperCase() + part.slice(1);
  };

  return (
    <header className="h-12 border-b border-canvas-border bg-canvas-sidebar/40 backdrop-blur-sm px-4 flex items-center justify-between shrink-0 select-none">
      <div className="flex items-center gap-3">
        <button
          onClick={toggleSidebar}
          title={isSidebarCollapsed ? "Expand sidebar (Ctrl+\\)" : "Collapse sidebar (Ctrl+\\)"}
          className="p-1.5 text-text-secondary hover:text-text-primary hover:bg-canvas-surface rounded transition-colors"
        >
          {isSidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>

        {/* Breadcrumbs */}
        <nav className="flex items-center gap-1.5 text-xs text-text-secondary">
          <Link to="/" className="hover:text-text-primary transition-colors">
            Workspace
          </Link>
          {pathParts.length > 0 && <span className="text-text-muted">/</span>}
          {pathParts.map((part, index) => {
            const isLast = index === pathParts.length - 1;
            const to = '/' + pathParts.slice(0, index + 1).join('/');
            return (
              <React.Fragment key={to}>
                {isLast ? (
                  <span className="font-medium text-text-primary">
                    {formatBreadcrumb(part)}
                  </span>
                ) : (
                  <>
                    <Link to={to} className="hover:text-text-primary transition-colors">
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

      <div className="flex items-center gap-2">
        <button
          onClick={() => setCommandPaletteOpen(true)}
          className="flex items-center gap-2 px-2.5 py-1 text-xs text-text-secondary bg-canvas-surface hover:bg-canvas-elevated border border-canvas-border rounded-md transition-colors"
        >
          <Search size={14} className="text-text-muted" />
          <span>Quick Search...</span>
          <kbd className="text-[10px] bg-canvas-app border border-canvas-border px-1.5 py-0.5 rounded text-text-muted">
            Ctrl+K
          </kbd>
        </button>
      </div>
    </header>
  );
};
