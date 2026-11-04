import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, beforeEach } from 'vitest';
import { SidebarNav } from '../components/layout/SidebarNav';
import { TopBar } from '../components/layout/TopBar';
import { useUIStore } from '../store/useUIStore';

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

describe('Application Shell — SidebarNav & TopBar (Milestone 1)', () => {
  beforeEach(() => {
    useUIStore.setState({
      isSidebarCollapsed: false,
      isMobileDrawerOpen: false,
      isCommandPaletteOpen: false,
    });
  });

  it('renders application branding and workspace indicator when expanded', () => {
    renderWithProviders(<SidebarNav />);
    expect(screen.getByText('DevJournal')).toBeInTheDocument();
    expect(screen.getByText('Local Workspace')).toBeInTheDocument();
  });

  it('renders all 6 approved Workspace navigation items', () => {
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

  it('renders the Settings link and avoids duplicate Search button in Sidebar', () => {
    renderWithProviders(<SidebarNav />);
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.queryByText('Quick Search...')).not.toBeInTheDocument();
  });

  it('provides a single unified Quick Search trigger and sidebar toggle with tooltip in TopBar', () => {
    renderWithProviders(<TopBar />);
    const searchTrigger = screen.getByLabelText('Global Quick Search (Ctrl+K)');
    expect(searchTrigger).toBeInTheDocument();

    const collapseBtn = screen.getByLabelText('Collapse sidebar');
    fireEvent.mouseEnter(collapseBtn.parentElement!);
    expect(screen.getByRole('tooltip')).toHaveTextContent('Collapse sidebar');

    fireEvent.click(collapseBtn);
    expect(useUIStore.getState().isSidebarCollapsed).toBe(true);
    expect(screen.getByLabelText('Expand sidebar')).toBeInTheDocument();
  });

  it('completely hides text labels and section headings when collapsed while portaling tooltips on hover', () => {
    useUIStore.setState({ isSidebarCollapsed: true });
    renderWithProviders(<SidebarNav />);

    // Visible section headings and text labels must not be rendered in the collapsed rail
    expect(screen.queryByText('Workspace')).not.toBeInTheDocument();
    expect(screen.queryByText('Knowledge Domains')).not.toBeInTheDocument();
    expect(screen.queryByText('Troubleshooting')).not.toBeInTheDocument();

    // Links remain accessible by aria-label
    const networkingLink = screen.getByRole('link', { name: 'Networking' });
    expect(networkingLink).toBeInTheDocument();

    // Hovering displays the portaled tooltip in document.body
    fireEvent.mouseEnter(networkingLink.parentElement!);
    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveTextContent('Networking');
    expect(tooltip.parentElement).toBe(document.body);
  });

  it('supports responsive mobile drawer open and close behavior', () => {
    useUIStore.setState({ isMobileDrawerOpen: true });
    renderWithProviders(<SidebarNav />);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();

    const closeBtn = screen.getByLabelText('Close navigation drawer');
    fireEvent.click(closeBtn);
    expect(useUIStore.getState().isMobileDrawerOpen).toBe(false);
  });
});
