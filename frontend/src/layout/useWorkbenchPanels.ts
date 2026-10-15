import { useCallback, useEffect, useRef, useState } from 'react';

// Keep aligned with the workbench breakpoint in workbench.css.
const COMPACT_QUERY = '(width < 1150px)';
type SidePanel = 'library' | 'inspector';
type Panel = SidePanel | 'artifacts';

/** UI preferences never enter the blueprint or trigger persistence/preview requests. */
export function useWorkbenchPanels() {
  const [compact, setCompact] = useState(() => window.matchMedia(COMPACT_QUERY).matches);
  const [desktopLibraryOpen, setDesktopLibraryOpen] = useState(true);
  const [artifactsOpen, setArtifactsOpen] = useState(true);
  const [desktopInspectorOpen, setDesktopInspectorOpen] = useState(true);
  const [overlay, setOverlay] = useState<SidePanel | null>(null);
  const artifactsTrigger = useRef<HTMLButtonElement>(null);
  const libraryTrigger = useRef<HTMLButtonElement>(null);
  const inspectorTrigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const query = window.matchMedia(COMPACT_QUERY);
    const update = () => {
      const focusedPanel = document.activeElement?.closest(
        '#workbench-library, #workbench-inspector',
      );
      setCompact(query.matches);
      setOverlay(null);
      if (query.matches && focusedPanel) {
        const trigger = focusedPanel.id === 'workbench-library' ? libraryTrigger : inspectorTrigger;
        requestAnimationFrame(() => trigger.current?.focus());
      }
    };
    query.addEventListener('change', update);
    update();
    return () => query.removeEventListener('change', update);
  }, []);

  const showInspector = useCallback(() => {
    if (compact) setOverlay('inspector');
    else setDesktopInspectorOpen(true);
  }, [compact]);

  const close = useCallback(
    (panel: Panel) => {
      if (panel === 'artifacts') setArtifactsOpen(false);
      else if (compact) setOverlay(null);
      else if (panel === 'inspector') setDesktopInspectorOpen(false);
      else setDesktopLibraryOpen(false);
      const trigger =
        panel === 'artifacts'
          ? artifactsTrigger
          : panel === 'library'
            ? libraryTrigger
            : inspectorTrigger;
      // The desktop reopen button becomes visible after React commits the closed state.
      requestAnimationFrame(() => trigger.current?.focus());
    },
    [compact],
  );

  return {
    compact,
    libraryOpen: compact ? overlay === 'library' : desktopLibraryOpen,
    artifactsOpen,
    artifactsTrigger,
    inspectorOpen: compact ? overlay === 'inspector' : desktopInspectorOpen,
    libraryTrigger,
    inspectorTrigger,
    showInspector,
    close,
    toggleLibrary: () => {
      if (compact) setOverlay((current) => (current === 'library' ? null : 'library'));
      else setDesktopLibraryOpen((current) => !current);
    },
    toggleArtifacts: () => setArtifactsOpen((current) => !current),
    toggleInspector: () => {
      if (compact) setOverlay((current) => (current === 'inspector' ? null : 'inspector'));
      else setDesktopInspectorOpen((current) => !current);
    },
    closeOverlay: () => {
      if (overlay) close(overlay);
    },
  };
}

export type WorkbenchPanels = ReturnType<typeof useWorkbenchPanels>;
