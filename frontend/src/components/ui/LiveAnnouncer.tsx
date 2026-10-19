import { useSyncExternalStore } from 'react';

/** Zero-width space: invisible, but a changed string for the live region. */
const INVISIBLE = String.fromCharCode(0x200b);

let message = '';
let flip = false;
const listeners = new Set<() => void>();

/**
 * Speak `text` through the always-mounted live region. Repeating the same text appends an
 * invisible character so assistive technology sees a change and reads it again.
 */
export function announce(text: string): void {
  flip = text === message.replace(INVISIBLE, '') ? !flip : false;
  message = flip ? `${text}${INVISIBLE}` : text;
  listeners.forEach((listener) => listener());
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** Mount once at the root: content added to a freshly created live region is announced unreliably. */
export function LiveAnnouncer() {
  const text = useSyncExternalStore(subscribe, () => message);
  return (
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {text}
    </div>
  );
}
