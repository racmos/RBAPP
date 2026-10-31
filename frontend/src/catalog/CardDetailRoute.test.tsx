import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { Outlet } from 'react-router';
import type { RouteObject } from 'react-router';
import { API, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { cardDetail } from '@/test/fixtures/cards';
import { CardDetailRoute } from './CardDetailRoute';
import type { CardDetailOutletContext } from './context';

const LONG = { timeout: 10000 };

function signedInApi() {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
}

function ModalLayout({ onClose }: { onClose: () => void }) {
  const context: CardDetailOutletContext = {
    presentation: 'modal',
    siblings: [
      { setId: 'OGN', cardId: '78' },
      { setId: 'OGN', cardId: '79' },
      { setId: 'OGN', cardId: '80' },
    ],
    onClose,
  };
  return (
    <div>
      <Outlet context={context} />
    </div>
  );
}

const modalRoute = (onClose: () => void): RouteObject => ({
  path: '/test-modal',
  Component: () => <ModalLayout onClose={onClose} />,
  children: [{ path: ':setId/:cardId', Component: CardDetailRoute }],
});

describe('CardDetailRoute (F2-f S4-S6, S11)', () => {
  it('renders the page at /cards/OGN/79', async () => {
    signedInApi();
    await renderApp({ path: '/cards/OGN/79', width: 390 });
    expect(
      await screen.findByRole('heading', { level: 1, name: cardDetail.name }, LONG),
    ).toBeVisible();
  });

  it('shows three columns at 1280 px', async () => {
    signedInApi();
    await renderApp({
      path: '/test-page/OGN/79',
      width: 1280,
      extraRoutes: () => [{ path: '/test-page/:setId/:cardId', Component: CardDetailRoute }],
    });
    await screen.findByRole('heading', { level: 1, name: cardDetail.name }, LONG);
    expect(document.querySelector('[data-presentation="page"]')).toBeVisible();
  });

  it('opens as a modal with prev/next and disabled ends', async () => {
    signedInApi();
    const onClose = vi.fn();
    await renderApp({
      path: '/test-modal/OGN/78',
      width: 1280,
      extraRoutes: () => [modalRoute(onClose)],
    });
    expect(await screen.findByRole('dialog', undefined, LONG)).toBeVisible();
    const prev = screen.getByRole('button', { name: 'Previous card' });
    const next = screen.getByRole('button', { name: 'Next card' });
    expect(prev).toBeVisible();
    expect(next).toBeVisible();
    expect(prev).toBeDisabled();
    expect(next).toBeEnabled();

    await userEvent.click(next);
    await waitFor(
      () => expect(screen.getByRole('button', { name: 'Previous card' })).toBeEnabled(),
      LONG,
    );
  });

  it('navigates to next and previous with buttons', async () => {
    signedInApi();
    const onClose = vi.fn();
    const { where } = await renderApp({
      path: '/test-modal/OGN/79',
      width: 1280,
      extraRoutes: () => [modalRoute(onClose)],
    });
    await screen.findByRole('dialog', undefined, LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Next card' }));
    await waitFor(() => expect(where()).toBe('/test-modal/OGN/80'), LONG);
    await userEvent.click(screen.getByRole('button', { name: 'Previous card' }));
    await waitFor(() => expect(where()).toBe('/test-modal/OGN/79'), LONG);
  });

  it('navigates with arrow keys', async () => {
    signedInApi();
    const onClose = vi.fn();
    const { where } = await renderApp({
      path: '/test-modal/OGN/79',
      width: 1280,
      extraRoutes: () => [modalRoute(onClose)],
    });
    await screen.findByRole('dialog', undefined, LONG);
    await userEvent.keyboard('{ArrowRight}');
    await waitFor(() => expect(where()).toBe('/test-modal/OGN/80'), LONG);
    await userEvent.keyboard('{ArrowLeft}');
    await waitFor(() => expect(where()).toBe('/test-modal/OGN/79'), LONG);
  });

  it('calls onClose when Esc is pressed in modal', async () => {
    signedInApi();
    const onClose = vi.fn();
    await renderApp({
      path: '/test-modal/OGN/79',
      width: 1280,
      extraRoutes: () => [modalRoute(onClose)],
    });
    await screen.findByRole('dialog', undefined, LONG);
    await userEvent.keyboard('{Escape}');
    await waitFor(() => expect(onClose).toHaveBeenCalled(), LONG);
  });

  it('shows a 404 empty state', async () => {
    signedInApi();
    server.use(
      http.get(`${API}/cards/:setId/:cardId`, () => failure(404, { message: 'Not found' })),
    );
    await renderApp({ path: '/cards/OGN/NOPE', width: 390 });
    expect(await screen.findByText('Card not found', {}, LONG)).toBeVisible();
    expect(screen.getByText('The link may be old or the card may no longer exist.')).toBeVisible();
  });

  it('shows a loading skeleton while the card loads', async () => {
    signedInApi();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get(`${API}/cards/:setId/:cardId`, async () => {
        await gate;
        return ok(cardDetail);
      }),
    );
    await renderApp({ path: '/cards/OGN/79', width: 390 });
    expect(await screen.findByTestId('card-detail-loading', {}, LONG)).toHaveAttribute(
      'aria-busy',
      'true',
    );
    release();
    expect(
      await screen.findByRole('heading', { level: 1, name: cardDetail.name }, LONG),
    ).toBeVisible();
  });

  it('shows an error state with retry', async () => {
    signedInApi();
    let failing = true;
    server.use(
      http.get(`${API}/cards/:setId/:cardId`, () =>
        failing ? failure(500, { message: 'boom' }) : ok(cardDetail),
      ),
    );
    await renderApp({ path: '/cards/OGN/79', width: 390 });
    expect(await screen.findByRole('alert', undefined, LONG)).toBeVisible();
    failing = false;
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(
      await screen.findByRole('heading', { level: 1, name: cardDetail.name }, LONG),
    ).toBeVisible();
  });
});
