import { join } from 'node:path';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { BREAKPOINTS, up } from '@/lib/breakpoints';
import { SRC_DIR, declsFor, readCss, rules } from '@/test/css';
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

const css = readCss(join(SRC_DIR, 'shell/Topbar.module.css'));
const base = (selector: string, prop: string) =>
  rules(css)
    .filter(
      (rule) =>
        rule.selectors.includes(selector) && !rule.atRules.some((at) => at.startsWith('media')),
    )
    .flatMap((rule) => rule.decls)
    .filter((decl) => decl.prop === prop)
    .at(-1)?.value;
const inMedia = (media: string, selector: string, prop: string) =>
  rules(css)
    .filter((rule) => rule.selectors.includes(selector) && rule.atRules.includes(`media ${media}`))
    .flatMap((rule) => rule.decls)
    .find((decl) => decl.prop === prop)?.value;

describe('Topbar fits from the desktop breakpoint up (owner feedback S18 f)', () => {
  it.each([1000, 1440])(
    'at %i px each link keeps its text as name and shows it as a tooltip',
    async (width) => {
      await renderSignedIn('/', width);
      const nav = screen.getByRole('navigation', { name: 'Navegación principal' });
      const link = within(nav).getByRole('link', { name: 'Colección' });
      expect(link).toHaveAttribute('title', 'Colección');
      expect(link.querySelector('svg')).not.toBeNull();
      expect(link.querySelector('[data-slot="label"]')).toHaveTextContent('Colección');
    },
  );

  it('shows the icons from md and the link texts only from 2xl', () => {
    expect(declsFor(css, '.icon')).not.toContainEqual({ prop: 'display', value: 'none' });
    // visually hidden (still read) below 2xl, laid out again from 2xl
    expect(base('.label', 'position')).toBe('absolute');
    expect(base('.label', 'clip-path')).toBe('inset(50%)');
    expect(BREAKPOINTS['2xl']).toBe(1600);
    expect(inMedia(up('2xl'), '.label', 'position')).toBe('static');
    expect(inMedia(up('2xl'), '.label', 'clip-path')).toBe('none');
  });

  it('never shrinks the navigation or the account area, and never wraps logout', () => {
    expect(declsFor(css, '.nav')).toContainEqual({ prop: 'flex', value: 'none' });
    expect(declsFor(css, '.right')).toContainEqual({ prop: 'flex', value: 'none' });
    expect(declsFor(css, '.logout')).toContainEqual({ prop: 'white-space', value: 'nowrap' });
    expect(declsFor(css, '.account')).toContainEqual({ prop: 'white-space', value: 'nowrap' });
  });

  it.each([1440, 1920])(
    'at %i px logout is an icon with its name and a tooltip (no text to wrap)',
    async (width) => {
      await renderSignedIn('/', width);
      const logout = screen.getByRole('button', { name: 'Cerrar sesión' });
      expect(logout).toHaveAttribute('title', 'Cerrar sesión');
      expect(logout.querySelector('svg')).not.toBeNull();
      expect(logout).toHaveTextContent('');
    },
  );

  it('keeps the 2xl room for the link texts: same link padding, install entry an icon', () => {
    // the labels take the room at 2xl, so nothing else grows there
    expect(inMedia(up('2xl'), '.link', 'padding')).toBeUndefined();
    expect(
      rules(css)
        .filter((rule) => rule.selectors.includes('.installText'))
        .flatMap((rule) => rule.decls)
        .filter((decl) => decl.prop === 'display'),
    ).toEqual([{ prop: 'display', value: 'none' }]);
  });

  it('keeps the placeholder clear of the "/" hint', () => {
    expect(declsFor(css, '.search input')).toContainEqual({ prop: 'padding-right', value: '36px' });
  });
});
