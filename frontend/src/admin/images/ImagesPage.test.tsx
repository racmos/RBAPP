import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { axe } from 'vitest-axe';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import type { AdminCard, AdminProduct } from '@/api/endpoints';
import { clearToasts, getToasts } from '@/components/ui/toastStore';
import { sleeves } from '@/test/fixtures/products';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };

function card(cardId: string, name: string, extra: Partial<AdminCard> = {}): AdminCard {
  return {
    set_id: 'OGN',
    card_id: cardId,
    key: `OGN-${cardId}`,
    name,
    domain: null,
    type: 'Rune',
    tags: null,
    energy: null,
    power: null,
    might: null,
    ability: null,
    rarity: 'Common',
    artist: null,
    image: null,
    image_url: null,
    image_src: null,
    has_image: false,
    ...extra,
  };
}

const RUNE = card('66', 'Fury Rune');
const LOST = card('67', 'Calm Rune', {
  image: 'ogn_67.png',
  image_src: '/riftbound/media/cards/ogn/ogn_67.png',
});
const SUMMARY = { cards: { missing: 2, total: 300 }, products: { missing: 1, total: 40 } };
const UPLOADED = {
  ...RUNE,
  image: 'ogn_66.webp',
  image_src: '/riftbound/media/cards/ogn/ogn_66.webp',
  has_image: true,
  previous: null,
  width: 640,
  height: 894,
  bytes: 87_040,
};

let append: MockInstance<FormData['append']>;
const createObjectURL = vi.fn(() => 'blob:preview-1');
const revokeObjectURL = vi.fn();

beforeEach(() => {
  createObjectURL.mockClear();
  // jsdom has no object URLs.
  Object.assign(URL, { createObjectURL, revokeObjectURL });
  append = vi.spyOn(FormData.prototype, 'append');
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  clearToasts();
});

type Calls = {
  cardQueries: URLSearchParams[];
  productQueries: URLSearchParams[];
  uploads: string[];
  undos: unknown[];
  finalized: unknown[];
};

