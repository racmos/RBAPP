import { QueryClient } from '@tanstack/react-query';
import { http, HttpResponse, delay } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/errors';
import type { Prefs } from '@/api/types';
import { sessionQuery } from '@/auth';
import { API, NO_PREFS, USER, failure } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { createPrefsSync } from './sync';

type Body = Partial<Prefs>;

/** Record every PATCH body; `reply` decides the answer (default: echo the merged prefs). */
function recordPatches(reply?: (body: Body, index: number) => Response | Promise<Response>) {
  const bodies: Body[] = [];
  let stored: Prefs = { ...NO_PREFS } as Prefs;
  server.use(
    http.patch(`${API}/me/prefs`, async ({ request }) => {
      const body = (await request.json()) as Body;
      bodies.push(body);
      if (reply) return reply(body, bodies.length - 1);
      stored = { ...stored, ...body };
      return HttpResponse.json({ success: true, data: { prefs: stored } });
    }),
  );
  return bodies;
}

const seed = (queryClient: QueryClient, prefs: Prefs = NO_PREFS as Prefs) =>
  queryClient.setQueryData(sessionQuery.queryKey, { authenticated: true, user: USER, prefs });
const cached = (queryClient: QueryClient) =>
  queryClient.getQueryData(sessionQuery.queryKey)!.prefs as Prefs;

let queryClient: QueryClient;
let errors: { error: unknown; retry: () => void }[];
const make = (debounceMs?: number) =>
  createPrefsSync({
    queryClient,
    debounceMs,
    onError: (error, retry) => errors.push({ error, retry }),
  });

beforeEach(() => {
  queryClient = new QueryClient();
  errors = [];
  seed(queryClient);
});
afterEach(() => vi.useRealTimers());

describe('optimistic save (PREF-8)', () => {
  it('applies the value at once and sends exactly one PATCH with that field', async () => {
    const bodies = recordPatches();
    const sync = make();
    sync.set('accent', 'cyan');
    expect(cached(queryClient).accent).toBe('cyan'); // before the answer
    await vi.waitFor(() => expect(bodies).toEqual([{ accent: 'cyan' }]));
    await vi.waitFor(() => expect(cached(queryClient).accent).toBe('cyan'));
    expect(errors).toEqual([]);
  });

  it('keeps the server answer in the session cache and the mirror source', async () => {
    recordPatches(() =>
      HttpResponse.json({
        success: true,
        data: { prefs: { ...NO_PREFS, density: 'comfy', lang: 'en' } },
      }),
    );
    const sync = make();
    sync.set('density', 'comfy');
    await vi.waitFor(() => expect(cached(queryClient).lang).toBe('en'));
    expect(cached(queryClient).density).toBe('comfy');
  });

  it('Auto sends null', async () => {
    seed(queryClient, { ...NO_PREFS, density: 'comfy' } as Prefs);
    const bodies = recordPatches();
    make().set('density', null);
    expect(cached(queryClient).density).toBeNull();
    await vi.waitFor(() => expect(bodies).toEqual([{ density: null }]));
  });

  it('sends only the fields that differ from the confirmed state', async () => {
    seed(queryClient, { ...NO_PREFS, accent: 'cyan' } as Prefs);
    const bodies = recordPatches();
    const sync = make();
    sync.set('accent', 'cyan'); // unchanged
    sync.set('lang', 'en');
    await vi.waitFor(() => expect(bodies).toEqual([{ lang: 'en' }]));
  });
});

