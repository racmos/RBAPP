import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';
import { API, adminSession, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

/** SHELL-9: the structure of the shell has no axe violations in either layout. */
describe('shell accessibility (SHELL-9)', () => {
  it('has no violations at 1280 px (topbar navigation)', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/', width: 1280 });
    await screen.findByRole('banner');
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations at 390 px (bottom navigation)', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/', width: 390 });
    await screen.findByRole('banner');
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations with the "Más" sheet open (member)', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: 'Más' }));
    expect(screen.getByRole('dialog', { name: 'Más opciones' })).toBeVisible();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations with the "Más" sheet open (admin)', async () => {
    server.use(http.get(`${API}/auth/session`, () => adminSession()));
    await renderApp({ path: '/', width: 390 });
    await userEvent.click(await screen.findByRole('button', { name: 'Más' }));
    expect(screen.getByRole('link', { name: 'Administración' })).toBeVisible();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it('has no violations on the 404 view and in English', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await renderApp({ path: '/nope', width: 1280, lang: 'en' });
    await screen.findByRole('heading', { name: 'Page not found' });
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
