import { demoWithinLimits } from './limits';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import type { Dialog } from '../components/Modal';
import { api } from '../lib/api';
import { download, jsonFile } from '../lib/downloads';
import { editorStore } from './store';
import { parseBlueprint, toBlueprint } from './adapters';
import { artifacts } from './lifecycle';

/** Editor operations and their cancellation lifecycle, independent of panel layout. */
export function useEditorCommands(recoveryRaw: string | null) {
  const [dialog, setDialog] = useState<Dialog>(null);
  const [notice, setNotice] = useState<{ text: string; error: boolean } | null>(null);
  const [busy, setBusy] = useState('');
  const importRef = useRef<HTMLInputElement>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const operation = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const onNotice = useCallback((text: string, error = false) => {
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    setNotice({ text, error });
    noticeTimer.current = setTimeout(() => setNotice(null), 4500);
  }, []);
  const cancelPending = useCallback(() => {
    pending.current?.abort();
    operation.current++;
  }, []);
  useEffect(() => {
    const unsubscribe = editorStore.subscribe((s, p) => {
      if (s.semanticRevision !== p.semanticRevision) {
        cancelPending();
        setBusy('');
      }
    });
    return () => {
      unsubscribe();
      cancelPending();
      if (noticeTimer.current) clearTimeout(noticeTimer.current);
    };
  }, [cancelPending]);
  const execute = useCallback(
    async (label: string, fn: (signal: AbortSignal) => Promise<void>) => {
      pending.current?.abort();
      const controller = new AbortController();
      pending.current = controller;
      const token = ++operation.current;
      setBusy(label);
      try {
        await fn(controller.signal);
      } catch (e) {
        if (!controller.signal.aborted) onNotice(e instanceof Error ? e.message : String(e), true);
      } finally {
        if (operation.current === token) setBusy('');
      }
    },
    [onNotice],
  );
  const exportHdf5 = () =>
    void execute('hdf5', async () => {
      const blob = await artifacts.hdf5();
      if (blob) download(blob, 'experiment-template.h5');
    });
  const exportShacl = () =>
    void execute('shacl', async () => {
      const text = await artifacts.shacl();
      if (text !== undefined)
        download(new Blob([text], { type: 'text/turtle' }), 'experiment.shacl.ttl');
    });
  const previewShacl = () =>
    void execute('shacl-preview', async () => {
      if ((await artifacts.shacl()) !== undefined) setDialog('shacl');
    });
  const previewStructure = () =>
    void execute('preview', async () => {
      if (await artifacts.preview()) setDialog('structure');
    });
  const runValidation = (file?: File) =>
    void execute('validate', async () => {
      const report = await artifacts.validation(file);
      if (report) {
        setDialog('validation');
        onNotice(
          report.conforms
            ? 'Validation passed.'
            : `${report.issue_count} validation issue(s) found.`,
          !report.conforms,
        );
      }
    });
  const refresh = () =>
    void execute('refresh', async () => {
      if (await artifacts.preview()) onNotice('Blueprint analyzed.');
    });
  const importBlueprint = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    await execute('import', async (signal) => {
      const { catalog, capabilities } = editorStore.getState();
      if (!capabilities) throw new Error('Backend limits are not loaded. Retry connection.');
      const content = parseBlueprint(JSON.parse(await file.text()), catalog, capabilities);
      if (signal.aborted) return;
      editorStore.getState().replace(content);
      onNotice('Blueprint imported.');
    });
  };
  const reset = () =>
    void execute('reset', async (signal) => {
      if (!window.confirm('Reset the current experiment to the demonstration blueprint?')) return;
      const { catalog, capabilities } = editorStore.getState();
      if (!capabilities) throw new Error('Backend limits are not loaded. Retry connection.');
      const content = demoWithinLimits(
        parseBlueprint(await api.demo(signal), catalog),
        capabilities,
      );
      if (signal.aborted) return;
      editorStore.getState().replace(content);
      editorStore.getState().select('pressure');
      onNotice(
        content.nodes.length
          ? 'Demo experiment restored.'
          : 'Empty workspace restored; the demo exceeds the configured limits.',
      );
    });
  const onSaveJson = () =>
    jsonFile(toBlueprint(editorStore.getState()), 'experiment-blueprint.json');
  const onLoadFile = () => importRef.current?.click();
  const exportRecovery = () => {
    if (recoveryRaw !== null)
      download(new Blob([recoveryRaw], { type: 'application/json' }), 'original-draft.json');
  };

  return {
    dialog,
    setDialog,
    notice,
    dismissNotice: () => setNotice(null),
    onNotice,
    busy,
    importRef,
    uploadRef,
    importBlueprint,
    onLoadFile,
    onSaveJson,
    exportRecovery,
    exportHdf5,
    exportShacl,
    previewShacl,
    previewStructure,
    runValidation,
    refresh,
    reset,
  };
}
export type EditorCommands = ReturnType<typeof useEditorCommands>;
