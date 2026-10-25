import { useEffect, useRef, useState } from 'react';
import { buildTemplateDraft } from './draft';
import type { CatalogItem, ProfileDocument, ProfileField, ProfileAnalysis } from '../types';
import { api } from '../lib/api';
import { useEditorStore } from '../editor/context';
import { useProjectSession } from '../projects/EditorSessionContext';

export function useLibraryEditor(template: CatalogItem | undefined, onClose: () => void) {
  const editorStore = useEditorStore();
  const session = useProjectSession();
  const [mode, setMode] = useState<'form' | 'turtle'>(template ? 'turtle' : 'form');
  const [label, setLabel] = useState(template?.label || '');
  const [category, setCategory] = useState(template?.category || 'Metadata');
  const [kind, setKind] = useState<'group' | 'dataset'>(template?.kind || 'group');
  const [path, setPath] = useState(String(template?.defaults.path || '/experiment/custom'));
  const [dtype, setDtype] = useState(String(template?.defaults.dtype || 'float64'));
  const [dimensions, setDimensions] = useState(String(template?.defaults.shape || '0'));
  const [color, setColor] = useState(template?.color || 'blue');
  const [icon, setIcon] = useState(template?.icon || 'metadata');
  const [shape, setShape] = useState(
    () => template?.shape || `urn:fair-hdf5:profile:${crypto.randomUUID()}`,
  );
  const [ttl, setTtl] = useState(template?.profile_ttl || '');
  const [fields, setFields] = useState<ProfileField[]>(
    () =>
      template?.fields?.map((f) => ({
        ...f,
        defaultValue: f.multiple
          ? undefined
          : String(template.defaults[f.key] ?? f.defaultValue ?? ''),
      })) || [],
  );
  const [documents, setDocuments] = useState<Record<string, ProfileDocument>>(
    template?.documents || {},
  );
  const [sourceUri, setSourceUri] = useState(template?.source_uri || '');
  const [dependencyUri, setDependencyUri] = useState('');
  const [analysis, setAnalysis] = useState<ProfileAnalysis | null>(null);
  const [analyzed, setAnalyzed] = useState(!!template);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  const beginRequest = () => {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    setError('');
    return controller;
  };
  const updateField = (index: number, patch: Partial<ProfileField>) =>
    setFields((fs) => fs.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  const analyze = async () => {
    const controller = beginRequest();
    setAnalyzed(false);
    try {
      const result = await api.analyzeProfile(
        ttl,
        documents,
        sourceUri || undefined,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setAnalysis(result);
      setDocuments(result.documents);
      setSourceUri(result.source_uri || '');
      const selected =
        result.shapes.find((s) => s.shape === shape && s.supported) ||
        result.shapes.find((s) => s.shape === result.source_uri && s.supported) ||
        result.shapes.find((s) => s.supported);
      if (selected) {
        if (!label.trim()) setLabel(selected.label);
        setShape(selected.shape);
        setFields(
          (selected.fields || []).map((f) => ({
            ...f,
            key: template?.mapping?.[f.predicate] || f.key,
          })),
        );
        setAnalyzed(true);
      } else setError('This file has no supported profile. See the explanations below.');
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  const save = async () => {
    const controller = beginRequest();
    try {
      const draft = buildTemplateDraft(
        {
          mode,
          label,
          category,
          kind,
          path,
          dtype,
          dimensions,
          color,
          icon,
          shape,
          fields,
          ttl,
          sourceUri,
          documents,
        },
        template,
      );
      const saved = await session.publish(
        draft,
        template?.project_local ? template.id : undefined,
        template?.project_local ? template.revision : undefined,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      editorStore.getState().publishTemplate(saved, template);
      onClose();
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  };
  return {
    mode,
    setMode,
    label,
    setLabel,
    category,
    setCategory,
    kind,
    setKind,
    path,
    setPath,
    dtype,
    setDtype,
    dimensions,
    setDimensions,
    color,
    setColor,
    icon,
    setIcon,
    shape,
    setShape,
    ttl,
    setTtl,
    fields,
    setFields,
    documents,
    setDocuments,
    sourceUri,
    setSourceUri,
    dependencyUri,
    setDependencyUri,
    analysis,
    setAnalysis,
    analyzed,
    setAnalyzed,
    error,
    setError,
    busy,
    setBusy,
    updateField,
    analyze,
    save,
  };
}
export type LibraryEditorModel = ReturnType<typeof useLibraryEditor>;
