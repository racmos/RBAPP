import { describe, expect, it } from 'vitest';
import { request } from '@/api/client';

describe('MSW test server', () => {
  it('fails a request that has no handler instead of reaching the network', async () => {
    await expect(request('/no/such/endpoint')).rejects.toMatchObject({ kind: 'network' });
  });

  it('serves the default anonymous session', async () => {
    await expect(request('/auth/session')).resolves.toMatchObject({ authenticated: false });
  });
});
