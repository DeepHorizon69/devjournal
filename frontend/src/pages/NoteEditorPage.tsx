import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Save, Split, Eye, Edit3 } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { useUIStore } from '../store/useUIStore';

export const NoteEditorPage: React.FC = () => {
  const { noteId } = useParams<{ noteId: string }>();
  const navigate = useNavigate();
  const { editorViewMode, setEditorViewMode } = useUIStore();

  return (
    <div className="flex flex-col h-full bg-canvas-app">
      {/* Top action toolbar */}
      <div className="h-12 border-b border-canvas-border px-4 flex items-center justify-between shrink-0 bg-canvas-sidebar/40">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            icon={<ArrowLeft size={16} />}
            onClick={() => navigate(-1)}
          >
            Back
          </Button>
          <span className="text-xs text-text-muted">/</span>
          <span className="text-xs font-mono text-text-secondary">Note ID: {noteId || 'New'}</span>
          <Badge variant="accent" size="sm">Saved</Badge>
        </div>

        <div className="flex items-center gap-2">
          {/* Mode Switcher */}
          <div className="flex items-center bg-canvas-surface border border-canvas-border rounded-md p-0.5">
            <button
              onClick={() => setEditorViewMode('edit')}
              className={`px-2 py-1 text-xs rounded transition-colors flex items-center gap-1.5 ${
                editorViewMode === 'edit' ? 'bg-canvas-elevated text-text-primary' : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <Edit3 size={13} />
              <span>Edit</span>
            </button>
            <button
              onClick={() => setEditorViewMode('split')}
              className={`px-2 py-1 text-xs rounded transition-colors flex items-center gap-1.5 ${
                editorViewMode === 'split' ? 'bg-canvas-elevated text-text-primary' : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <Split size={13} />
              <span>Split</span>
            </button>
            <button
              onClick={() => setEditorViewMode('preview')}
              className={`px-2 py-1 text-xs rounded transition-colors flex items-center gap-1.5 ${
                editorViewMode === 'preview' ? 'bg-canvas-elevated text-text-primary' : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <Eye size={13} />
              <span>Preview</span>
            </button>
          </div>

          <Button variant="primary" size="sm" icon={<Save size={14} />}>
            Save
          </Button>
        </div>
      </div>

      {/* Editor Content Area Placeholder */}
      <div className="flex-1 flex items-center justify-center p-8 text-center">
        <div className="max-w-md space-y-2">
          <h2 className="text-lg font-bold text-text-primary">Split-View Markdown Workspace</h2>
          <p className="text-xs text-text-secondary leading-relaxed">
            CodeMirror 6 editor and live rendered documentation preview integration is sequenced in Milestone 3.
          </p>
        </div>
      </div>
    </div>
  );
};
