import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/renderApp';

// Startup smoke test (M-a): the whole app boots on a signed-out session (default MSW handlers).
describe('smoke', () => {
  it('the app boots on the login screen', async () => {
    await renderApp({ path: '/login' });
    expect(await screen.findByLabelText('Username')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeVisible();
  });
});
