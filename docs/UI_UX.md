# DevJournal — UI/UX Design System Specification

This document details the visual direction, design tokens, component inventory, navigation hierarchy, screen specifications, and interaction patterns for **DevJournal**.

---

## 1. Visual Direction & Design Philosophy

DevJournal is designed as a focused, high-density, calm engineering workspace combining the organization of **Obsidian**, the interaction polish of **Linear**, and the typography and readability of **Stripe Documentation**.

### 1.1 Core Design Tenets
1. **Developer-First Ergonomics**: Prioritizes keyboard navigation, clear visual hierarchy, and fast access over decorative flourishes.
2. **Zero Visual Noise**: No gradients, saturated card backgrounds, glassmorphism, or heavy drop shadows. Structure is defined by crisp `1px` subtle borders (`#1E293B`).
3. **Calm Graphite / Navy Palette**: Deep dark background (`#0B0F17`) prevents eye strain during prolonged technical writing. The subtle sky-blue accent (`#38BDF8`) is reserved for interactive focus, primary actions, and active navigation indicators.
4. **Documentation-Grade Reading Measure**: Reading prose is constrained to `68ch–75ch` (`max-w-[72ch]`) with a 1.7 line-height for optimal legibility.

---

## 2. Design Tokens & Styling Rules

### 2.1 Color Tokens
| Token | Hex / Value | Semantic Application |
|---|---|---|
| `--bg-app` (`canvas-app`) | `#0B0F17` | Main viewport canvas |
| `--bg-sidebar` (`canvas-sidebar`) | `#0E131F` | Navigation sidebar & compact topbar |
| `--bg-surface` (`canvas-surface`) | `#131B2E` | Default cards, panels, inputs, and table rows |
| `--bg-elevated` (`canvas-elevated`) | `#1A243B` | Interactive hover states, dropdowns, popovers, modals |
| `--border-subtle` (`canvas-border`) | `#1E293B` | Structural dividers & component borders |
| `--border-hover` (`canvas-borderHover`) | `#334155` | Hover state for interactive borders |
| `--text-primary` | `#F1F5F9` | Page headings, note titles, code syntax |
| `--text-secondary` | `#94A3B8` | Descriptions, inactive navigation items, metadata |
| `--text-muted` | `#64748B` | Timestamps, line numbers, keyboard shortcut badges |
| `--accent-primary` (`accent`) | `#38BDF8` | Primary button, active nav indicator, links |
| `--accent-hover` | `#0EA5E9` | Primary button hover |
| `--accent-subtle` | `rgba(56, 189, 248, 0.10)` | Active navigation background tint |
| `--status-success` | `#34D399` | Emerald status indicator (`resolved`, `completed`, `online`) |
| `--status-warning` | `#FBBF24` | Amber status indicator (`active`, `investigating`, `unsaved`) |
| `--status-danger` | `#F87171` | Rose status indicator (`error`, `failed`, `conflict`, `delete`) |

### 2.2 Spacing System
- **Base Unit**: **4px** (`0.25rem`) is the standard spacing increment (`4px`, `8px`, `12px`, `16px`, `20px`, `24px`, `32px`).
- **Micro-Spacing Allowance**: **6px** (`0.375rem`) is permitted strictly for compact micro-spacing inside high-density controls (e.g. icon-to-label gaps inside badges, compact 30px nav items, and 28px buttons).

### 2.3 Typography Scale
- **UI & Headings**: Inter (`font-sans`)
  - Page Titles: `20px–24px` (`text-xl` to `text-2xl`), font-semibold, letter-spacing `-0.015em`.
  - Section Headings: `14px` (`text-sm`), font-semibold, tracking tight.
  - Body & Table Cells: `13px` (`text-[13px]`), font-normal.
  - Metadata & Badges: `11px–12px` (`text-xs` / `text-[11px]`), font-medium.
- **Code & Editor**: JetBrains Mono (`font-mono`)
  - Editor & Syntax: `14px`, line-height `1.6`.
  - Inline Code: `0.875em`, padded `0.125rem 0.375rem` with `#131B2E` background.

### 2.4 Motion & Transitions
- Simple Hover & Focus: `140ms ease-out`.
- Popover & Modal Reveal: `160ms cubic-bezier(0.16, 1, 0.3, 1)`.
- Sidebar Expand/Collapse: `200ms ease-in-out`.
- Full support for `@media (prefers-reduced-motion: reduce)` which zeroes animations.

---

## 3. Information Architecture & Navigation Hierarchy

The left navigation sidebar presents an orthogonal separation between **content types** and **subject matter**:

```text
[DevJournal Logo]  Local Workspace
[+ New Note        Alt+N]

WORKSPACE
  Overview
  All Notes
  Experiments
  Troubleshooting
  Projects
  Daily Journal

KNOWLEDGE DOMAINS
  Networking
  Linux
  Programming
  IoT
  Cybersecurity
  Homelab
  Mathematics

Settings
Vault: Online  v0.1.0
```

