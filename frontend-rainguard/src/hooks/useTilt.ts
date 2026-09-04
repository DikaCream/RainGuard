import { useCallback, useRef, type MouseEvent as ReactMouseEvent } from "react";

interface TiltOptions {
  /** Max rotation in degrees each way. */
  max?: number;
}

export interface TiltHandlers<T extends HTMLElement> {
  ref: (node: T | null) => void;
  onMouseMove: (e: ReactMouseEvent<T>) => void;
  onMouseLeave: () => void;
}

/**
 * Cursor-tracked 3D tilt. Writes --rx/--ry (deg) so the card can render
 * `perspective(...) rotateX(var(--rx)) rotateY(var(--ry))`, plus --gx/--gy (%)
 * so a glare highlight follows the pointer. Pair with the `.tilt`/`.glare`
 * CSS classes. Exposes a callback ref so it works on any element type.
 */
export function useTilt<T extends HTMLElement = HTMLDivElement>({
  max = 8,
}: TiltOptions = {}): TiltHandlers<T> {
  const nodeRef = useRef<T | null>(null);

  const setRef = useCallback((node: T | null) => {
    nodeRef.current = node;
  }, []);

  const onMouseMove = useCallback(
    (e: ReactMouseEvent<T>) => {
      const el = nodeRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      const px = (e.clientX - r.left) / r.width;
      const py = (e.clientY - r.top) / r.height;
      el.style.setProperty("--rx", `${((0.5 - py) * max * 2).toFixed(2)}deg`);
      el.style.setProperty("--ry", `${((px - 0.5) * max * 2).toFixed(2)}deg`);
      el.style.setProperty("--gx", `${(px * 100).toFixed(1)}%`);
      el.style.setProperty("--gy", `${(py * 100).toFixed(1)}%`);
    },
    [max],
  );

  const onMouseLeave = useCallback(() => {
    const el = nodeRef.current;
    if (!el) return;
    el.style.setProperty("--rx", "0deg");
    el.style.setProperty("--ry", "0deg");
  }, []);

  return { ref: setRef, onMouseMove, onMouseLeave };
}