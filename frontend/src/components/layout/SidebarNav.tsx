import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
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
  CheckCircle2,
  AlertTriangle,
  X,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useQuery } from '@tanstack/react-query';
import { useUIStore } from '../../store/useUIStore';
import { api } from '../../api/client';
import { NavigationItem } from '../ui/NavigationItem';
import { Button } from '../ui/Button';
import { IconButton } from '../ui/IconButton';
import { Tooltip } from '../ui/Tooltip';

export const SidebarNav: React.FC = () => {
  const {
    isSidebarCollapsed,
    isMobileDrawerOpen,
    setMobileDrawerOpen,
    openNewNoteModal,
  } = useUIStore();
  const navigate = useNavigate();

  const { data: health, isError } = useQuery({
    queryKey: ['system-health'],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  });

  const { data: taxonomy } = useQuery({
    queryKey: ['taxonomy'],
    queryFn: api.getTaxonomy,
    refetchInterval: 15000,
  });

  const workspaceNav = [
    { name: 'Overview', to: '/', icon: LayoutDashboard, count: undefined, end: true },
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

  const handleNewNote = () => {
    setMobileDrawerOpen(false);
    openNewNoteModal();
    navigate('/notes?new=true');
  };

  const handleNavClick = () => {
    if (isMobileDrawerOpen) {
      setMobileDrawerOpen(false);
    }
  };

  const vaultStatusLabel = isError
    ? 'Vault: Offline'
    : health?.status === 'ok'
    ? 'Vault: Online'
    : 'Connecting...';

  const renderSidebarContent = (collapsed: boolean, isMobile = false) => (
    <div className="flex flex-col h-full w-full select-none overflow-hidden">
      {/* Application Identity Header (44px aligned with TopBar) */}
      <div
        className={clsx(
          'h-11 border-b border-canvas-border flex items-center shrink-0 overflow-hidden',
          collapsed ? 'justify-center px-0' : 'justify-between px-3'
        )}
      >
        {collapsed ? (
          <Tooltip content="DevJournal — Local Workspace" side="right">
            <Link
              to="/"
              aria-label="DevJournal Local Workspace"
              onClick={handleNavClick}
              className="w-8 h-8 rounded-md bg-accent/15 border border-accent/30 flex items-center justify-center text-accent font-mono font-semibold text-xs shrink-0 focus-visible:rounded"
            >
              DJ
            </Link>
          </Tooltip>
        ) : (
          <Link
            to="/"
            onClick={handleNavClick}
            className="flex items-center gap-2.5 min-w-0 focus-visible:rounded"
          >
            <div className="w-7 h-7 rounded-md bg-accent/15 border border-accent/30 flex items-center justify-center text-accent font-mono font-semibold text-xs shrink-0">
              DJ
            </div>
            <div className="min-w-0">
              <h1 className="text-[13px] font-semibold text-text-primary tracking-tight leading-none truncate">
                DevJournal
              </h1>
              <p className="text-[11px] text-text-muted leading-none mt-1 truncate">
                Local Workspace
              </p>
            </div>
          </Link>
        )}

        {isMobile && (
          <IconButton
            label="Close navigation drawer"
            size="sm"
            icon={<X size={16} />}
            onClick={() => setMobileDrawerOpen(false)}
          />
        )}
      </div>

      {/* Primary Action: New Note */}
      <div
        className={clsx(
          'py-2.5 border-b border-canvas-border/60 shrink-0 overflow-hidden',
          collapsed ? 'flex justify-center px-0' : 'px-2.5'
        )}
      >
        {collapsed ? (
          <IconButton
            label="New Note"
            shortcut="Alt+N"
            tooltipSide="right"
            variant="surface"
            size="md"
            className="w-9 h-8"
            icon={<Plus size={16} className="text-accent" />}
            onClick={handleNewNote}
          />
        ) : (
          <Button
            variant="surface"
            size="sm"
            className="w-full justify-between px-2.5"
            icon={<Plus size={15} className="text-accent" />}
            trailingIcon={
              <kbd className="text-[10px] font-mono text-text-muted bg-canvas-app px-1 py-0.5 rounded border border-canvas-border">
                Alt+N
              </kbd>
            }
            onClick={handleNewNote}
          >
            New Note
          </Button>
        )}
      </div>

      {/* Scrollable Navigation Groups */}
      <div
        className={clsx(
          'flex-1 overflow-y-auto overflow-x-hidden py-2.5',
          collapsed ? 'px-0 space-y-2' : 'px-2 space-y-4'
        )}
      >
        {/* Workspace Group */}
        <div>
          {!collapsed && (
            <div className="px-2 pb-1 text-[11px] font-medium text-text-muted tracking-wide truncate">
              Workspace
            </div>
          )}
          <nav aria-label="Workspace navigation" className="space-y-0.5">
            {workspaceNav.map((item) => (
              <NavigationItem
                key={item.to}
                name={item.name}
                to={item.to}
                icon={item.icon}
                count={item.count}
                end={item.end}
                collapsed={collapsed}
                onClick={handleNavClick}
              />
            ))}
          </nav>
        </div>

        {collapsed && (
          <div
            className="mx-auto w-6 h-[1px] bg-canvas-border"
            role="separator"
            aria-hidden="true"
          />
        )}

        {/* Knowledge Domains Group */}
        <div>
          {!collapsed && (
            <div className="px-2 pb-1 text-[11px] font-medium text-text-muted tracking-wide truncate">
              Knowledge Domains
            </div>
          )}
          <nav aria-label="Knowledge domains" className="space-y-0.5">
            {knowledgeDomains.map((domain) => (
              <NavigationItem
                key={domain.to}
                name={domain.name}
                to={domain.to}
                icon={domain.icon}
                count={domain.count}
                collapsed={collapsed}
                onClick={handleNavClick}
              />
            ))}
          </nav>
        </div>
      </div>

      {/* Anchored Footer: Settings & Vault Status */}
      <div
        className={clsx(
          'py-2 border-t border-canvas-border space-y-1.5 shrink-0 bg-canvas-sidebar overflow-hidden',
          collapsed ? 'px-0' : 'px-2'
        )}
      >
        <NavigationItem
          name="Settings"
          to="/settings"
          icon={Settings}
          collapsed={collapsed}
          onClick={handleNavClick}
        />

        {/* Vault Status Row */}
        {collapsed ? (
          <div className="flex justify-center w-full">
            <Tooltip content={vaultStatusLabel} side="right">
              <div
                tabIndex={0}
                aria-label={vaultStatusLabel}
                className="flex items-center justify-center h-7 w-9 rounded text-text-muted hover:bg-canvas-surface/60 transition-colors focus-visible:rounded"
              >
                {isError ? (
                  <AlertTriangle size={14} className="text-status-danger" />
                ) : health?.status === 'ok' ? (
                  <CheckCircle2 size={14} className="text-status-success" />
                ) : (
                  <span className="w-2 h-2 rounded-full bg-status-warning animate-pulse" />
                )}
              </div>
            </Tooltip>
          </div>
        ) : (
          <div className="px-2.5 py-1 flex items-center justify-between text-[11px] text-text-muted truncate">
            <span className="flex items-center gap-1.5 truncate">
              {isError ? (
                <>
                  <AlertTriangle size={12} className="text-status-danger shrink-0" />
                  <span className="text-status-danger truncate">Vault: Offline</span>
                </>
              ) : health?.status === 'ok' ? (
                <>
                  <CheckCircle2 size={12} className="text-status-success shrink-0" />
                  <span className="text-text-secondary truncate">Vault: Online</span>
                </>
              ) : (
                <>
                  <span className="w-2 h-2 rounded-full bg-status-warning animate-pulse shrink-0" />
                  <span className="truncate">Connecting...</span>
                </>
              )}
            </span>
            <span className="font-mono text-[10px] shrink-0">v0.1.0</span>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar (Expanded 240px or Collapsed 60px Icon Rail) */}
      <aside
        aria-label="Primary Sidebar"
        className={clsx(
          'hidden md:flex flex-col h-screen bg-canvas-sidebar border-r border-canvas-border shrink-0 overflow-hidden transition-[width] duration-panel ease-in-out',
          isSidebarCollapsed ? 'w-[60px]' : 'w-60'
        )}
      >
        {renderSidebarContent(isSidebarCollapsed, false)}
      </aside>

      {/* Mobile & Tablet Responsive Drawer (< 768px) */}
      {isMobileDrawerOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden" role="dialog" aria-modal="true">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-[1px]"
            onClick={() => setMobileDrawerOpen(false)}
          />
          <aside className="relative z-10 flex flex-col w-60 max-w-[80vw] h-full bg-canvas-sidebar border-r border-canvas-border shadow-2xl overflow-hidden">
            {renderSidebarContent(false, true)}
          </aside>
        </div>
      )}
    </>
  );
};
