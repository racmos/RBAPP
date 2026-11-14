/** F9-i AC1 (S1, S2, S14): the account area is one place with sections: tabs below 1240 px,
    a sticky sidebar with the identity summary from 1240 px. */
import { join } from 'node:path';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import { up } from '@/lib/breakpoints';
import { SRC_DIR, readCss, rules } from '@/test/css';
import { API, NO_PREFS, USER, USER_TOKEN, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { ACCOUNT_SECTIONS } from './sections';

const LONG = { timeout: 10000 };

function signedIn(user: Partial<typeof USER> = {}) {
  server.use(
    http.get(`${API}/auth/session`, () =>
      Object.keys(user).length === 0
        ? signedInSession()
        : ok({
            authenticated: true,
            csrf_token: USER_TOKEN,
            user: { ...USER, ...user },
            prefs: NO_PREFS,
          }),
    ),
  );
}

async function open(path: string, width: number) {
  const app = await renderApp({ path, width });
  await screen.findByRole('heading', { level: 1 }, LONG);
  return app;
}

const sectionsNav = () => screen.getByRole('navigation', { name: 'Account sections' });
const sidebar = () => screen.queryByRole('complementary', { name: 'Account' });

describe('Account routes (F9-i S1)', () => {
  it('/account opens the profile', async () => {
    signedIn();
    const { where } = await renderApp({ path: '/account', width: 390 });
    await waitFor(() => expect(where()).toBe('/account/profile'), LONG);
    expect(await screen.findByRole('heading', { level: 1, name: 'Profile' }, LONG)).toBeVisible();
  }, 20000);

  it('an unknown section is the shell not-found page', async () => {
    signedIn();
    await renderApp({ path: '/account/nope', width: 390 });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Page not found' }, LONG),
    ).toBeVisible();
    expect(screen.getByRole('banner')).toBeVisible();
  }, 20000);

  it('the topbar account link opens the account area', async () => {
    signedIn();
    await open('/', 1280);
    expect(screen.getByRole('link', { name: "ada's account" })).toHaveAttribute(
      'href',
      '/riftbound/app/account',
    );
  }, 20000);
});

describe('Account sections (F9-i S2)', () => {
  it('lists the sections once, in order', () => {
    expect(ACCOUNT_SECTIONS.map((section) => [section.id, section.to])).toEqual([
      ['profile', '/account/profile'],
      ['interface', '/account/interface'],
    ]);
  });

  it.each([390, 1000, 1239])(
    'at %i px renders a row of tabs, no sidebar',
    async (width) => {
      signedIn();
      await open('/account/profile', width);
      const nav = sectionsNav();
      const links = within(nav).getAllByRole('link');
      expect(links.map((link) => link.textContent)).toEqual(['Profile', 'Interface']);
      expect(within(nav).getByRole('link', { name: 'Profile' })).toHaveAttribute(
        'aria-current',
        'page',
      );
      expect(within(nav).getByRole('link', { name: 'Interface' })).not.toHaveAttribute(
        'aria-current',
      );
      expect(sidebar()).toBeNull();
    },
    20000,
  );

  it('from 1240 px renders the sidebar with the identity summary and the section links', async () => {
    signedIn({ display_name: 'Ada L.' });
    await open('/account/profile', 1280);
    const aside = sidebar();
    expect(aside).not.toBeNull();
    const side = within(aside as HTMLElement);
    expect(side.getByText('Ada L.')).toBeVisible();
    expect(side.getByText('@ada')).toBeVisible();
    const nav = side.getByRole('navigation', { name: 'Account sections' });
    expect(within(nav).getByRole('link', { name: 'Profile' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    // one section navigation at a time
    expect(screen.getAllByRole('navigation', { name: 'Account sections' })).toHaveLength(1);
  }, 20000);

  it('the sidebar shows the username when there is no display name', async () => {
    signedIn();
    await open('/account/profile', 1600);
    const side = within(sidebar() as HTMLElement);
    expect(side.getByText('ada')).toBeVisible();
    expect(side.getByText('@ada')).toBeVisible();
  }, 20000);

  it('the sidebar avatar is the photo when the user has one', async () => {
    signedIn({ avatar_url: '/riftbound/api/v1/users/7/avatar?v=2' });
    await open('/account/profile', 1280);
    const img = (sidebar() as HTMLElement).querySelector('img');
    expect(img).toHaveAttribute('src', '/riftbound/api/v1/users/7/avatar?v=2&size=64');
  }, 20000);

  it.each([390, 1280])(
    'at %i px the interface section stays reachable',
    async (width) => {
      signedIn();
      const { where } = await open('/account/profile', width);
      await userEvent.click(within(sectionsNav()).getByRole('link', { name: 'Interface' }));
      expect(
        await screen.findByRole('heading', { level: 1, name: 'Interface' }, LONG),
      ).toBeVisible();
      expect(where()).toBe('/account/interface');
      expect(within(sectionsNav()).getByRole('link', { name: 'Interface' })).toHaveAttribute(
        'aria-current',
        'page',
      );
    },
    20000,
  );

  it('the sidebar is sticky and 264 px wide, the tabs scroll sideways', () => {
    const css = rules(readCss(join(SRC_DIR, 'account/AccountLayout.module.css')));
    const decl = (selector: string, prop: string, media?: string) =>
      css
        .filter(
          (rule) =>
            rule.selectors.includes(selector) &&
            (media
              ? rule.atRules.includes(`media ${media}`)
              : !rule.atRules.some((at) => at.startsWith('media'))),
        )
        .flatMap((rule) => rule.decls)
        .find((d) => d.prop === prop)?.value;
    expect(decl('.sidebar', 'position')).toBe('sticky');
    expect(decl('.sidebar', 'width')).toBe('264px');
    expect(decl('.tabs', 'overflow-x')).toBe('auto');
    expect(decl('.layout', 'grid-template-columns', up('xl'))).toBe('264px minmax(0, 1fr)');
  });
});

describe('Account area accessibility (F9-i S14)', () => {
  it.each([
    ['/account/profile', 390],
    ['/account/profile', 1280],
    ['/account/interface', 390],
    ['/account/interface', 1280],
  ])(
    '%s at %i px is axe clean',
    async (path, width) => {
      signedIn();
      const { container } = await open(path, width);
      if (path.endsWith('profile')) {
        await screen.findByRole('form', { name: 'Details' }, LONG);
      }
      expect(await axe(container)).toHaveNoViolations();
    },
    30000,
  );
});
