import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { aylaLines } from '@/test/fixtures/collection';
import {
  useAddLine,
  useCollectionList,
  useDeleteLine,
  useKeepPlayset,
  usePatchLine,
  useSplitLine,
} from './queries';

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, 'invalidateQueries');
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, invalidate, wrapper };
}

describe('collection queries (F3-g S1)', () => {
  it('loads the list under a key made of the serialised params', async () => {
    const { client, wrapper } = setup();
    const { result } = renderHook(() => useCollectionList({ sort: 'value', dir: 'desc' }), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data.items).toHaveLength(3);
    expect(result.current.data?.meta?.totals.qty).toBe(16);
    expect(
      client.getQueryCache().find({ queryKey: ['collection', 'list', 'sort=value&dir=desc'] }),
    ).toBeDefined();
  });

  it('sends the search to the server', async () => {
    const { wrapper } = setup();
    const { result } = renderHook(() => useCollectionList({ q: 'ember' }), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data.items.map((group) => group.key)).toEqual(['OGN-12:S']);
  });

  const writes = [
    ['add', () => useAddLine(), { set_id: 'OGN', card_id: '79', foil: false, qty: 1 }],
    ['patch', () => usePatchLine(), { id: 1201, body: { qty: 2 } }],
    ['delete', () => useDeleteLine(), 1201],
    ['split', () => useSplitLine(), { id: 1201, body: { qty: 1, condition: 'EX' } }],
    ['keep playset', () => useKeepPlayset(), { set_id: 'OGN', card_id: '79', keep: true }],
  ] as const;

  it.each(writes)('%s refreshes the collection and the catalog counts', async (_, hook, vars) => {
    const { invalidate, wrapper } = setup();
    const { result } = renderHook(hook as () => { mutateAsync: (v: unknown) => Promise<unknown> }, {
      wrapper,
    });
    await act(async () => {
      await result.current.mutateAsync(vars);
    });
    const keys = invalidate.mock.calls.map(([filters]) => filters?.queryKey);
    expect(keys).toContainEqual(['collection']);
    expect(keys).toContainEqual(['cards']);
  });

  it('a patch returns the saved line', async () => {
    const { wrapper } = setup();
    const { result } = renderHook(() => usePatchLine(), { wrapper });
    let line;
    await act(async () => {
      line = await result.current.mutateAsync({ id: aylaLines[0].id, body: { qty: 5 } });
    });
    expect(line).toMatchObject({ id: 1201, qty: 5 });
  });
});
