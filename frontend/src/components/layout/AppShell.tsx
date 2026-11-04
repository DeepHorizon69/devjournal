import React, { useEffect } from 'react';
import { Outlet, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { SidebarNav } from './SidebarNav';
import { TopBar } from './TopBar';
import { QuickSearchModal } from './QuickSearchModal';
import { NewNoteModal } from '../notes/NewNoteModal';
import { ToastContainer } from '../ui/Toast';
import { useUIStore } from '../../store/useUIStore';
import { KnowledgeDomain, NoteType } from '../../types';

const DOMAIN_MAP: Record<string, KnowledgeDomain> = {
  networking: 'Networking',
  linux: 'Linux',
  programming: 'Programming',
  iot: 'IoT',
  cybersecurity: 'Cybersecurity',
  homelab: 'Homelab',
  mathematics: 'Mathematics',
};

export const AppShell: React.FC = () => {
  const {
    toggleSidebar,
    setCommandPaletteOpen,
    openNewNoteModal,
    setMobileDrawerOpen,
  } = useUIStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  // Trigger NewNoteModal when ?new=true query param is present
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      const tpl = searchParams.get('template') || undefined;
      const type = (searchParams.get('type') as NoteType | null) || undefined;
      const domParam = searchParams.get('domain');
      const domain = domParam
        ? DOMAIN_MAP[domParam.toLowerCase()] || (domParam as KnowledgeDomain)
        : undefined;

      openNewNoteModal({ template: tpl, noteType: type, domain });

      const nextParams = new URLSearchParams(searchParams);
      nextParams.delete('new');
      nextParams.delete('template');
      nextParams.delete('type');
      nextParams.delete('domain');
      setSearchParams(nextParams, { replace: true });
    }
  }, [searchParams, setSearchParams, openNewNoteModal]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Toggle sidebar: Ctrl+\ or Cmd+\
      if ((e.ctrlKey || e.metaKey) && e.key === '\\') {
        e.preventDefault();
        toggleSidebar();
      }
      // Global Quick Search: Ctrl+K or Cmd+K
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (location.pathname === '/search') {
          setCommandPaletteOpen(false);
        } else {
          setCommandPaletteOpen(true);
        }
      }
      // Quick New Note: Alt+N
      if (e.altKey && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        openNewNoteModal();
      }
      // Close mobile drawer on Escape
      if (e.key === 'Escape') {
        setMobileDrawerOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    toggleSidebar,
    setCommandPaletteOpen,
    openNewNoteModal,
    setMobileDrawerOpen,
    navigate,
    location.pathname,
  ]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-canvas-app text-text-primary">
      <SidebarNav />
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto min-w-0 bg-canvas-app">
          <Outlet />
        </main>
      </div>
      <NewNoteModal />
      <QuickSearchModal />
      <ToastContainer />
    </div>
  );
};
