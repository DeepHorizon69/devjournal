import { create } from 'zustand';
import { KnowledgeDomain, NoteType } from '../types';

export interface NewNoteDefaults {
  template?: string;
  noteType?: NoteType;
  domain?: KnowledgeDomain;
}

interface UIState {
  isSidebarCollapsed: boolean;
  isMobileDrawerOpen: boolean;
  editorViewMode: 'split' | 'edit' | 'preview';
  isCommandPaletteOpen: boolean;
  isNewNoteModalOpen: boolean;
  newNoteDefaults: NewNoteDefaults;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setMobileDrawerOpen: (open: boolean) => void;
  setEditorViewMode: (mode: 'split' | 'edit' | 'preview') => void;
  setCommandPaletteOpen: (open: boolean) => void;
  openNewNoteModal: (defaults?: NewNoteDefaults) => void;
  closeNewNoteModal: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  isSidebarCollapsed: false,
  isMobileDrawerOpen: false,
  editorViewMode: 'split',
  isCommandPaletteOpen: false,
  isNewNoteModalOpen: false,
  newNoteDefaults: {},
  toggleSidebar: () =>
    set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
  setSidebarCollapsed: (isSidebarCollapsed) => set({ isSidebarCollapsed }),
  setMobileDrawerOpen: (isMobileDrawerOpen) => set({ isMobileDrawerOpen }),
  setEditorViewMode: (editorViewMode) => set({ editorViewMode }),
  setCommandPaletteOpen: (isCommandPaletteOpen) => set({ isCommandPaletteOpen }),
  openNewNoteModal: (defaults = {}) =>
    set({ isNewNoteModalOpen: true, newNoteDefaults: defaults }),
  closeNewNoteModal: () =>
    set({ isNewNoteModalOpen: false, newNoteDefaults: {} }),
}));
