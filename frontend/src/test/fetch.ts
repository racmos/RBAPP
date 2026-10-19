/**
 * Node's `fetch` rejects relative URLs, but the SPA always calls same-origin paths. Resolve them
 * against the jsdom location, as a browser does.
 */
export function installRelativeFetch(): void {
  const nativeFetch = globalThis.fetch.bind(globalThis);
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
    nativeFetch(
      typeof input === 'string' ? new URL(input, window.location.href).href : input,
      init,
    )) as typeof fetch;
}
