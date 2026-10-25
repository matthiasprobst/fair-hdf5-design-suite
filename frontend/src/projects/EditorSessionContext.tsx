import { createContext, useContext } from 'react';
import { useStore } from 'zustand';
import type { ProjectEditorSession } from './editorSession';

export const EditorSessionContext = createContext<ProjectEditorSession | null>(null);
export function useProjectSession() {
  const session = useContext(EditorSessionContext);
  if (!session) throw new Error('Project editor session is missing.');
  return session;
}
export function useCanEdit() {
  const session = useProjectSession();
  const editing = useStore(session.state, (s) => s.mode === 'editing' && !s.busy);
  return editing && session.canEdit();
}
