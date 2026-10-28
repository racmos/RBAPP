import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { API, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

async function renderSignedIn(path: string, width: number) {
  server.use(http.get(`${API}/auth/session`, () => signedInSession()));
  const app = await renderApp({ path, width });
  await screen.findByRole('banner', {}, LONG);
  return app;
}

const globalSearch = () => screen.queryByRole('combobox', { name: 'Buscar cartas' });

describe('Topbar global card search (F2-k S6)', () => {
  it('renders the search box from 1240 px', async () => {
    await renderSignedIn('/', 1280);
    const box = await screen.findByRole('combobox', { name: 'Buscar cartas' }, LONG);
    expect(box).toHaveAttribute('placeholder', 'Buscar cartas…');
  });

  it.each([1239, 1000, 700])('does not render it at %i px', async (width) => {
    await renderSignedIn('/', width);
    expect(globalSearch()).toBeNull();
  });

  it('opens the chosen card on the detail route, remembering it came from the catalog', async () => {
    const { router, where } = await renderSignedIn('/', 1280);
    const user = userEvent.setup();
    await user.type(await screen.findByRole('combobox', { name: 'Buscar cartas' }), 'ember');
    await screen.findByRole('option', { name: /Ember Wisp/ }, LONG);
    await user.keyboard('{Enter}');
    await waitFor(() => expect(where()).toBe('/cards/OGN/12'), LONG);
    expect(router.state.location.state).toEqual({ fromCatalog: true });
  });

  it('focuses the box when "/" is pressed outside an editable field', async () => {
    await renderSignedIn('/', 1280);
    const box = await screen.findByRole('combobox', { name: 'Buscar cartas' }, LONG);
    expect(box).not.toHaveFocus();
    const notPrevented = fireEvent.keyDown(document.body, { key: '/' });
    expect(notPrevented).toBe(false); // preventDefault, so no "/" is typed into the box
    expect(box).toHaveFocus();
    expect(box).toHaveValue('');
  });

  it('leaves "/" alone inside an input', async () => {
    await renderSignedIn('/cards', 1280);
    const [catalogSearch] = await screen.findAllByRole('searchbox', {}, LONG);
    catalogSearch.focus();
    const notPrevented = fireEvent.keyDown(catalogSearch, { key: '/' });
    expect(notPrevented).toBe(true);
    expect(catalogSearch).toHaveFocus();
  }, 15000);

  it('ignores "/" with a modifier key', async () => {
    await renderSignedIn('/', 1280);
    const box = await screen.findByRole('combobox', { name: 'Buscar cartas' }, LONG);
    fireEvent.keyDown(document.body, { key: '/', ctrlKey: true });
    expect(box).not.toHaveFocus();
  });

  it('shows a "/" key hint that assistive technology skips', async () => {
    await renderSignedIn('/', 1280);
    await screen.findByRole('combobox', { name: 'Buscar cartas' }, LONG);
    const hint = screen.getByRole('banner').querySelector('kbd');
    expect(hint).toHaveTextContent('/');
    expect(hint).toHaveAttribute('aria-hidden', 'true');
  });

  it('has no axe violations at 1280 px', async () => {
    await renderSignedIn('/', 1280);
    await screen.findByRole('combobox', { name: 'Buscar cartas' }, LONG);
    expect(await axe(screen.getByRole('banner'))).toHaveNoViolations();
  });
});
