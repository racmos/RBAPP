export type Settled<T> = { ok: true; value: T } | { ok: false; error: unknown };

/**
 * Run `worker` over `items` with at most `concurrency` at a time (F13-h S6). A failure is
 * recorded and the others go on; `onSettled(done)` reports the progress. The results keep the
 * order of `items`.
 */
export async function runBatch<I, T>(
  items: readonly I[],
  worker: (item: I, index: number) => Promise<T>,
  { concurrency = 2, onSettled }: { concurrency?: number; onSettled?: (done: number) => void } = {},
): Promise<Settled<T>[]> {
  const results: Settled<T>[] = new Array(items.length);
  let next = 0;
  let done = 0;
  const lane = async () => {
    while (next < items.length) {
      const index = next++;
      try {
        results[index] = { ok: true, value: await worker(items[index], index) };
      } catch (error) {
        results[index] = { ok: false, error };
      }
      done += 1;
      onSettled?.(done);
    }
  };
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, lane));
  return results;
}
