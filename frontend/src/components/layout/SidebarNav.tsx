import React from 'react';
import { NavLink, Link, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  FlaskConical,
  Wrench,
  FolderGit2,
  Calendar,
  Network,
  Terminal,
  Code2,
  Cpu,
  ShieldCheck,
  Server,
  Sigma,
  Settings,
  Plus,
  Search,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useUIStore } from '../../store/useUIStore';
import { api } from '../../api/client';
import { Button } from '../ui/Button';

export const SidebarNav: React.FC = () => {
  const { isSidebarCollapsed, setCommandPaletteOpen } = useUIStore();
  const navigate = useNavigate();

  // Query system health
  const { data: health, isError } = useQuery({
    queryKey: ['system-health'],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  });

  // Query taxonomy counts
  const { data: taxonomy } = useQuery({
    queryKey: ['taxonomy'],
    queryFn: api.getTaxonomy,
    refetchInterval: 15000,
  });

  const workspaceNav = [
    { name: 'Overview', to: '/', icon: LayoutDashboard, count: undefined },
    { name: 'All Notes', to: '/notes', icon: FileText, count: taxonomy?.total_active },
    { name: 'Experiments', to: '/experiments', icon: FlaskConical, count: taxonomy?.types?.['experiment'] },
    { name: 'Troubleshooting', to: '/troubleshooting', icon: Wrench, count: taxonomy?.types?.['troubleshooting'] },
    { name: 'Projects', to: '/projects', icon: FolderGit2, count: taxonomy?.types?.['project'] },
    { name: 'Daily Journal', to: '/daily', icon: Calendar, count: taxonomy?.types?.['daily'] },
  ];

  const knowledgeDomains = [
    { name: 'Networking', to: '/domains/networking', icon: Network, count: taxonomy?.domains?.['Networking'] },
    { name: 'Linux', to: '/domains/linux', icon: Terminal, count: taxonomy?.domains?.['Linux'] },
    { name: 'Programming', to: '/domains/programming', icon: Code2, count: taxonomy?.domains?.['Programming'] },
    { name: 'IoT', to: '/domains/iot', icon: Cpu, count: taxonomy?.domains?.['IoT'] },
    { name: 'Cybersecurity', to: '/domains/cybersecurity', icon: ShieldCheck, count: taxonomy?.domains?.['Cybersecurity'] },
    { name: 'Homelab', to: '/domains/homelab', icon: Server, count: taxonomy?.domains?.['Homelab'] },
    { name: 'Mathematics', to: '/domains/mathematics', icon: Sigma, count: taxonomy?.domains?.['Mathematics'] },
  ];

  return (
    <aside
      className={`h-screen border-r border-canvas-border bg-canvas-sidebar flex flex-col shrink-0 transition-all duration-200 select-none ${
        isSidebarCollapsed ? 'w-0 -ml-64 overflow-hidden border-r-0' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="p-4 border-b border-canvas-border flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center text-accent font-bold text-sm tracking-wider shadow-sm">
            DJ
          </div>
          <div>
            <h1 className="text-sm font-bold text-text-primary tracking-tight">DevJournal</h1>
            <p className="text-[11px] text-text-muted">Local Workspace</p>
          </div>
        </Link>
      </div>

      {/* Primary Actions */}
      <div className="p-3 border-b border-canvas-border/50 flex flex-col gap-2">
        <Button
          variant="primary"
          size="sm"
          className="w-full justify-center"
          icon={<Plus size={16} />}
          onClick={() => navigate('/notes?new=true')}
        >
          New Note
        </Button>
        <button
          onClick={() => setCommandPaletteOpen(true)}
          className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-text-secondary bg-canvas-surface hover:bg-canvas-elevated border border-canvas-border rounded-md transition-colors"
        >
          <span className="flex items-center gap-2">
            <Search size={14} className="text-text-muted" />
            <span>Search</span>
          </span>
          <kbd className="text-[10px] text-text-muted bg-canvas-app px-1.5 py-0.5 rounded border border-canvas-border">
            Ctrl+K
          </kbd>
        </button>
      </div>

      {/* Nav Scroll Area */}
      <div className="flex-1 overflow-y-auto px-2 py-3 space-y-6">
        {/* Workspace Navigation */}
        <div>
          <div className="px-2 pb-1.5 text-[11px] font-semibold text-text-muted tracking-wider uppercase">
            Workspace
          </div>
          <nav className="space-y-0.5">
            {workspaceNav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-accent/15 text-accent border border-accent/25'
                      : 'text-text-secondary hover:text-text-primary hover:bg-canvas-surface'
                  }`
                }
              >
                <div className="flex items-center gap-2.5 truncate">
                  <item.icon size={16} className="shrink-0" />
                  <span className="truncate">{item.name}</span>
                </div>
                {item.count !== undefined && item.count > 0 && (
                  <span className="text-[10px] font-mono text-text-muted px-1.5 py-0.5 rounded bg-canvas-app border border-canvas-border">
                    {item.count}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Knowledge Domains */}
        <div>
          <div className="px-2 pb-1.5 text-[11px] font-semibold text-text-muted tracking-wider uppercase">
            Knowledge Domains
          </div>
          <nav className="space-y-0.5">
            {knowledgeDomains.map((domain) => (
              <NavLink
                key={domain.to}
                to={domain.to}
                className={({ isActive }) =>
                  `flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-accent/15 text-accent border border-accent/25'
                      : 'text-text-secondary hover:text-text-primary hover:bg-canvas-surface'
                  }`
                }
              >
                <div className="flex items-center gap-2.5 truncate">
                  <domain.icon size={16} className="shrink-0" />
                  <span className="truncate">{domain.name}</span>
                </div>
                {domain.count !== undefined && domain.count > 0 && (
                  <span className="text-[10px] font-mono text-text-muted px-1.5 py-0.5 rounded bg-canvas-app border border-canvas-border">
                    {domain.count}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>

      {/* Footer Navigation & Health Status */}
      <div className="p-3 border-t border-canvas-border space-y-2 shrink-0">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
              isActive
                ? 'bg-accent/15 text-accent border border-accent/25'
                : 'text-text-secondary hover:text-text-primary hover:bg-canvas-surface'
            }`
          }
        >
          <Settings size={16} />
          <span>Settings</span>
        </NavLink>

        {/* Health Status Pill */}
        <div className="pt-1 px-2.5 flex items-center justify-between text-[11px] text-text-muted">
          <span className="flex items-center gap-1.5">
            {isError ? (
              <>
                <AlertTriangle size={12} className="text-rose-400" />
                <span className="text-rose-400">Vault: Offline</span>
              </>
            ) : health?.status === 'ok' ? (
              <>
                <CheckCircle2 size={12} className="text-emerald-400" />
                <span className="text-text-secondary">Vault: Online</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                <span>Connecting...</span>
              </>
            )}
          </span>
          <span className="font-mono text-[10px]">v0.1.0</span>
        </div>
      </div>
    </aside>
  );
};
