import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect } from 'vitest';
import { SidebarNav } from '../components/layout/SidebarNav';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  );
}

describe('SidebarNav component', () => {
  it('renders application branding and workspace indicator', () => {
    renderWithProviders(<SidebarNav />);
    expect(screen.getByText('DevJournal')).toBeInTheDocument();
    expect(screen.getByText('Local Workspace')).toBeInTheDocument();
  });

  it('renders all approved Workspace navigation items', () => {
    renderWithProviders(<SidebarNav />);
    const workspaceItems = [
      'Overview',
      'All Notes',
      'Experiments',
      'Troubleshooting',
      'Projects',
      'Daily Journal',
    ];
    workspaceItems.forEach((item) => {
      expect(screen.getByText(item)).toBeInTheDocument();
    });
  });

  it('renders all 7 Knowledge Domains', () => {
    renderWithProviders(<SidebarNav />);
    const domains = [
      'Networking',
      'Linux',
      'Programming',
      'IoT',
      'Cybersecurity',
      'Homelab',
      'Mathematics',
    ];
    domains.forEach((domain) => {
      expect(screen.getByText(domain)).toBeInTheDocument();
    });
  });

  it('renders the Settings link', () => {
    renderWithProviders(<SidebarNav />);
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });
});
