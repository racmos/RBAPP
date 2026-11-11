import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/renderApp';
import { installWishlists, signedIn } from '@/test/wishlists';

const LONG = { timeout: 10000 };

describe.each([390, 1280])('Collection | Wishlists tabs at %i px (F3-j)', (width) => {
  it('the collection page links to the wishlists and back', async () => {
    signedIn();
    installWishlists();
    const { where } = await renderApp({ path: '/collection', width });
    await screen.findByRole('button', { name: /Ayla/ }, LONG);
    const tabs = screen.getByRole('navigation', { name: 'Collection sections' });
    expect(within(tabs).getByRole('link', { name: 'Collection' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    await userEvent.click(within(tabs).getByRole('link', { name: 'Wishlists' }));
    await waitFor(() => expect(where()).toBe('/collection/wishlists'), LONG);
    expect(await screen.findByRole('heading', { level: 1, name: 'Wishlists' }, LONG)).toBeVisible();
  }, 20000);
});

describe('main navigation on a wishlist route (F3-j)', () => {
  it('keeps Collection marked as the current section', async () => {
    signedIn();
    installWishlists();
    await renderApp({ path: '/collection/wishlists', width: 1280 });
    await screen.findByRole('heading', { level: 1, name: 'Wishlists' }, LONG);
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    expect(within(nav).getByRole('link', { name: 'Collection' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(nav).getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current');
  }, 20000);
});
