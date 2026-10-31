import { join } from 'node:path';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { I18nextProvider } from 'react-i18next';
import { describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { createI18n } from '@/i18n';
import { SRC_DIR, declsFor, readCss } from '@/test/css';
import { aylaGroup, emberGroup, runeGroup } from '@/test/fixtures/collection';
import { CollectionItem } from './CollectionItem';

async function renderItem(group = aylaGroup, variant: 'tile' | 'row' = 'tile', onOpen = vi.fn()) {
  const i18n = await createI18n();
  const view = render(
    <I18nextProvider i18n={i18n}>
      <CollectionItem group={group} variant={variant} playsetSize={3} onOpen={onOpen} />
    </I18nextProvider>,
  );
  return { ...view, onOpen };
}

describe('CollectionItem (F3-g S5)', () => {
  it('shows quantity, name, printing and value', async () => {
    await renderItem();
    expect(screen.getByText('×4')).toBeVisible();
    expect(screen.getByText("Ayla, Fury's Champion")).toBeVisible();
    expect(screen.getByText('OGN · #79')).toBeVisible();
    expect(screen.getByText('4.84 €')).toBeVisible();
  });

  it('marks foil groups and not the others', async () => {
    const { unmount } = await renderItem(emberGroup);
    expect(screen.getByText('Foil')).toBeVisible();
    unmount();
    await renderItem(aylaGroup);
    expect(screen.queryByText('Foil')).toBeNull();
  });

  it('tags the copies on sale only when there are some', async () => {
    const { unmount } = await renderItem(aylaGroup);
    expect(screen.getByText('On sale: 2')).toBeVisible();
    unmount();
    await renderItem(emberGroup);
    expect(screen.queryByText(/On sale/)).toBeNull();
  });

  it('writes the playset shortage as text and outlines the item', async () => {
    const { container } = await renderItem(aylaGroup);
    expect(screen.getByText('Playset incomplete (2/3)')).toBeVisible();
    expect(container.querySelector('button')?.className).toMatch(/short/);
  });

  it('shows nothing about the playset for a complete or unmarked card', async () => {
    const { container } = await renderItem(emberGroup);
    expect(screen.queryByText(/Playset/)).toBeNull();
    expect(container.querySelector('button')?.className).not.toMatch(/short/);
  });

  it('shows a dash for a group without a price', async () => {
    await renderItem(runeGroup);
    expect(screen.getByText('—')).toBeVisible();
  });

  it('opens the group with its key on click', async () => {
    const { onOpen } = await renderItem();
    await userEvent.click(screen.getByRole('button'));
    expect(onOpen).toHaveBeenCalledWith('OGN-79:N');
  });

  it('is the same data as a list row', async () => {
    await renderItem(aylaGroup, 'row');
    expect(screen.getByText('Playset incomplete (2/3)')).toBeVisible();
    expect(screen.getByText('4.84 €')).toBeVisible();
  });

  it('shows the playset state and the copies on sale on a tile', async () => {
    await renderItem(aylaGroup, 'tile');
    expect(screen.getByText('Playset incomplete (2/3)')).toBeVisible();
    expect(screen.getByText('On sale: 2')).toBeVisible();
  });

  it('has no axe violations', async () => {
    const { container } = await renderItem();
    expect(await axe(container)).toHaveNoViolations();
  });
});

const itemCss = readCss(join(SRC_DIR, 'collection/CollectionItem.module.css'));
const pageCss = readCss(join(SRC_DIR, 'collection/CollectionPage.module.css'));
const desktopCss = readCss(join(SRC_DIR, 'collection/CollectionDesktop.module.css'));
const decl = (css: string, selector: string, prop: string) =>
  declsFor(css, selector).find((item) => item.prop === prop)?.value;

describe('CollectionItem sizes (owner feedback S10)', () => {
  it('puts the sale and playset notes on one status line', async () => {
    const { container } = await renderItem(aylaGroup);
    const status = container.querySelector('[data-slot="status"]');
    expect(status?.textContent).toContain('On sale: 2');
    expect(status?.textContent).toContain('Playset incomplete (2/3)');
  });

  it('gives a list row its own quantity column instead of a badge on the thumbnail', async () => {
    const { container } = await renderItem(aylaGroup, 'row');
    const qty = container.querySelector('[data-slot="qty"]');
    expect(qty?.textContent).toBe('×4');
    expect(qty?.closest('[data-slot="art"]')).toBeNull();
  });

  it('keeps the quantity badge on the tile image', async () => {
    const { container } = await renderItem(aylaGroup, 'tile');
    expect(container.querySelector('[data-slot="art"] [data-slot="qty"]')?.textContent).toBe('×4');
  });

  it('makes every grid row the same height and every tile fill its cell', () => {
    for (const css of [pageCss, desktopCss]) {
      expect(decl(css, '.grid', 'grid-auto-rows')).toBe('1fr');
    }
    expect(decl(itemCss, '.tile', 'height')).toBe('100%');
    expect(decl(itemCss, '.tile .art', 'width')).toBe('100%');
  });

  it('lays a list row out in fixed columns: thumbnail, text, quantity, value', () => {
    expect(decl(itemCss, '.row', 'display')).toBe('grid');
    expect(decl(itemCss, '.row', 'grid-template-columns')).toBe('44px minmax(0, 1fr) 44px 76px');
  });

  it('keeps each text line to one line with an ellipsis', () => {
    for (const selector of ['.name', '.meta', '.status']) {
      expect(decl(itemCss, selector, 'white-space')).toBe('nowrap');
      expect(decl(itemCss, selector, 'text-overflow')).toBe('ellipsis');
    }
  });
});
