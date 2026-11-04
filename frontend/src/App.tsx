import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from './components/layout/AppShell';
import { OverviewPage } from './pages/OverviewPage';
import { NotesListPage } from './pages/NotesListPage';
import { DailyJournalPage } from './pages/DailyJournalPage';
import { NoteEditorPage } from './pages/NoteEditorPage';
import { SearchPage } from './pages/SearchPage';
import { SettingsPage } from './pages/SettingsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="notes" element={<NotesListPage />} />
            <Route path="experiments" element={<NotesListPage fixedType="experiment" />} />
            <Route path="troubleshooting" element={<NotesListPage fixedType="troubleshooting" />} />
            <Route path="projects" element={<NotesListPage fixedType="project" />} />
            <Route path="daily" element={<DailyJournalPage />} />
            <Route path="domains/:domainSlug" element={<NotesListPage />} />
            <Route path="notes/:noteId" element={<NoteEditorPage />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
