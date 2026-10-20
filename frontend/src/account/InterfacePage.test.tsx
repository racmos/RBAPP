import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http } from 'msw';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';
import type { Prefs } from '@/api/types';
import { API, NO_PREFS, failure, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';
import { setViewport } from '@/test/viewport';

const html = document.documentElement;

/** Signed in with `prefs`; records the PATCH bodies and answers like the API would. */
function setup(prefs: Partial<Prefs> = {}, patch?: () => Response | Promise<Response>) {
  const stored = { ...NO_PREFS, ...prefs };
  const bodies: Record<string, unknown>[] = [];
  server.use(
    http.get(`${API}/auth/session`, () => signedInSession(stored)),
    http.patch(`${API}/me/prefs`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      bodies.push(body);
      return patch ? patch() : ok({ prefs: { ...stored, ...body } });
    }),
  );
  return bodies;
}

const openPage = async (width = 1280, lang: 'es' | 'en' = 'es') => {
  const app = await renderApp({ path: '/account/interface', width, lang });
  await screen.findByRole('heading', { level: 1, name: lang === 'es' ? 'Interfaz' : 'Interface' });
  return app;
};

const group = (name: string) => screen.getByRole('radiogroup', { name });
const options = (name: string) =>
  within(group(name))
    .getAllByRole('radio')
    .map((radio) => (radio.closest('label') as HTMLElement).textContent);
const checked = (name: string) =>
  within(group(name))
    .getAllByRole('radio')
    .filter((radio) => (radio as HTMLInputElement).checked)
    .map((radio) => (radio.closest('label') as HTMLElement).textContent);

describe('InterfacePage controls (SHELL-7)', () => {
  it('has the five labelled controls with their options', async () => {
    setup();
    await openPage();
    expect(options('Densidad')).toEqual(['Auto', 'Compacta', 'Regular', 'Cómoda']);
    expect(options('Color de acento')).toEqual(['Cian', 'Naranja']);
    expect(options('Idioma')).toEqual(['Auto', 'Español', 'English']);
    expect(options('Vista de la colección')).toEqual(['Auto', 'Tabla', 'Cuadrícula']);
    const slider = screen.getByRole('slider', { name: 'Intensidad del fondo' });
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', '100');
  });

  it('shows Auto, the default accent and 100 % for a user with no stored preferences', async () => {
    setup();
    await openPage();
    expect(checked('Densidad')).toEqual(['Auto']);
    expect(checked('Color de acento')).toEqual(['Naranja']);
    expect(checked('Idioma')).toEqual(['Auto']);
    expect(checked('Vista de la colección')).toEqual(['Auto']);
    expect(screen.getByRole('slider')).toHaveValue('100');
    expect(screen.getByText('100%')).toBeVisible();
  });

  it('shows the stored values', async () => {
    setup({
      density: 'comfy',
      accent: 'cyan',
      bg_intensity: 40,
      lang: 'en',
      collection_view: 'grid',
    });
    await openPage(1280, 'en');
    expect(checked('Density')).toEqual(['Comfy']);
    expect(checked('Accent color')).toEqual(['Cyan']);
    expect(checked('Language')).toEqual(['English']);
    expect(checked('Collection view')).toEqual(['Grid']);
    expect(screen.getByRole('slider', { name: 'Background intensity' })).toHaveValue('40');
  });

  it('has the page title in the document', async () => {
    setup();
    await openPage();
    expect(document.title).toBe('Interfaz · Rift Manager');
  });
});

