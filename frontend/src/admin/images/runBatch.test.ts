import { describe, expect, it } from 'vitest';
import { runBatch } from './runBatch';

const tick = () => new Promise((resolve) => setTimeout(resolve, 1));

describe('runBatch (F13-h S6: concurrency 2, a failure never stops the others)', () => {
  it('runs at most two at a time, reports progress and keeps going after a failure', async () => {
    let running = 0;
    let peak = 0;
    const progress: number[] = [];
    const results = await runBatch(
      [1, 2, 3, 4, 5],
      async (value) => {
        running += 1;
        peak = Math.max(peak, running);
        await tick();
        running -= 1;
        if (value === 2) throw new Error('boom');
        return value * 10;
      },
      { concurrency: 2, onSettled: (done) => progress.push(done) },
    );
    expect(peak).toBe(2);
    expect(progress).toEqual([1, 2, 3, 4, 5]);
    expect(results).toEqual([
      { ok: true, value: 10 },
      { ok: false, error: new Error('boom') },
      { ok: true, value: 30 },
      { ok: true, value: 40 },
      { ok: true, value: 50 },
    ]);
  });

  it('an empty batch settles at once', async () => {
    expect(await runBatch([], async () => 1)).toEqual([]);
  });
});