### 3.1 Workspace Navigation (Workflow Structure)
- Represents the **purpose or workflow type** of a note.
- Determines the note's single canonical `note_type` and default vault subfolder (`10-Notes`, `20-Projects`, `30-Experiments`, `40-Troubleshooting`, `90-Daily`).

### 3.2 Knowledge Domains (Subject Matter Classification)
- Represents the **engineering domain**.
- Stored as a multi-valued list in frontmatter (`domains: ["Linux", "Networking"]`) and indexed in the `note_domains` junction table.
- **Zero File Duplication**: A note tagged with both `Linux` and `Networking` appears under both domain views and its workspace view, referencing the exact same underlying file.

---

## 4. Reusable Component Inventory (20 Primitives)

All components are located in `frontend/src/components/ui/` and `notes/`:

1. **`Button`**: Primary (sky-blue), secondary (surface outline), surface (elevated), ghost, and danger variants across `xs`, `sm`, `md`, `lg` sizes with loading spinners.
2. **`IconButton`**: Square icon button with accessible `aria-label` and built-in tooltip support.
3. **`Input`**: Standard text input with floating label, error text, and focus-visible ring.
4. **`SearchInput`**: Specialized search field with leading magnifying glass, clear button, and shortcut badge.
5. **`Select`**: Styled compact select dropdown with custom chevron indicator.
6. **`Dropdown`**: Floating menu for actions, sorting, and export options.
7. **`Popover`**: Anchored floating panel for domain multi-select and filter facets.
8. **`Modal`**: Keyboard-accessible dialog (`Esc` dismiss, backdrop click) for New Note creation and confirmations.
9. **`Tooltip`**: Portaled to `document.body` with fixed positioning, escaping overflow clipping with viewport edge clamping.
10. **`Badge`**: Compact metadata pill with subtle semantic dot indicators (`success`, `warning`, `danger`, `domain`).
11. **`Card`**: Standardized `#131B2E` container with `#1E293B` border and optional hover effects.
12. **`StatCard`**: Metric card displaying mono count, semantic status dot, and click-through navigation.
13. **`NavigationItem`**: 30px height sidebar row with left accent indicator bar, count pill, and collapsed icon mode.
14. **`NoteRow`**: High-density list item showing pin button, title, excerpt, type pill, domain tags, and relative timestamp.
15. **`FilterBar`**: Toolbar with keyword search input, type/domain/status/tag/folder select dropdowns, and sort selector.
16. **`EmptyState`**: Compact, contextual empty state without oversized dashed containers.
17. **`Skeleton`**: Subtle animated pulse placeholders for loading states.
18. **`Toast`**: Non-blocking bottom-right notification stack for save and backup feedback.
19. **`StatusIndicator`**: Distinct save status pill: `Saved`, `Unsaved changes`, `Saving...`, `Save failed`, `Conflict with server`.
20. **`SectionHeader`**: Clean section title with optional subtitle and right-aligned action slot.

---

## 5. Screen Specifications

### 5.1 Overview Dashboard (`/`)
- **Header**: `Engineering Overview` title, contextual subtitle, and primary `+ New Note` action (duplicate `Today's Journal` header button removed).
- **Stat Cards**: 4-column strip (`Total Notes`, `Experiments`, `Troubleshooting`, `Projects`) displaying real SQLite counts.
- **Quick Capture Templates**: 5 compact interactive cards (`General Note`, `Experiment`, `Troubleshooting`, `Project`, `Today's Journal`).
- **Continue Reading**: List of the last 5 opened notes (`last_opened_at DESC`).
- **Recently Updated**: List of the last 5 edited notes (`updated_at DESC`).
- **Knowledge Domains Overview**: Responsive 7-column card grid displaying real note counts per domain with direct navigation links.

### 5.2 Flagship Markdown Editor (`/notes/:noteId`)
- **Compact Header (`40px`)**: Breadcrumbs, save status indicator, view mode switcher (`Edit` | `Split` | `Preview`), and quick export/delete actions.
- **Metadata Bar**: Inline editable title, note type selector, status selector, multi-domain popover, and tag chips.
- **Split Workspace**: Resizable panes via `react-resizable-panels`. Left pane hosts CodeMirror 6 with custom graphite theme; right pane hosts live documentation preview debounced with a **150ms timer** (`useDebouncedValue`).
- **Conflict Handling**: If another process edits the note, saving triggers an `HTTP 409` banner with options to **Reload Server Version** or **Force Overwrite**.

### 5.3 Global Search & Command Palette (`Ctrl+K`)
- Centered modal displaying an instant-search input.
- Real-time BM25 matching against title, headings, body, tags, and domains.
- Highlighted matched terms with `<mark>` tags.
- Full keyboard navigation (`↑`, `↓`, `Enter`, `Esc`).

### 5.4 Settings Page (`/settings`)
- **Vault & Storage**: Vault path, active note count, and one-click **Rebuild Search Index**.
- **Data Management**: Single-file Markdown import and full vault `.zip` backup.
- **Trash Manager**: Soft-deleted note list with **Restore** and **Delete Permanently**.
- **Editor Preferences**: Persisted configuration for default view mode, font size (12–20px), word wrap, and autosave delay.
