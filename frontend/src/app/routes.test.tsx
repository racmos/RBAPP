import { screen } from '@testing-library/react';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { API, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { cardDetail } from '@/test/fixtures/cards';

const LONG = { timeout: 10000 };

function signedInApi() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

describe('createAppRoutes /cards (F2-h S6, S13)', () => {
  it('renders the card detail page at 390 px, axe clean', async () => {
    signedInApi();
    const { container } = await renderApp({ path: '/cards/OGN/79', width: 390 });
    expect(
      await screen.findByRole('heading', { level: 1, name: cardDetail.name }, LONG),
    ).toBeVisible();
    expect(await axe(container)).toHaveNoViolations();
  });

  it('renders the catalog and detail modal at 1280 px, axe clean', async () => {
    signedInApi();
    const { container } = await renderApp({ path: '/cards/OGN/79', width: 1280 });
    expect(await screen.findByRole('dialog', undefined, LONG)).toBeVisible();
    expect(await screen.findByText(/Origen · #79/, {}, LONG)).toBeVisible();
    const modal = document.querySelector('[data-presentation="modal"]');
    expect(modal).toBeTruthy();
    expect(modal).toHaveTextContent(cardDetail.name);
    expect(await axe(container)).toHaveNoViolations();
  });
});
