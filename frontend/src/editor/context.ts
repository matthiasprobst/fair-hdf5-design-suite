import { createContext, useContext } from 'react';
import type { EditorStore } from './store';

export const EditorStoreContext = createContext<EditorStore | null>(null);
export function useEditorStore() {
  const store = useContext(EditorStoreContext);
  if (!store) throw new Error('Editor store context is missing.');
  return store;
}
