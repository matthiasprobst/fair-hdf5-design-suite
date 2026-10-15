import { useLayoutEffect, useRef, useState } from 'react';
import type { WorkbenchPanels } from './useWorkbenchPanels';
import {
  CANVAS_MIN_WIDTH,
  PANEL_GAP,
  PANEL_MAX,
  PANEL_MIN,
  STAGE_MIN_HEIGHT,
  resolvePanelSizes,
} from './panelSizes';
import type { PanelPreferences, PanelSizes, ResizablePanel } from './panelSizes';

export function useWorkbenchSizing(panels: WorkbenchPanels) {
  const ref = useRef<HTMLDivElement>(null);
  const [preferences, setPreferences] = useState<PanelPreferences>({});
  const [bounds, setBounds] = useState({
    width: 1200,
    height: 640,
    defaults: { library: 225, inspector: 333, artifacts: 213 },
  });

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const measure = () => {
      const style = getComputedStyle(element);
      const next = {
        width: element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
        height: element.clientHeight,
        defaults: {
          library: parseFloat(style.getPropertyValue('--library-width')),
          inspector: parseFloat(style.getPropertyValue('--inspector-width')),
          artifacts: parseFloat(style.getPropertyValue('--artifacts-height')),
        },
      };
      setBounds((previous) =>
        previous.width === next.width &&
        previous.height === next.height &&
        Object.keys(next.defaults).every(
          (key) =>
            previous.defaults[key as ResizablePanel] === next.defaults[key as ResizablePanel],
        )
          ? previous
          : next,
      );
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    // Media-query defaults can change even when the workspace's dimensions do not.
    window.addEventListener('resize', measure);
    measure();
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, []);

  const sizes = resolvePanelSizes(
    { ...bounds.defaults, ...preferences },
    bounds.width,
    bounds.height,
    panels.compact,
    panels.libraryOpen,
    panels.inspectorOpen,
  );
  const available =
    bounds.width -
    CANVAS_MIN_WIDTH -
    PANEL_GAP * (Number(panels.libraryOpen) + Number(panels.inspectorOpen));
  const maxima: PanelSizes = {
    library: Math.max(
      PANEL_MIN.library,
      Math.min(
        PANEL_MAX.library,
        panels.compact
          ? bounds.width * 0.8
          : available - (panels.inspectorOpen ? sizes.inspector : 0),
      ),
    ),
    inspector: Math.max(
      PANEL_MIN.inspector,
      Math.min(
        PANEL_MAX.inspector,
        panels.compact ? bounds.width * 0.8 : available - (panels.libraryOpen ? sizes.library : 0),
      ),
    ),
    artifacts: Math.max(PANEL_MIN.artifacts, bounds.height - STAGE_MIN_HEIGHT - PANEL_GAP),
  };
  return {
    ref,
    sizes,
    maxima,
    resize: (panel: ResizablePanel, size: number) =>
      setPreferences((current) => ({ ...current, [panel]: size })),
    reset: (panel: ResizablePanel) =>
      setPreferences((current) => {
        const next = { ...current };
        delete next[panel];
        return next;
      }),
  };
}
