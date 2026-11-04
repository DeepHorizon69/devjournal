import { create } from 'zustand';

interface UIState {
  isSidebarCollapsed: boolean;
  editorViewMode: 'split' | 'edit' | 'preview';
  isCommandPaletteOpen: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setEditorViewMode: (mode: 'split' | 'edit' | 'preview') => void;
  setCommandPaletteOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  isSidebarCollapsed: false,
  editorViewMode: 'split',
  isCommandPaletteOpen: false,
  toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
  setSidebarCollapsed: (isSidebarCollapsed) => set({ isSidebarCollapsed }),
  setEditorViewMode: (editorViewMode) => set({ editorViewMode }),
  setCommandPaletteOpen: (isCommandPaletteOpen) => set({ isCommandPaletteOpen }),
}));
