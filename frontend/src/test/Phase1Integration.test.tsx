import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NoteRow } from '../components/notes/NoteRow';
import { renderHighlightedSnippet } from '../utils/highlight';
import {
  saveLocalDraft,
  loadLocalDraft,
  clearMemoryDraftCacheForTesting,
  LocalDraftRecord,
} from '../utils/draftStorage';
import { NoteSummary } from '../types';

describe('Phase 1 Frontend Integration & Safety Contracts', () => {
  beforeEach(() => {
    localStorage.clear();
    clearMemoryDraftCacheForTesting();
    vi.restoreAllMocks();
  });

  it('NoteRow omits status badge when status is null (General Note default) and shows badge when non-null', () => {
    const generalNote: NoteSummary = {
      id: '01HTESTGENERAL000000000001',
      title: 'Architecture General Note',
      slug: 'architecture-general-note',
      note_type: 'note',
      status: null,
      folder: '10-Notes',
      rel_path: '10-Notes/architecture-general-note.md',
      domains: ['Programming'],
      tags: ['architecture'],
      is_pinned: false,
      is_trashed: false,
      word_count: 10,
      reading_time_mins: 1,
      content_hash: 'sha256:0000',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      excerpt: 'General notes default to null status',
    };

    const { rerender } = render(
      <NoteRow note={generalNote} onSelect={() => {}} />
    );

    expect(screen.getByText('Architecture General Note')).toBeDefined();
    expect(screen.queryByText('draft')).toBeNull();
    expect(screen.queryByText('active')).toBeNull();

    // Rerender with active status
    rerender(
      <NoteRow
        note={{ ...generalNote, status: 'active' }}
        onSelect={() => {}}
      />
    );
    expect(screen.getByText('active')).toBeDefined();
  });

  it('renderHighlightedSnippet safely highlights matched segments and escapes literal <mark> and <script> tags', () => {
    const { container } = render(
      <div>
        {renderHighlightedSnippet('', [
          { text: 'Literal <mark>fake</mark> and <script>alert(1)</script> before ', highlight: false },
          { text: 'matched term', highlight: true },
        ])}
      </div>
    );

    // Only one real <mark> DOM node should exist (for 'matched term')
    const marks = container.querySelectorAll('mark');
    expect(marks.length).toBe(1);
    expect(marks[0].textContent).toBe('matched term');

    // No <script> element should exist in the DOM
    expect(container.querySelectorAll('script').length).toBe(0);
    expect(container.textContent).toContain('Literal <mark>fake</mark> and <script>alert(1)</script> before matched term');
  });

  it('saveLocalDraft never evicts another note persistent draft on QuotaExceededError and retains current draft in memory', () => {
    const otherNoteId = '01HOTHERNOTE00000000000001';
    const currentNoteId = '01HCURRENTNOTE000000000002';

    const otherDraft: LocalDraftRecord = {
      noteId: otherNoteId,
      title: 'Existing Persistent Draft',
      noteType: 'note',
      status: null,
      folder: '10-Notes',
      domains: ['Linux'],
      tags: ['keep-me'],
      isPinned: false,
      body: 'Important unsaved work on another note',
      baseContentHash: 'sha256:1111',
      updatedAt: new Date(Date.now() - 60000).toISOString(),
    };

    // Save the first note's draft normally into localStorage
    const firstSave = saveLocalDraft(otherNoteId, otherDraft);
    expect(firstSave.persistedToLocalStorage).toBe(true);
    expect(localStorage.getItem(`devjournal:unsaved-draft:${otherNoteId}`)).not.toBeNull();

    // Simulate QuotaExceededError on subsequent localStorage.setItem calls
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError', 'QuotaExceededError');
    });

    const currentDraft: LocalDraftRecord = {
      noteId: currentNoteId,
      title: 'Active Note Hitting Quota',
      noteType: 'experiment',
      status: 'active',
      folder: '30-Experiments',
      domains: ['Networking'],
      tags: ['quota-test'],
      isPinned: false,
      body: 'Large draft content kept in in-memory cache',
      baseContentHash: 'sha256:2222',
      updatedAt: new Date().toISOString(),
    };

    const secondSave = saveLocalDraft(currentNoteId, currentDraft);
    expect(secondSave.persistedToLocalStorage).toBe(false);
    expect(secondSave.warningMessage).toContain('Persistent browser storage is full');

    // Verify the other note's persistent draft in localStorage was NOT evicted!
    const rawOther = localStorage.getItem(`devjournal:unsaved-draft:${otherNoteId}`);
    expect(rawOther).not.toBeNull();
    expect(JSON.parse(rawOther!).title).toBe('Existing Persistent Draft');

    // Verify the current note's draft is still recoverable from in-memory cache across route changes
    const recoveredCurrent = loadLocalDraft(currentNoteId);
    expect(recoveredCurrent).not.toBeNull();
    expect(recoveredCurrent?.body).toBe('Large draft content kept in in-memory cache');
  });
});
