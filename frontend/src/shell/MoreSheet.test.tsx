import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { API, adminSession, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const openSheet = async (session: 'member' | 'admin' = 'member') => {
  server.use(
    http.get(`${API}/auth/session`, () =>
      session === 'admin' ? adminSession() : signedInSession(),
    ),
  );
  const app = await renderApp({ path: '/', width: 390 });
  const more = await screen.findByRole('button', { name: 'Más' });
  await userEvent.click(more);
  const sheet = screen.getByRole('dialog', { name: 'Más opciones' });
  return { app, more, sheet };
};

describe('MoreSheet (SHELL-4)', () => {
  it('lists Interface, the classic modules, language and logout, and no Admin', async () => {
    const { sheet } = await openSheet();
    expect(within(sheet).getByRole('link', { name: 'Interfaz' })).toHaveAttribute(
      'href',
      '/riftbound/app/account/interface',
    );
    for (const [name, href] of [
      ['Panel', '/riftbound/'],
      ['Sets', '/riftbound/set'],
      ['Cartas', '/riftbound/card'],
      ['Colección', '/riftbound/collection'],
      ['Mazos', '/riftbound/deck'],
      ['Perfil', '/riftbound/profile'],
    ] as const) {
      expect(within(sheet).getByRole('link', { name })).toHaveAttribute('href', href);
    }
    expect(within(sheet).getByRole('group', { name: 'Idioma' })).toBeVisible();
    expect(within(sheet).getByRole('button', { name: 'Cerrar sesión' })).toBeVisible();
    expect(within(sheet).queryByRole('link', { name: 'Administración' })).not.toBeInTheDocument();
  });

  it('shows an Admin entry to an admin, pointing at the legacy price page', async () => {
    const { sheet } = await openSheet('admin');
    expect(within(sheet).getByRole('link', { name: 'Administración' })).toHaveAttribute(
      'href',
      '/riftbound/price',
    );
  });

  it('Escape closes it and focus returns to "Más"', async () => {
    const { more } = await openSheet();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(more).toHaveFocus();
  });

  it('a backdrop click closes it', async () => {
    const { sheet, more } = await openSheet();
    await userEvent.click(sheet);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(more).toHaveFocus();
  });

  it('activating an entry closes the sheet and goes there', async () => {
    const { app } = await openSheet();
    await userEvent.click(screen.getByRole('link', { name: 'Interfaz' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await waitFor(() => expect(app.where()).toBe('/account/interface'));
  });

  it('switching language from the sheet changes the UI', async () => {
    const { sheet } = await openSheet();
    await userEvent.click(within(sheet).getByRole('button', { name: 'English' }));
    expect(await screen.findByRole('dialog', { name: 'More options' })).toBeVisible();
    expect(localStorage.getItem('rb_lang')).toBe('en');
  });

  it('logs out from the sheet', async () => {
    const { app } = await openSheet();
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cerrar sesión' }),
    );
    expect(await screen.findByLabelText('Usuario')).toBeVisible();
    expect(app.where()).toBe('/login');
  });

  it('leaves a slot for the install entry of the PWA unit', async () => {
    // Nothing is rendered for it yet; the entry must not leave an empty section behind.
    const { sheet } = await openSheet();
    expect(within(sheet).queryByText(/instalar/i)).not.toBeInTheDocument();
  });
});
