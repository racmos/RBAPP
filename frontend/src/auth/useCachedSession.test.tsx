import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { ANONYMOUS, sessionQuery } from './session';
import { useCachedSession } from './useAuth';

const setup = () => {
  const queryClient = new QueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, ...renderHook(() => useCachedSession(), { wrapper }) };
};

describe('useCachedSession', () => {
  it('is undefined while the cache is empty and never fetches (MSW would fail the test)', () => {
    const { result, queryClient } = setup();
    expect(result.current).toBeUndefined();
    expect(queryClient.isFetching()).toBe(0);
  });

  it('follows the cache, including a clear followed by an anonymous session', () => {
    const { result, queryClient } = setup();
    act(
      () =>
        void queryClient.setQueryData(sessionQuery.queryKey, { ...ANONYMOUS, authenticated: true }),
    );
    expect(result.current?.authenticated).toBe(true);
    act(() => {
      queryClient.clear();
    });
    expect(result.current).toBeUndefined();
    expect(queryClient.isFetching()).toBe(0); // still no refetch
    act(() => void queryClient.setQueryData(sessionQuery.queryKey, ANONYMOUS));
    expect(result.current).toEqual(ANONYMOUS);
  });
});
