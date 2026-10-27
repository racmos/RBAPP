import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import type { PricePoint } from '@/api/types';
import { API, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { cardDetail } from '@/test/fixtures/cards';

const LONG = { timeout: 10000 };

const pricePoints: PricePoint[] = Array.from({ length: 10 }, (_, i) => ({
  date: `2026-10-${16 + i}`,
  market: 1.1 + i * 0.02,
  low: 1.0 + i * 0.02,
  avg7: 1.08 + i * 0.02,
  avg30: 1.05 + i * 0.02,
  market_foil: 2.2 + i * 0.03,
}));

function signedInApi() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

function priceHandler(range: string, points: PricePoint[]) {
  return ok({
    range,
    currency: 'EUR',
    foilable: cardDetail.foilable,
    product_id: 123456,
    points,
  });
}

describe('CatalogPreview (F2-i S5)', () => {
  it('shows the preview panel at 1680 px and selects the first card by default', async () => {
    signedInApi();
    server.use(
      http.get(`${API}/cards/:setId/:cardId/prices`, ({ request }) => {
        const url = new URL(request.url);
        return priceHandler(url.searchParams.get('range') ?? '90d', pricePoints);
      }),
    );
    await renderApp({ path: '/cards', width: 1680 });
    const preview = await screen.findByTestId('catalog-preview', {}, LONG);
    await screen.findByRole('heading', { name: /Ayla/ }, LONG);
    expect(preview).toHaveTextContent(/Ayla/);
    const first = screen.getByRole('button', { name: /Ayla/ });
    expect(first).toHaveAttribute('aria-pressed', 'true');
  }, 15000);

  it('selects another tile with replace and updates the preview', async () => {
    signedInApi();
    server.use(
      http.get(`${API}/cards/:setId/:cardId/prices`, ({ request }) => {
        const url = new URL(request.url);
        return priceHandler(url.searchParams.get('range') ?? '90d', pricePoints);
      }),
    );
    const { where } = await renderApp({ path: '/cards', width: 1680 });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    const tile = screen.getByText('Ember Wisp').closest('button')!;
    await userEvent.click(tile);
    await waitFor(() => expect(where()).toMatch(/selected=OGN-12/), LONG);
    expect(await screen.findByText('Ember Wisp', {}, LONG)).toBeVisible();
  });

  it('loads table at 1680', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1680 });
    expect(await screen.findByRole('table', {}, { timeout: 10000 })).toBeVisible();
  }, 15000);

  it('shows market and foil prices plus the 30-day sparkline for a foilable card', async () => {
    signedInApi();
    server.use(
      http.get(`${API}/cards/:setId/:cardId/prices`, ({ request }) => {
        const url = new URL(request.url);
        return priceHandler(url.searchParams.get('range') ?? '90d', pricePoints);
      }),
    );
    await renderApp({ path: '/cards?selected=OGN-79', width: 1680 });
    await screen.findByRole('heading', { name: /Ayla/ }, LONG);
    const preview = screen.getByTestId('catalog-preview');
    expect(preview).toHaveTextContent('1,21 €');
    expect(preview).toHaveTextContent('2,50 €');
    await waitFor(() => expect(preview.querySelector('svg[role="img"]')).toBeInTheDocument(), LONG);
  }, 15000);

  it('does not show a foil price for a non-foilable card', async () => {
    signedInApi();
    server.use(
      http.get(`${API}/cards/:setId/:cardId/prices`, ({ request }) => {
        const url = new URL(request.url);
        return priceHandler(url.searchParams.get('range') ?? '90d', pricePoints);
      }),
    );
    await renderApp({ path: '/cards?selected=OGN-r01', width: 1680 });
    await screen.findByRole('heading', { name: /Fury Rune/ }, LONG);
    const preview = screen.getByTestId('catalog-preview');
    expect(preview).not.toHaveTextContent('2,50 €');
  }, 15000);

  it('has a link to open the detail modal', async () => {
    signedInApi();
    server.use(
      http.get(`${API}/cards/:setId/:cardId/prices`, ({ request }) => {
        const url = new URL(request.url);
        return priceHandler(url.searchParams.get('range') ?? '90d', []);
      }),
    );
    await renderApp({ path: '/cards?selected=OGN-79', width: 1680 });
    await screen.findByRole('heading', { name: /Ayla/ }, LONG);
    const link = await screen.findByRole('link', { name: /ficha completa/ }, LONG);
    expect(link).toHaveAttribute('href', '/riftbound/app/cards/OGN/79?selected=OGN-79');
  }, 15000);

  it('hides the preview in table view', async () => {
    window.localStorage.setItem('rb_cards_view', 'table');
    signedInApi();
    await renderApp({ path: '/cards', width: 1680 });
    expect(await screen.findByRole('table', {}, LONG)).toBeVisible();
    expect(screen.queryByTestId('catalog-preview')).not.toBeInTheDocument();
  });

  it('is axe clean at 1680 px with the preview open', async () => {
    signedInApi();
    server.use(
      http.get(`${API}/cards/:setId/:cardId/prices`, ({ request }) => {
        const url = new URL(request.url);
        return priceHandler(url.searchParams.get('range') ?? '90d', pricePoints);
      }),
    );
    const { container } = await renderApp({ path: '/cards?selected=OGN-79', width: 1680 });
    await screen.findByRole('heading', { name: /Ayla/ }, LONG);
    expect(await axe(container)).toHaveNoViolations();
  }, 15000);
});
