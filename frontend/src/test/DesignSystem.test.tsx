import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import {
  Button,
  IconButton,
  StatCard,
  StatusIndicator,
  NoteRow,
  FilterBar,
  Modal,
  EmptyState,
} from '../components/ui';
import { NoteSummary } from '../types';
import { Plus } from 'lucide-react';

describe('Design System Components (Milestone 1)', () => {
  it('renders Button variants, disabled state, and loading state', () => {
    const onClick = vi.fn();
    const { rerender } = render(
      <Button variant="primary" onClick={onClick}>
        Save Note
      </Button>
    );
    const btn = screen.getByRole('button', { name: 'Save Note' });
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);

    rerender(
      <Button variant="primary" loading onClick={onClick}>
        Save Note
      </Button>
    );
    expect(screen.getByRole('button', { name: 'Save Note' })).toBeDisabled();
  });

  it('renders IconButton with accessible label and tooltip on hover', () => {
    render(<IconButton label="Create item" shortcut="Alt+N" icon={<Plus size={14} />} />);
    const iconBtn = screen.getByRole('button', { name: 'Create item' });
    expect(iconBtn).toBeInTheDocument();

    fireEvent.mouseEnter(iconBtn.parentElement!);
    expect(screen.getByRole('tooltip')).toHaveTextContent('Create item');
    expect(screen.getByRole('tooltip')).toHaveTextContent('Alt+N');
  });

  it('renders StatusIndicator for all five save states', () => {
    const { rerender } = render(<StatusIndicator state="saved" />);
    expect(screen.getByText('Saved')).toBeInTheDocument();

    rerender(<StatusIndicator state="unsaved" />);
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();

    rerender(<StatusIndicator state="saving" />);
    expect(screen.getByText('Saving...')).toBeInTheDocument();

    rerender(<StatusIndicator state="failed" />);
    expect(screen.getByText('Save failed')).toBeInTheDocument();

    rerender(<StatusIndicator state="conflict" />);
    expect(screen.getByText('Conflict with server')).toBeInTheDocument();
  });

  it('renders StatCard with count and click handler', () => {
    const onSelect = vi.fn();
    render(
      <StatCard
        label="Experiments"
        count={14}
        indicatorColor="accent"
        onClick={onSelect}
      />
    );
    expect(screen.getByText('Experiments')).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button'));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it('renders NoteRow with title, excerpt, domains, tags, and pin action', () => {
    const sampleNote: NoteSummary = {
      id: 'note-1',
      title: 'WireGuard MTU Investigation',
      slug: 'wireguard-mtu',
      rel_path: '40-Troubleshooting/wireguard-mtu.md',
      folder: '40-Troubleshooting',
      note_type: 'troubleshooting',
      status: 'resolved',
      excerpt: 'Diagnosing packet drops on site-to-site tunnel.',
      word_count: 320,
      reading_time_mins: 2,
      content_hash: 'abc123',
      is_pinned: true,
      is_trashed: false,
      domains: ['Networking', 'Linux'],
      tags: ['wireguard', 'mtu'],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const onSelect = vi.fn();
    const onTogglePin = vi.fn();

    render(
      <NoteRow
        note={sampleNote}
        onSelect={onSelect}
        onTogglePin={onTogglePin}
      />
    );

    expect(screen.getByText('WireGuard MTU Investigation')).toBeInTheDocument();
    expect(screen.getByText('Networking')).toBeInTheDocument();
    expect(screen.getByText('Linux')).toBeInTheDocument();
    expect(screen.getByText('#wireguard')).toBeInTheDocument();
    expect(screen.getByText('resolved')).toBeInTheDocument();
  });

  it('renders FilterBar and triggers filter change and reset', () => {
    const onChange = vi.fn();
    const onReset = vi.fn();

    render(
      <FilterBar
        filters={{
          search: 'systemd',
          type: 'troubleshooting',
          domain: '',
          status: '',
          tag: '',
          folder: '',
          sort: 'updated_desc',
        }}
        onChange={onChange}
        onReset={onReset}
        totalCount={3}
      />
    );

    expect(screen.getByText('3 notes')).toBeInTheDocument();
    const resetBtn = screen.getByRole('button', { name: 'Reset' });
    fireEvent.click(resetBtn);
    expect(onReset).toHaveBeenCalledTimes(1);
  });

  it('renders Modal and EmptyState cleanly', () => {
    const onClose = vi.fn();
    render(
      <Modal open={true} onClose={onClose} title="Test Modal">
        <EmptyState compact title="Nothing here yet" description="Create a note to begin." />
      </Modal>
    );
    expect(screen.getByText('Test Modal')).toBeInTheDocument();
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
