import { useRef, useState } from 'react';
import type { PointerEvent } from 'react';

type Props = {
  label: string;
  controls: string;
  orientation: 'horizontal' | 'vertical';
  direction: 1 | -1;
  value: number;
  min: number;
  max: number;
  onResize: (size: number) => void;
  onReset: () => void;
};

/** Pointer capture keeps dragging reliable when the pointer leaves the narrow divider. */
export function ResizeHandle({
  label,
  controls,
  orientation,
  direction,
  value,
  min,
  max,
  onResize,
  onReset,
}: Props) {
  const drag = useRef<{ pointerId: number; coordinate: number; size: number } | null>(null);
  const [resizing, setResizing] = useState(false);
  const vertical = orientation === 'vertical';
  const coordinate = (event: PointerEvent<HTMLDivElement>) =>
    vertical ? event.clientX : event.clientY;
  const resize = (size: number) => onResize(Math.min(Math.max(size, min), max));
  const finish = (element: HTMLDivElement, restore = false) => {
    const current = drag.current;
    drag.current = null;
    setResizing(false);
    if (!current) return;
    if (restore) onResize(current.size);
    if (element.hasPointerCapture(current.pointerId))
      element.releasePointerCapture(current.pointerId);
  };

  return (
    <div
      className="resize-handle"
      role="separator"
      tabIndex={0}
      aria-label={label}
      aria-controls={controls}
      aria-orientation={orientation}
      aria-valuemin={Math.round(min)}
      aria-valuemax={Math.round(max)}
      aria-valuenow={Math.round(value)}
      aria-valuetext={`${Math.round(value)} pixels`}
      title={`${label} · Drag or use arrow keys · Double-click to reset`}
      data-resizing={resizing}
      onPointerDown={(event) => {
        if (event.button !== 0 || !event.isPrimary) return;
        event.preventDefault();
        event.stopPropagation();
        event.currentTarget.focus();
        drag.current = { pointerId: event.pointerId, coordinate: coordinate(event), size: value };
        event.currentTarget.setPointerCapture(event.pointerId);
        setResizing(true);
      }}
      onPointerMove={(event) => {
        const current = drag.current;
        if (!current || current.pointerId !== event.pointerId) return;
        event.preventDefault();
        resize(current.size + direction * (coordinate(event) - current.coordinate));
      }}
      onPointerUp={(event) => finish(event.currentTarget)}
      onPointerCancel={(event) => finish(event.currentTarget, true)}
      onLostPointerCapture={() => {
        drag.current = null;
        setResizing(false);
      }}
      onDoubleClick={onReset}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && drag.current) {
          finish(event.currentTarget, true);
        } else if (event.key === 'Home') {
          resize(min);
        } else if (event.key === 'End') {
          resize(max);
        } else {
          const delta =
            event.key === (vertical ? 'ArrowRight' : 'ArrowDown')
              ? 1
              : event.key === (vertical ? 'ArrowLeft' : 'ArrowUp')
                ? -1
                : 0;
          if (!delta) return;
          resize(value + delta * direction * (event.shiftKey ? 50 : 10));
        }
        event.preventDefault();
        event.stopPropagation();
      }}
    />
  );
}
