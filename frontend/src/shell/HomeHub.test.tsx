import { screen, within } from '@testing-library/react';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { API, adminSession, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const launchers = async () => {
  await screen.findByRole('banner');
  const main = screen.getByRole('main');
  // The account panel beside the launchers has a link of its own; it is not a launcher.
  return within(main)
    .getAllByRole('link')
    .filter((link) => link.querySelector('[data-launcher-title]'));
};

describe('HomeHub (SHELL-6)', () => {
  it('shows six launchers to a member and no Price', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/' });
    const links = await launchers();
    expect(links.map((link) => link.querySelector('[data-launcher-title]')?.textContent)).toEqual([
      'Panel',
      'Sets',
      'Cartas',
      'Colección',
      'Mazos',
      'Perfil',
    ]);
    expect(screen.queryByRole('link', { name: /Precios/ })).not.toBeInTheDocument();
  });

  it('sends each launcher to its Jinja page with a plain anchor', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/' });
    const hrefs = (await launchers()).map((link) => link.getAttribute('href'));
    expect(hrefs).toEqual([
      '/riftbound/',
      '/riftbound/set',
      '/riftbound/card',
      '/riftbound/collection',
      '/riftbound/deck',
      '/riftbound/profile',
    ]);
  });

  it('adds Price for an admin', async () => {
    server.use(http.get(`${API}/auth/session`, () => adminSession()));
    await renderApp({ path: '/' });
    const links = await launchers();
    expect(links).toHaveLength(7);
    expect(links.at(-1)).toHaveAttribute('href', '/riftbound/price');
    expect(links.at(-1)).toHaveTextContent('Precios');
  });

  it('greets the user by name and offers the interface settings', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Hola, ada' })).toBeVisible();
    expect(document.title).toBe('Inicio · Rift Manager');
    const settings = await screen.findByRole('link', { name: /Personalizar la interfaz/ });
    expect(settings).toHaveAttribute('href', '/riftbound/app/account/interface');
  });

  it('speaks English with the English catalog', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/', lang: 'en' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Hello, ada' })).toBeVisible();
    const links = await launchers();
    expect(links.map((link) => link.querySelector('[data-launcher-title]')?.textContent)).toEqual([
      'Dashboard',
      'Sets',
      'Cards',
      'Collection',
      'Decks',
      'Profile',
    ]);
  });
});