describe('failure (PREF-8)', () => {
  it('reverts the value and reports the error with a retry action', async () => {
    seed(queryClient, { ...NO_PREFS, density: 'regular' } as Prefs);
    const bodies = recordPatches(() => failure(500, { message: 'boom' }));
    const sync = make();
    sync.set('density', 'comfy');
    expect(cached(queryClient).density).toBe('comfy');
    await vi.waitFor(() => expect(errors).toHaveLength(1));
    expect(cached(queryClient).density).toBe('regular');
    expect(errors[0].error).toBeInstanceOf(ApiError);
    expect(bodies).toEqual([{ density: 'comfy' }]);
  });

  it('the retry action applies and sends the failed change again', async () => {
    let attempts = 0;
    const bodies = recordPatches((body) => {
      attempts += 1;
      return attempts === 1
        ? failure(500)
        : HttpResponse.json({ success: true, data: { prefs: { ...NO_PREFS, ...body } } });
    });
    const sync = make();
    sync.set('density', 'comfy');
    await vi.waitFor(() => expect(errors).toHaveLength(1));
    errors[0].retry();
    expect(cached(queryClient).density).toBe('comfy');
    await vi.waitFor(() => expect(bodies).toEqual([{ density: 'comfy' }, { density: 'comfy' }]));
    await vi.waitFor(() => expect(cached(queryClient).density).toBe('comfy'));
    expect(errors).toHaveLength(1);
  });

  it('does not report a 401: the global handler owns it', async () => {
    recordPatches(() => failure(401, { code: 'unauthenticated' }));
    const sync = make();
    sync.set('accent', 'cyan');
    await vi.waitFor(() => expect(cached(queryClient).accent).toBeNull());
    expect(errors).toEqual([]);
  });
});

describe('slider debounce (PREF-8)', () => {
  it('ten values within the window send one PATCH with the last value', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const bodies = recordPatches();
    const sync = make(400);
    for (let value = 10; value <= 100; value += 10) {
      sync.set('bg_intensity', value, { debounce: true });
      vi.advanceTimersByTime(30);
    }
    expect(cached(queryClient).bg_intensity).toBe(100); // live
    expect(bodies).toEqual([]); // nothing yet
    vi.advanceTimersByTime(400);
    vi.useRealTimers();
    await vi.waitFor(() => expect(bodies).toEqual([{ bg_intensity: 100 }]));
  });

  it('flush() sends at once (pointerup, blur, pagehide)', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const bodies = recordPatches();
    const sync = make(400);
    sync.set('bg_intensity', 40, { debounce: true });
    sync.flush();
    vi.useRealTimers();
    await vi.waitFor(() => expect(bodies).toEqual([{ bg_intensity: 40 }]));
  });

  it('sends nothing when the slider comes back to the confirmed value', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    seed(queryClient, { ...NO_PREFS, bg_intensity: 100 } as Prefs);
    const bodies = recordPatches();
    const sync = make(400);
    sync.set('bg_intensity', 40, { debounce: true });
    sync.set('bg_intensity', 100, { debounce: true });
    vi.advanceTimersByTime(500);
    vi.useRealTimers();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(bodies).toEqual([]);
  });
});

describe('one request in flight', () => {
  it('merges the changes made meanwhile into the next request', async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    let serverSide: Prefs = { ...NO_PREFS } as Prefs;
    const bodies = recordPatches(async (body, index) => {
      if (index === 0) await gate;
      serverSide = { ...serverSide, ...body };
      return HttpResponse.json({ success: true, data: { prefs: serverSide } });
    });
    const sync = make();
    sync.set('accent', 'cyan');
    await vi.waitFor(() => expect(bodies).toHaveLength(1));
    sync.set('density', 'comfy');
    sync.set('lang', 'en');
    await delay(30);
    expect(bodies).toHaveLength(1); // still waiting for the first answer
    release();
    await vi.waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toEqual({ density: 'comfy', lang: 'en' });
    await vi.waitFor(() => expect(cached(queryClient).lang).toBe('en'));
    expect(cached(queryClient)).toMatchObject({ accent: 'cyan', density: 'comfy', lang: 'en' });
  });

  it('keeps a newer pending value when an older request fails', async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    const bodies = recordPatches(async (body, index) => {
      if (index === 0) {
        await gate;
        return failure(500);
      }
      return HttpResponse.json({ success: true, data: { prefs: { ...NO_PREFS, ...body } } });
    });
    const sync = make();
    sync.set('accent', 'cyan');
    await vi.waitFor(() => expect(bodies).toHaveLength(1));
    sync.set('accent', 'orange'); // newer value for the same field
    release();
    await vi.waitFor(() => expect(errors).toHaveLength(1));
    await vi.waitFor(() => expect(bodies).toEqual([{ accent: 'cyan' }, { accent: 'orange' }]));
    await vi.waitFor(() => expect(cached(queryClient).accent).toBe('orange'));
  });
});
