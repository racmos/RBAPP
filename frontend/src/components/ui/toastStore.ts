import { announce } from './LiveAnnouncer';

export type ToastKind = 'success' | 'error' | 'info';
export type ToastInput = {
  kind: ToastKind;
  message: string;
  /** A focusable button; running it dismisses the toast. */
  action?: { label: string; onAction: () => void };
  /** Milliseconds before it goes away; 0 keeps it until dismissed. */
  duration?: number;
  /** Runs once when the toast goes away without its action: timed out or closed (F13-h S7). */
  onExpire?: () => void;
};
export type Toast = ToastInput & { id: number };

export const DEFAULT_DURATION_MS = 6000;

let toasts: readonly Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

const emit = (next: readonly Toast[]) => {
  toasts = next;
  listeners.forEach((listener) => listener());
};

export function pushToast(input: ToastInput): number {
  const id = nextId++;
  emit([...toasts, { ...input, id }]);
  announce(input.message);
  return id;
}

/** Remove a toast; unless it went away through its action, its `onExpire` runs. */
export const dismissToast = (id: number, { byAction = false } = {}): void => {
  const gone = toasts.find((toast) => toast.id === id);
  emit(toasts.filter((toast) => toast.id !== id));
  if (gone && !byAction) gone.onExpire?.();
};
export const clearToasts = (): void => emit([]);

export const subscribeToasts = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};
export const getToasts = (): readonly Toast[] => toasts;
