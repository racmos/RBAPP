import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { listen, resetInstallPrompt } from '@/pwa/installPrompt';
import { API, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { setViewport } from '@/test/viewport';

const signedIn = () => server.use(http.get(`${API}/auth/session`, () => signedInSession()));

const open = async (width: number, lang: 'es' | 'en' = 'es') => {
  signedIn();
  const app = await renderApp({ path: '/', width, lang });
  await screen.findByRole('banner'); // the shell, not the loading screen
  return app;
};

describe('AppShell at 1280 px (SHELL-1, SHELL-2)', () => {
  it('has exactly one main, one banner and one navigation', async () => {
    await open(1280);
    expect(screen.getAllByRole('main')).toHaveLength(1);
    expect(screen.getAllByRole('banner')).toHaveLength(1);
    expect(screen.getAllByRole('navigation')).toHaveLength(1);
  });

  it('makes "skip to content" the first tab stop and it moves focus to main', async () => {
    await open(1280);
    await userEvent.tab();
    const skip = screen.getByRole('link', { name: 'Saltar al contenido' });
    expect(skip).toHaveFocus();
    await userEvent.keyboard('{Enter}');
    expect(screen.getByRole('main')).toHaveFocus();
  });

  it('has no bottom navigation and no bottom padding marker', async () => {
    await open(1280);
    expect(screen.queryByRole('button', { name: 'Más' })).not.toBeInTheDocument();
    expect(screen.getByRole('main')).not.toHaveAttribute('data-botnav');
  });

  it('shows the wordmark, not the mark alone, linking home', async () => {
    await open(1280);
    const banner = screen.getByRole('banner');
    const brand = within(banner).getByRole('img', { name: 'Rift Manager' });
    expect(brand.getAttribute('src')).toContain('wordmark');
    expect(within(banner).getAllByRole('img', { name: 'Rift Manager' })).toHaveLength(1);
    expect(within(banner).getByRole('link', { name: 'Rift Manager' })).toHaveAttribute(
      'href',
      '/riftbound/app',
    );
  });

  it('lists the entries of the registry for a member (no Price)', async () => {
    await open(1280);
    const nav = screen.getByRole('navigation', { name: 'Navegación principal' });
    expect(
      within(nav)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Inicio', 'Panel', 'Sets', 'Cartas', 'Colección', 'Mazos']);
  });

  it('links legacy entries as plain anchors to the Jinja pages', async () => {
    await open(1280);
    const nav = screen.getByRole('navigation');
    expect(within(nav).getByRole('link', { name: 'Colección' })).toHaveAttribute(
      'href',
      '/riftbound/collection',
    );
    expect(within(nav).getByRole('link', { name: 'Panel' })).toHaveAttribute('href', '/riftbound/');
  });

  it('marks the current entry with aria-current="page"', async () => {
    await open(1280);
    const nav = screen.getByRole('navigation');
    expect(within(nav).getByRole('link', { name: 'Inicio' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(nav).getByRole('link', { name: 'Cartas' })).not.toHaveAttribute('aria-current');
  });

  it('has the ES/EN toggle, the avatar with initials and the logout button', async () => {
    await open(1280);
    const banner = screen.getByRole('banner');
    expect(within(banner).getByRole('group', { name: 'Idioma' })).toBeVisible();
    const account = within(banner).getByRole('link', { name: 'Cuenta de ada' });
    expect(account).toHaveAttribute('href', '/riftbound/app/account/interface');
    expect(account).toHaveTextContent('AD');
    expect(within(banner).getByRole('button', { name: 'Cerrar sesión' })).toBeVisible();
  });

  it('shows Price to an admin', async () => {
    server.use(
      http.get(`${API}/auth/session`, async () =>
        (await import('@/test/msw/handlers')).adminSession(),
      ),
    );
    await renderApp({ path: '/', width: 1280 });
    const nav = await screen.findByRole('navigation');
    expect(within(nav).getByRole('link', { name: 'Precios' })).toHaveAttribute(
      'href',
      '/riftbound/price',
    );
  });

  it('translates the shell when the language changes', async () => {
    await open(1280, 'en');
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    expect(within(nav).getByRole('link', { name: 'Collection' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeVisible();
  });
});

describe('AppShell install entry on the desktop topbar (PWA-6)', () => {
  afterEach(() => resetInstallPrompt());

  it('has no install button until the browser offers the install', async () => {
    await open(1280);
    expect(screen.queryByRole('button', { name: 'Instalar app' })).not.toBeInTheDocument();
  });

  it('shows "Instalar app" in the banner once it does, and runs the saved prompt', async () => {
    const stopListening = listen();
    const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
      prompt: vi.fn(() => Promise.resolve()),
      userChoice: Promise.resolve({ outcome: 'accepted' as const }),
    });
    await open(1280);
    act(() => void window.dispatchEvent(event));
    const banner = screen.getByRole('banner');
    await userEvent.click(within(banner).getByRole('button', { name: 'Instalar app' }));
    expect(event.prompt).toHaveBeenCalledTimes(1);
    stopListening();
  });
});

describe('AppShell at 390 px (SHELL-2, SHELL-3)', () => {
  it('shows the mark alone and no navigation list in the topbar', async () => {
    await open(390);
    const banner = screen.getByRole('banner');
    const brand = within(banner).getByRole('img', { name: 'Rift Manager' });
    expect(brand.getAttribute('src')).not.toContain('wordmark');
    expect(within(banner).queryByRole('navigation')).not.toBeInTheDocument();
    expect(within(banner).queryByRole('link', { name: 'Sets' })).not.toBeInTheDocument();
  });

  it('has a bottom navigation with at most five items, the last being "Más"', async () => {
    await open(390);
    const nav = screen.getByRole('navigation');
    const items = within(nav).getAllByRole('listitem');
    expect(items.length).toBeLessThanOrEqual(5);
    expect(items.map((item) => item.textContent)).toEqual([
      'Inicio',
      'Cartas',
      'Colección',
      'Mazos',
      'Más',
    ]);
    expect(within(items.at(-1)!).getByRole('button', { name: 'Más' })).toBeVisible();
    expect(screen.getAllByRole('navigation')).toHaveLength(1);
  });

  it('marks the active item with aria-current="page" and marks main for bottom padding', async () => {
    await open(390);
    const nav = screen.getByRole('navigation');
    expect(within(nav).getByRole('link', { name: 'Inicio' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(nav).getByRole('link', { name: 'Mazos' })).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('main')).toHaveAttribute('data-botnav');
  });

  it('keeps a logout button with its name in the topbar', async () => {
    await open(390);
    const banner = screen.getByRole('banner');
    const logout = within(banner).getByRole('button', { name: 'Cerrar sesión' });
    expect(logout).toBeVisible();
    expect(logout).not.toHaveTextContent('Cerrar sesión'); // icon only: the name is not visible text
  });

  it('has no ES/EN toggle in the topbar (it lives in the "Más" sheet)', async () => {
    await open(390);
    expect(
      within(screen.getByRole('banner')).queryByRole('group', { name: 'Idioma' }),
    ).not.toBeInTheDocument();
  });
});

describe('AppShell responds to the viewport (SHELL-3)', () => {
  it('has no bottom navigation at 1024 px', async () => {
    await open(1024);
    expect(screen.queryByRole('button', { name: 'Más' })).not.toBeInTheDocument();
    expect(
      within(screen.getByRole('navigation')).getByRole('link', { name: 'Sets' }),
    ).toBeVisible();
  });

  it('swaps top and bottom navigation when the viewport crosses 860 px', async () => {
    await open(1280);
    expect(screen.getByRole('link', { name: 'Sets' })).toBeVisible();
    act(() => setViewport(859));
    expect(await screen.findByRole('button', { name: 'Más' })).toBeVisible();
    expect(screen.queryByRole('link', { name: 'Sets' })).not.toBeInTheDocument();
    act(() => setViewport(860));
    expect(await screen.findByRole('link', { name: 'Sets' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Más' })).not.toBeInTheDocument();
  });
});
