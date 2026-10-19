import { QueryClient } from '@tanstack/react-query';
import { shouldRetry } from '@/auth/session';

export function createQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: shouldRetry } } });
}
