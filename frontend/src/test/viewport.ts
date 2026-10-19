/**
 * matchMedia mock for jsdom. It evaluates `min-width` / `max-width` clauses (joined with
 * `and`) against a width set by `setViewport`; any other media feature does not match.
 */
const DEFAULT_WIDTH = 1280;

type Listener = (event: MediaQueryListEvent) => void;
type Entry = {
  media: string;
  onchange: Listener | null;
  listeners: Set<Listener>;
  last: boolean;
};

let width = DEFAULT_WIDTH;
const subscribed = new Set<Entry>();

const CLAUSE = /^\(\s*(min|max)-width\s*:\s*([\d.]+)px\s*\)$/;

function evaluate(media: string): boolean {
  return media.split(/\s+and\s+/).every((part) => {
    const match = CLAUSE.exec(part.trim());
    if (!match) return false;
    const limit = Number(match[2]);
    return match[1] === 'min' ? width >= limit : width <= limit;
  });
}

function createList(media: string): MediaQueryList {
  const entry: Entry = { media, onchange: null, listeners: new Set(), last: evaluate(media) };
  const subscribe = (listener: Listener) => {
    entry.listeners.add(listener);
    entry.last = evaluate(media);
    subscribed.add(entry);
  };
  const unsubscribe = (listener: Listener) => {
    entry.listeners.delete(listener);
    if (entry.listeners.size === 0) subscribed.delete(entry);
  };
  const list = {
    get matches() {
      return evaluate(media);
    },
    media,
    get onchange() {
      return entry.onchange;
    },
    set onchange(handler) {
      entry.onchange = handler as Listener | null;
    },
    addEventListener: (type: string, listener: Listener) => {
      if (type === 'change') subscribe(listener);
    },
    removeEventListener: (type: string, listener: Listener) => {
      if (type === 'change') unsubscribe(listener);
    },
    addListener: subscribe,
    removeListener: unsubscribe,
    dispatchEvent: () => false,
  };
  return list as unknown as MediaQueryList;
}

/** Replace `window.matchMedia` with the mock. */
export function installMatchMedia(): void {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (media: string) => createList(media),
  });
}

/** Set the viewport width and notify the listeners whose result changed. */
export function setViewport(next: number): void {
  width = next;
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: next });
  for (const entry of [...subscribed]) {
    const matches = evaluate(entry.media);
    if (matches === entry.last) continue;
    entry.last = matches;
    const event = { matches, media: entry.media } as MediaQueryListEvent;
    entry.onchange?.(event);
    for (const listener of [...entry.listeners]) listener(event);
  }
}

/** Back to the default desktop width and no live subscriptions. */
export function resetViewport(): void {
  subscribed.clear();
  setViewport(DEFAULT_WIDTH);
}
