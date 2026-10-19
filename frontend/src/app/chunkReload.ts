import { readStorage, removeStorage, writeStorage } from '@/lib/storage';

export const CHUNK_RELOAD_KEY = 'rb_chunk_reload';
/** After this long without another failure the next one counts as a fresh deploy. */
const HEALTHY_AFTER_MS = 10_000;

const CHUNK_ERROR =
  /dynamically imported module|importing a module script failed|unable to preload|error loading dynamically/i;

/** True for the errors a stale tab gets when a deploy removed the old hashed assets. */
export const isChunkLoadError = (error: unknown): boolean =>
  error instanceof Error && CHUNK_ERROR.test(error.message);

type Options = { reload?: () => void };

/**
 * After a deploy the old `assets/` are gone. On `vite:preloadError` reload once (D24); a
 * sessionStorage guard stops a reload loop when the failure is not a stale tab. Returns an
 * uninstall function.
 */
export function installChunkReload({
  reload = () => window.location.reload(),
}: Options = {}): () => void {
  const onError = (event: Event) => {
    if (readStorage(CHUNK_RELOAD_KEY, 'session') !== null) return;
    event.preventDefault();
    writeStorage(CHUNK_RELOAD_KEY, String(Date.now()), 'session');
    reload();
  };
  window.addEventListener('vite:preloadError', onError);
  const healthy = setTimeout(() => removeStorage(CHUNK_RELOAD_KEY, 'session'), HEALTHY_AFTER_MS);
  return () => {
    window.removeEventListener('vite:preloadError', onError);
    clearTimeout(healthy);
  };
}