function imagesApi({
  cards = [RUNE, LOST],
  products = [{ ...sleeves, image: null, has_image: false } as AdminProduct],
  upload = () => ok(UPLOADED),
}: {
  cards?: AdminCard[];
  products?: AdminProduct[];
  upload?: () => Response;
} = {}): Calls {
  const calls: Calls = {
    cardQueries: [],
    productQueries: [],
    uploads: [],
    undos: [],
    finalized: [],
  };
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/images/summary`, () => ok(SUMMARY)),
    http.get(`${API}/admin/overview`, () => ok({ catalog: { sets: 1, cards: 2 } })),
    http.get(`${API}/admin/sets`, () =>
      ok([
        {
          id: 'OGN',
          name: 'Origins',
          release_date: '2026-01-01',
          card_count: 2,
          declared_count: 2,
          window: 'monthly',
          next_run_at: null,
        },
      ]),
    ),
    http.get(`${API}/admin/cards`, ({ request }) => {
      calls.cardQueries.push(new URL(request.url).searchParams);
      return ok({ items: cards, meta: { page: 1, per_page: 50, total: cards.length, pages: 1 } });
    }),
    http.get(`${API}/admin/products`, ({ request }) => {
      calls.productQueries.push(new URL(request.url).searchParams);
      return ok({
        items: products,
        meta: { page: 1, per_page: 50, total: products.length, pages: 1 },
      });
    }),
    // jsdom's FormData cannot be read back by MSW in Node: the file is recorded on append.
    http.post(`${API}/admin/cards/:set/:id/image`, ({ params }) => {
      const [, file] = append.mock.calls.at(-1) as [string, File];
      calls.uploads.push(`${String(params.set)}-${String(params.id)}:${file.name}`);
      return upload();
    }),
    http.post(`${API}/admin/products/:id/image`, ({ params }) => {
      const [, file] = append.mock.calls.at(-1) as [string, File];
      calls.uploads.push(`product-${String(params.id)}:${file.name}`);
      return ok({
        ...products[0],
        image: `${String(params.id)}.webp`,
        image_src: `/riftbound/media/products/${String(params.id)}.webp`,
        has_image: true,
        previous: null,
        width: 640,
        height: 320,
        bytes: 2048,
      });
    }),
    http.post(`${API}/admin/images/undo`, async ({ request }) => {
      calls.undos.push(await request.json());
      return ok(RUNE);
    }),
    http.post(`${API}/admin/images/finalize`, async ({ request }) => {
      calls.finalized.push(await request.json());
      return ok({ deleted: true });
    }),
  );
  return calls;
}

function image(name = 'rune.png', size?: number, type = 'image/png'): File {
  const file = new File(['png-bytes'], name, { type });
  if (size !== undefined) Object.defineProperty(file, 'size', { value: size });
  return file;
}

const row = (name: string) => screen.getByRole('row', { name: new RegExp(name) });
const fileInputOf = (container: HTMLElement) =>
  container.querySelector('input[type="file"]') as HTMLInputElement;

async function pick(name: string, file: File) {
  const button = within(row(name)).getByRole('button', { name: `Choose a file for ${name}` });
  await userEvent.click(button);
  await userEvent.upload(fileInputOf(row(name)), file);
  return screen.findByRole('dialog', { name: `Image for ${name}` });
}

describe('ImagesPage (F13-h S1-S3)', () => {
  it('lists the cards without a usable image in a table with counters', async () => {
    const calls = imagesApi();
    const { container } = await renderApp({ path: '/admin/images', width: 1280 });
    const table = await screen.findByRole('table', { name: 'Cards without an image' }, LONG);
    expect(screen.getByRole('heading', { name: 'Images' })).toBeVisible();
    expect(await screen.findByText('2 of 300 without an image')).toBeVisible();
    const tabs = screen.getAllByRole('tab');
    expect(tabs.map((tab) => tab.textContent)).toEqual(['Cards2', 'Products1']);
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('2 of 300 without an image')).toBeVisible();
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((cell) => cell.textContent),
    ).toEqual(['Image', 'Name', 'Code', 'Set', 'File']);
    expect(within(row('Fury Rune')).getByText('No image')).toBeVisible();
    expect(within(row('Fury Rune')).getByText('OGN-66')).toBeVisible();
    expect(within(row('Calm Rune')).getByText('File missing')).toBeVisible();
    const query = calls.cardQueries.at(-1);
    expect(query?.get('image')).toBe('missing');
    expect(screen.getByRole('switch', { name: 'Include files missing on disk' })).toBeChecked();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);

  it('the switch off asks for the empty images only, the filters go to the request', async () => {
    const calls = imagesApi();
    await renderApp({ path: '/admin/images', width: 1280 });
    await screen.findByRole('table', { name: 'Cards without an image' }, LONG);
    await userEvent.click(screen.getByRole('switch', { name: 'Include files missing on disk' }));
    await waitFor(() => expect(calls.cardQueries.at(-1)?.get('image')).toBe('empty'));
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Set' }), 'OGN');
    await waitFor(() => expect(calls.cardQueries.at(-1)?.get('set')).toBe('OGN'));
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Per page' }), '200');
    await waitFor(() => expect(calls.cardQueries.at(-1)?.get('per_page')).toBe('200'));
  }, 30000);

  it('pick a file: preview and size first, then one upload, the row updates, Undo restores', async () => {
    const calls = imagesApi();
    await renderApp({ path: '/admin/images', width: 1280 });
    await screen.findByRole('table', { name: 'Cards without an image' }, LONG);
    const input = fileInputOf(row('Fury Rune'));
    expect(input).toHaveAttribute('accept', 'image/png,image/jpeg,image/webp');
    const dialog = await pick('Fury Rune', image('rune.png', 87_040));
    expect(within(dialog).getByRole('img', { name: 'Preview of rune.png' })).toHaveAttribute(
      'src',
      'blob:preview-1',
    );
    expect(within(dialog).getByText('rune.png · 85 KB')).toBeVisible();
    expect(calls.uploads).toEqual([]);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Upload' }));
    const undo = await screen.findByRole('button', { name: 'Undo' }, LONG);
    expect(calls.uploads).toEqual(['OGN-66:rune.png']);
    expect(
      screen.getByText('Image saved for Fury Rune: ogn_66.webp, 640 × 894 px, 85 KB.', {
        selector: '[data-toast] *',
      }),
    ).toBeVisible();
    expect(
      row('Fury Rune').querySelector('img[src="/riftbound/media/cards/ogn/ogn_66.webp"]'),
    ).not.toBeNull();
    await userEvent.click(undo);
    await waitFor(() =>
      expect(calls.undos).toEqual([
        { type: 'card', set_id: 'OGN', card_id: '66', image: 'ogn_66.webp', previous: null },
      ]),
    );
    expect(calls.finalized).toEqual([]);
  }, 30000);

  it('the previous file is finalized when the Undo toast goes away', async () => {
    const calls = imagesApi({
      cards: [LOST],
      upload: () =>
        ok({ ...UPLOADED, ...LOST, image: 'ogn_67.webp', previous: 'ogn_67.png', has_image: true }),
    });
    await renderApp({ path: '/admin/images', width: 1280 });
    await screen.findByRole('table', { name: 'Cards without an image' }, LONG);
    const dialog = await pick('Calm Rune', image('calm.png'));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Upload' }));
    await waitFor(() => expect(getToasts()).toHaveLength(1));
    act(() => {
      const [toast] = getToasts();
      toast.onExpire?.();
    });
    await waitFor(() =>
      expect(calls.finalized).toEqual([{ type: 'card', image: 'ogn_67.png', set_id: 'OGN' }]),
    );
  }, 30000);

  it('a refused upload shows the reason and keeps the dialog', async () => {
    imagesApi({
      upload: () =>
        failure(400, {
          error: 'Validation Error',
          message: 'Invalid request data',
          code: 'validation_error',
          details: [
            {
              field: 'file',
              message: 'image is too small',
              type: 'value_error',
              code: 'too_small',
              params: { min: 200 },
            },
          ],
        }),
    });
    await renderApp({ path: '/admin/images', width: 1280 });
    await screen.findByRole('table', { name: 'Cards without an image' }, LONG);
    const dialog = await pick('Fury Rune', image('tiny.png'));
    await userEvent.click(within(dialog).getByRole('button', { name: 'Upload' }));
    expect(
      await within(dialog).findByText(
        'The image is too small: its short side must be at least 200 px.',
      ),
    ).toBeVisible();
    expect(within(dialog).getByRole('alert')).toBeVisible();
  }, 30000);

  it('a file over 10 MB or not an image is refused in the browser', async () => {
    const calls = imagesApi();
    await renderApp({ path: '/admin/images', width: 1280 });
    await screen.findByRole('table', { name: 'Cards without an image' }, LONG);
    const dialog = await pick('Fury Rune', image('big.png', 10 * 1024 * 1024 + 1));
    expect(within(dialog).getByText('The file is too large (maximum 10 MB).')).toBeVisible();
    expect(within(dialog).getByRole('button', { name: 'Upload' })).toBeDisabled();
    expect(calls.uploads).toEqual([]);
  }, 30000);

  it('dropping an image on a row opens the same preview', async () => {
    imagesApi();
    await renderApp({ path: '/admin/images', width: 1280 });
    await screen.findByRole('table', { name: 'Cards without an image' }, LONG);
    fireEvent.drop(row('Fury Rune'), {
      dataTransfer: { files: [image('drop.webp', 10, 'image/webp')] },
    });
    expect(await screen.findByRole('dialog', { name: 'Image for Fury Rune' })).toBeVisible();
  }, 30000);

  it('the Products tab lists products, the kind filter goes to the request', async () => {
    const calls = imagesApi();
    await renderApp({ path: '/admin/images?tab=products', width: 1280 });
    const table = await screen.findByRole('table', { name: 'Products without an image' }, LONG);
    expect(within(table).getByText('Riftbound Sleeves')).toBeVisible();
    expect(screen.getByText('1 of 40 without an image')).toBeVisible();
    expect(calls.productQueries.at(-1)?.get('image')).toBe('missing');
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Kind' }), 'accessory');
    await waitFor(() => expect(calls.productQueries.at(-1)?.get('kind')).toBe('accessory'));
  }, 30000);

  it('a phone gets cards, not a table', async () => {
    imagesApi();
    const { container } = await renderApp({ path: '/admin/images', width: 390 });
    await screen.findByRole('button', { name: 'Choose a file for Fury Rune' }, LONG);
    expect(screen.queryByRole('table')).toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
