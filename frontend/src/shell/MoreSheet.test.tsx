import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { listen, resetInstallPrompt } from '@/pwa/installPrompt';
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

afterEach(() => resetInstallPrompt());

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

  it('has no install entry when the browser offers no way to install (PWA-6)', async () => {
    const { sheet } = await openSheet();
    expect(within(sheet).queryByText(/instalar/i)).not.toBeInTheDocument();
  });

  it('offers "Instalar app" once the browser fires beforeinstallprompt, and runs the prompt', async () => {
    const stopListening = listen();
    const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
      prompt: vi.fn(() => Promise.resolve()),
      userChoice: Promise.resolve({ outcome: 'accepted' as const }),
    });
    act(() => void window.dispatchEvent(event));
    const { sheet } = await openSheet();
    await userEvent.click(within(sheet).getByRole('button', { name: 'Instalar app' }));
    expect(event.prompt).toHaveBeenCalledTimes(1);
    stopListening();
  });
});
