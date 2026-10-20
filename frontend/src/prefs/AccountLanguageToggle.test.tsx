import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { API, NO_PREFS, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { SIGNED_IN, renderWithPrefs } from '@/test/prefs';
import { AccountLanguageToggle } from './AccountLanguageToggle';

const recordPatches = () => {
  const bodies: unknown[] = [];
  server.use(
    http.patch(`${API}/me/prefs`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      bodies.push(body);
      return ok({ prefs: { ...NO_PREFS, ...body } });
    }),
  );
  return bodies;
};

describe('AccountLanguageToggle (PREF-8, R4)', () => {
  it('anonymous: writes only rb_lang and sends no PATCH', async () => {
    const bodies = recordPatches();
    const { i18n } = await renderWithPrefs(<AccountLanguageToggle />);
    await userEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(i18n.language).toBe('en');
    expect(localStorage.getItem('rb_lang')).toBe('en');
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(bodies).toEqual([]);
  });

  it('signed in: writes rb_lang and sends {"lang":...}', async () => {
    const bodies = recordPatches();
    const { i18n, queryClient } = await renderWithPrefs(<AccountLanguageToggle />, {
      session: SIGNED_IN,
    });
    await userEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(localStorage.getItem('rb_lang')).toBe('en');
    expect(i18n.language).toBe('en');
    await waitFor(() => expect(bodies).toEqual([{ lang: 'en' }]));
    expect(queryClient.getQueryData<typeof SIGNED_IN>(['session'])?.prefs?.lang).toBe('en');
  });

  it('signed in: a failed save reverts the account value and says so, with a retry', async () => {
    server.use(http.patch(`${API}/me/prefs`, () => failure(500)));
    const { queryClient, i18n } = await renderWithPrefs(<AccountLanguageToggle />, {
      session: { ...SIGNED_IN, prefs: { ...NO_PREFS, lang: 'es' } as never },
    });
    await userEvent.click(screen.getByRole('button', { name: 'English' }));
    // The toast is built while the optimistic language is still on screen.
    expect(await screen.findByRole('button', { name: 'Retry' })).toBeVisible();
    expect(screen.getByText(/Couldn't save the change/)).toBeVisible();
    expect(queryClient.getQueryData<typeof SIGNED_IN>(['session'])?.prefs?.lang).toBe('es');
    await waitFor(() => expect(i18n.language).toBe('es')); // and the UI follows the account back
  });
});
