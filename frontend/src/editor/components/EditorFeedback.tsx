import { CircleCheck, CircleHelp, LoaderCircle, X } from 'lucide-react';
import type { EditorCommands } from '../useEditorCommands';

export function EditorFeedback({ commands }: { commands: EditorCommands }) {
  const { notice, dismissNotice, busy } = commands;
  return (
    <>
      {notice && (
        <div className={`toast ${notice.error ? 'toast-error' : ''}`} role="status">
          {notice.error ? <CircleHelp size={16} /> : <CircleCheck size={16} />} {notice.text}
          <button onClick={dismissNotice} aria-label="Dismiss notification">
            <X size={13} />
          </button>
        </div>
      )}
      {busy && (
        <div className="working-pill">
          <LoaderCircle className="spin" size={14} />
          {busy === 'validate' ? 'Validating model…' : 'Processing request…'}
        </div>
      )}
    </>
  );
}