describe('InterfacePage saving (PREF-8)', () => {
  it('applies the accent at once and sends one PATCH with that field', async () => {
    const bodies = setup();
    await openPage();
    await userEvent.click(screen.getByRole('radio', { name: 'Cian' }));
    expect(html.dataset.accent).toBe('cyan'); // before any answer
    await waitFor(() => expect(bodies).toEqual([{ accent: 'cyan' }]));
    expect(JSON.parse(localStorage.getItem('rb_prefs_v1')!).accent).toBe('cyan');
  });

  it('reverts the value and shows an error toast when the save fails', async () => {
    const bodies = setup({ density: 'regular' }, async () => {
      await delay(150); // long enough to look at the optimistic state
      return failure(500);
    });
    await openPage();
    await userEvent.click(screen.getByRole('radio', { name: 'Cómoda' }));
    expect(html.dataset.density).toBe('comfy');
    expect(await screen.findByRole('button', { name: 'Reintentar' })).toBeVisible();
    const toasts = screen.getByRole('region', { name: 'Notificaciones' });
    expect(within(toasts).getByText(/No se pudo guardar/)).toBeVisible();
    await waitFor(() => expect(checked('Densidad')).toEqual(['Regular']));
    expect(html.hasAttribute('data-density')).toBe(false); // regular
    expect(bodies).toEqual([{ density: 'comfy' }]);
  });

  it('choosing Auto sends null', async () => {
    const bodies = setup({ density: 'comfy' });
    await openPage();
    await userEvent.click(within(group('Densidad')).getByRole('radio', { name: 'Auto' }));
    await waitFor(() => expect(bodies).toEqual([{ density: null }]));
    expect(html.hasAttribute('data-density')).toBe(false); // Auto on a desktop is regular
  });

  it('Auto density on a phone resolves to compact', async () => {
    setup({ density: 'comfy' });
    await openPage(390);
    await userEvent.click(within(group('Densidad')).getByRole('radio', { name: 'Auto' }));
    expect(html.dataset.density).toBe('compact');
  });

  it('the view control sends its value', async () => {
    const bodies = setup();
    await openPage();
    await userEvent.click(screen.getByRole('radio', { name: 'Cuadrícula' }));
    await waitFor(() => expect(bodies).toEqual([{ collection_view: 'grid' }]));
  });

  it('the language control changes the UI and saves to the account', async () => {
    const bodies = setup();
    const app = await openPage();
    await userEvent.click(within(group('Idioma')).getByRole('radio', { name: 'English' }));
    expect(app.i18n.language).toBe('en');
    expect(await screen.findByRole('heading', { level: 1, name: 'Interface' })).toBeVisible();
    expect(localStorage.getItem('rb_lang')).toBe('en');
    await waitFor(() => expect(bodies).toEqual([{ lang: 'en' }]));
  });

  it('language Auto sends null and forgets the device choice', async () => {
    localStorage.setItem('rb_lang', 'en');
    const bodies = setup({ lang: 'en' });
    await openPage(1280, 'en');
    await userEvent.click(within(group('Language')).getByRole('radio', { name: 'Auto' }));
    await waitFor(() => expect(bodies).toEqual([{ lang: null }]));
    expect(localStorage.getItem('rb_lang')).toBeNull();
  });
});

describe('InterfacePage background slider (SHELL-7, PREF-8)', () => {
  it('sets --bg-image-opacity to 0 immediately and turns the layer off', async () => {
    setup();
    await openPage();
    expect(html.style.getPropertyValue('--bg-image-opacity')).toBe('1');
    fireEvent.change(screen.getByRole('slider'), { target: { value: '0' } });
    expect(html.style.getPropertyValue('--bg-image-opacity')).toBe('0');
    expect(html.dataset.bg).toBe('off');
    expect(screen.getByText('0%')).toBeVisible();
  });

  it('sends one PATCH with the last value after the user stops', async () => {
    const bodies = setup();
    await openPage();
    const slider = screen.getByRole('slider');
    for (const value of [90, 80, 70, 60, 50, 40, 30, 20, 10, 5]) {
      fireEvent.change(slider, { target: { value: String(value) } });
    }
    expect(bodies).toEqual([]); // still inside the debounce window
    await waitFor(() => expect(bodies).toEqual([{ bg_intensity: 5 }]));
  });

  it('sends at once on pointerup', async () => {
    const bodies = setup();
    await openPage();
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '60' } });
    fireEvent.pointerUp(slider);
    await waitFor(() => expect(bodies).toEqual([{ bg_intensity: 60 }]));
  });
});

describe('InterfacePage preview (SHELL-7)', () => {
  it('shows the live preview at xl (1280 px) and above', async () => {
    setup();
    await openPage(1280);
    expect(screen.getByRole('region', { name: 'Vista previa' })).toBeVisible();
  });

  it('shows no preview at 390 px or below xl', async () => {
    setup();
    await openPage(390);
    expect(screen.queryByRole('region', { name: 'Vista previa' })).not.toBeInTheDocument();
    act(() => setViewport(1100));
    expect(screen.queryByRole('region', { name: 'Vista previa' })).not.toBeInTheDocument();
    act(() => setViewport(1240));
    expect(await screen.findByRole('region', { name: 'Vista previa' })).toBeVisible();
  });
});

describe('InterfacePage accessibility (SHELL-7, SHELL-9)', () => {
  it.each([390, 1280])('has no axe violations at %i px', async (width) => {
    setup();
    await openPage(width);
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
