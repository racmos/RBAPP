import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import { clearToasts } from '@/components/ui/toastStore';
import { exportCsv } from '@/test/fixtures/collection';
import { API, NO_PREFS, failure, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderApp } from '@/test/renderApp';

const LONG = { timeout: 10000 };
const MB2 = 2 * 1024 * 1024;

type Sent = { path: string; body: Record<string, unknown> };
const sent: Sent[] = [];

beforeEach(() => {
  clearToasts();
  sent.length = 0;
  server.use(http.get(`${API}/auth/session`, () => signedInSession(NO_PREFS)));
  server.events.on('request:start', async ({ request }) => {
    const path = new URL(request.url).pathname.replace(API, '');
    if (!path.startsWith('/collection/import')) return;
    sent.push({ path, body: (await request.clone().json()) as Record<string, unknown> });
  });
});

afterEach(() => {
  server.events.removeAllListeners();
  vi.restoreAllMocks();
});

async function openWizard(width = 1280) {
  const rendered = await renderApp({ path: '/collection/import', width });
  expect(await screen.findByRole('heading', { name: 'Importar colección' }, LONG)).toBeVisible();
  return rendered;
}

const current = () =>
  within(screen.getByRole('list', { name: 'Importar colección' }))
    .getAllByRole('listitem')
    .find((item) => item.getAttribute('aria-current') === 'step');

async function pasteAndReview(text = exportCsv) {
  await userEvent.click(screen.getByRole('textbox', { name: 'O pega aquí el contenido' }));
  await userEvent.paste(text);
  await userEvent.click(screen.getByRole('button', { name: 'Revisar' }));
  await screen.findByText(
    'Correctas: 1 · Con avisos: 1 · Con errores: 1 · Cartas distintas: 2',
    {},
    LONG,
  );
}

async function toModeStep() {
  await pasteAndReview();
  await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
  await screen.findByRole('group', { name: 'Modo' });
}

describe('ImportWizard step 1 (F3-i S2)', () => {
  it('has four steps, the first one current, and the RBAPP hint', async () => {
    await openWizard();
    const steps = within(screen.getByRole('list', { name: 'Importar colección' })).getAllByRole(
      'listitem',
    );
    expect(steps.map((step) => step.textContent)).toEqual([
      '1Fichero',
      '2Revisión',
      '3Modo',
      '4Resultado',
    ]);
    expect(current()).toHaveTextContent('Fichero');
    expect(screen.getByLabelText('Fichero CSV en formato RBAPP')).toHaveAttribute('accept', '.csv');
    expect(
      screen.getByText('Por ahora solo se admite el formato RBAPP (el que genera «Exportar»).'),
    ).toBeVisible();
  }, 15000);

  it('sends the pasted text to the preview', async () => {
    await openWizard();
    await pasteAndReview();
    expect(sent).toEqual([{ path: '/collection/import/preview', body: { text: exportCsv } }]);
    expect(current()).toHaveTextContent('Revisión');
  }, 20000);

  it('reads a chosen file as text and sends it', async () => {
    await openWizard();
    const file = new File([exportCsv], 'mine.csv', { type: 'text/csv' });
    await userEvent.upload(screen.getByLabelText('Fichero CSV en formato RBAPP'), file);
    await userEvent.click(screen.getByRole('button', { name: 'Revisar' }));
    await screen.findByText(/Correctas: 1/, {}, LONG);
    expect(sent).toEqual([{ path: '/collection/import/preview', body: { text: exportCsv } }]);
  }, 20000);

  it('checks for nothing to send and for a file over 2 MB before asking the server', async () => {
    await openWizard();
    await userEvent.click(screen.getByRole('button', { name: 'Revisar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Elige un fichero o pega el contenido.',
    );
    const big = new File(['x'], 'big.csv', { type: 'text/csv' });
    Object.defineProperty(big, 'size', { value: MB2 + 1 });
    await userEvent.upload(screen.getByLabelText('Fichero CSV en formato RBAPP'), big);
    await userEvent.click(screen.getByRole('button', { name: 'Revisar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('El fichero supera 2 MB.');
    expect(sent).toEqual([]);
    expect(current()).toHaveTextContent('Fichero');
  }, 20000);

  it('shows import_format_unknown on the first step', async () => {
    server.use(
      http.post(`${API}/collection/import/preview`, () =>
        failure(400, { error: 'Validation Error', code: 'import_format_unknown' }),
      ),
    );
    await openWizard();
    await userEvent.click(screen.getByRole('textbox', { name: 'O pega aquí el contenido' }));
    await userEvent.paste('name;qty\nAyla;1');
    await userEvent.click(screen.getByRole('button', { name: 'Revisar' }));
    expect(await screen.findByRole('alert', {}, LONG)).toHaveTextContent(
      'No se reconoce el formato del fichero. Usa el formato RBAPP (exportación de la app).',
    );
    expect(current()).toHaveTextContent('Fichero');
  }, 20000);
});

describe('ImportWizard review (F3-i S2)', () => {
  it('lists every row with its status, card and joined reasons', async () => {
    await openWizard();
    await pasteAndReview();
    expect(screen.getByText('Las filas con error no se importarán.')).toBeVisible();
    const table = screen.getByRole('table', { name: 'Revisión' });
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(headers).toEqual(expect.arrayContaining(['Línea', 'Estado', 'Carta', 'Motivos']));
    const ayla = within(table).getByRole('row', { name: /Ayla/ });
    expect(within(ayla).getByText('Correcta')).toBeVisible();
    expect(within(ayla).getByText('OGN · #79')).toBeVisible();
    expect(within(ayla).getByText('0,80 €')).toBeVisible();
    const ember = within(table).getByRole('row', { name: /Ember Wisp/ });
    expect(within(ember).getByText('Aviso')).toBeVisible();
    expect(
      within(ember).getByText(
        'El nombre no coincide; se usa el del catálogo. Estado desconocido; se importa sin estado.',
      ),
    ).toBeVisible();
    const missing = within(table).getByRole('row', { name: /XXX · #999/ });
    expect(within(missing).getByText('Error')).toBeVisible();
    expect(within(missing).getByText('La carta no existe en el catálogo.')).toBeVisible();
  }, 20000);

  it('filters the rows by status', async () => {
    await openWizard();
    await pasteAndReview();
    const table = screen.getByRole('table', { name: 'Revisión' });
    await userEvent.click(screen.getByRole('radio', { name: 'Error' }));
    expect(within(table).queryByRole('row', { name: /Ayla/ })).toBeNull();
    expect(within(table).getByRole('row', { name: /XXX · #999/ })).toBeVisible();
    await userEvent.click(screen.getByRole('radio', { name: 'Aviso' }));
    expect(within(table).getByRole('row', { name: /Ember Wisp/ })).toBeVisible();
    expect(within(table).queryByRole('row', { name: /XXX/ })).toBeNull();
    await userEvent.click(screen.getByRole('radio', { name: 'Todas' }));
    expect(within(table).getAllByRole('row')).toHaveLength(4);
  }, 20000);

  it('goes back to the first step keeping the text', async () => {
    await openWizard();
    await pasteAndReview();
    await userEvent.click(screen.getByRole('button', { name: 'Atrás' }));
    expect(screen.getByRole('textbox', { name: 'O pega aquí el contenido' })).toHaveValue(
      exportCsv,
    );
    expect(current()).toHaveTextContent('Fichero');
  }, 20000);
});

describe('ImportWizard commit (F3-i S2, S4)', () => {
  it('adds by default, shows the result and refreshes the collection queries', async () => {
    const { queryClient, where } = await openWizard();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    await toModeStep();
    expect(current()).toHaveTextContent('Modo');
    expect(screen.getByRole('radio', { name: 'Añadir a mi colección' })).toBeChecked();
    expect(screen.getByText('Suma las copias; las líneas iguales se juntan.')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Importar' }));
    expect(
      await screen.findByText(
        'Creadas: 2 · Sumadas: 0 · Cartas reemplazadas: 0 · Omitidas: 1',
        {},
        LONG,
      ),
    ).toBeVisible();
    expect(current()).toHaveTextContent('Resultado');
    expect(sent[1]).toEqual({
      path: '/collection/import/commit',
      body: { preview_id: 'prev-1', mode: 'add' },
    });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['collection'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['cards'] });

    await userEvent.click(screen.getByRole('button', { name: 'Importar otro fichero' }));
    expect(current()).toHaveTextContent('Fichero');
    expect(screen.getByRole('textbox', { name: 'O pega aquí el contenido' })).toHaveValue('');

    await toModeStep();
    await userEvent.click(screen.getByRole('button', { name: 'Importar' }));
    await userEvent.click(await screen.findByRole('link', { name: 'Ir a la colección' }, LONG));
    await waitFor(() => expect(where()).toBe('/collection'));
  }, 30000);

  it('replace asks first, with the number of cards, and sends the mode', async () => {
    await openWizard();
    await toModeStep();
    await userEvent.click(screen.getByRole('radio', { name: 'Reemplazar estas cartas' }));
    expect(
      screen.getByText(
        'Para cada carta del fichero se borran tus líneas actuales de esa carta y se ponen las del fichero. El resto de tu colección no cambia.',
      ),
    ).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Importar' }));
    let confirm = await screen.findByRole('dialog', { name: 'Reemplazar estas cartas' });
    expect(within(confirm).getByText('¿Reemplazar 2 cartas de tu colección?')).toBeVisible();
    await userEvent.click(within(confirm).getByRole('button', { name: 'Cancelar' }));
    expect(sent.filter((one) => one.path.endsWith('/commit'))).toEqual([]);

    await userEvent.click(screen.getByRole('button', { name: 'Importar' }));
    confirm = await screen.findByRole('dialog', { name: 'Reemplazar estas cartas' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Importar' }));
    expect(
      await screen.findByText(
        'Creadas: 2 · Sumadas: 0 · Cartas reemplazadas: 2 · Omitidas: 1',
        {},
        LONG,
      ),
    ).toBeVisible();
    expect(sent[1].body).toEqual({ preview_id: 'prev-1', mode: 'replace' });
  }, 30000);

  it('an expired preview goes back to the first step with the reason', async () => {
    server.use(
      http.post(`${API}/collection/import/commit`, () =>
        failure(410, { error: 'Gone', code: 'import_expired' }),
      ),
    );
    await openWizard();
    await toModeStep();
    await userEvent.click(screen.getByRole('button', { name: 'Importar' }));
    expect(await screen.findByRole('alert', {}, LONG)).toHaveTextContent(
      'La vista previa ha caducado. Vuelve a subir el fichero.',
    );
    expect(current()).toHaveTextContent('Fichero');
  }, 25000);
});

describe('ImportWizard entry points and states (F3-i S2-S3)', () => {
  it('the collection toolbar links to the wizard', async () => {
    const { where } = await renderApp({ path: '/collection', width: 1280 });
    await userEvent.click(await screen.findByRole('link', { name: 'Importar' }, LONG));
    await waitFor(() => expect(where()).toBe('/collection/import'));
    expect(await screen.findByRole('heading', { name: 'Importar colección' }, LONG)).toBeVisible();
  }, 20000);

  it('offline: says why and disables the actions', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    await openWizard(390);
    expect(screen.getByText('Necesitas conexión para hacer cambios.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Revisar' })).toBeDisabled();
    expect(screen.getByLabelText('Fichero CSV en formato RBAPP')).toBeDisabled();
    expect(screen.getByRole('textbox', { name: 'O pega aquí el contenido' })).toBeDisabled();
  }, 15000);

  it('marks the busy preview button', async () => {
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post(`${API}/collection/import/preview`, async () => {
        await gate;
        return failure(400, { code: 'import_format_unknown' });
      }),
    );
    await openWizard();
    await userEvent.click(screen.getByRole('textbox', { name: 'O pega aquí el contenido' }));
    await userEvent.paste('x');
    await userEvent.click(screen.getByRole('button', { name: 'Revisar' }));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Revisar' })).toHaveAttribute('aria-busy', 'true'),
    );
    release();
    await screen.findByRole('alert', {}, LONG);
  }, 20000);
});

describe.each([390, 1280, 1700])('ImportWizard layout at %i px (F3-i S3)', (width) => {
  it('shows the review as a list on a phone and as a table from 860 px; axe clean', async () => {
    const { container } = await openWizard(width);
    expect(await axe(container)).toHaveNoViolations();
    await pasteAndReview();
    if (width < 860) {
      expect(screen.queryByRole('table', { name: 'Revisión' })).toBeNull();
      const list = screen.getByRole('list', { name: 'Revisión' });
      expect(within(list).getAllByRole('listitem')).toHaveLength(3);
      expect(within(list).getByText('La carta no existe en el catálogo.')).toBeVisible();
    } else {
      expect(screen.getByRole('table', { name: 'Revisión' })).toBeVisible();
    }
    expect(await axe(container)).toHaveNoViolations();
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
    await screen.findByRole('group', { name: 'Modo' });
    expect(await axe(container)).toHaveNoViolations();
  }, 30000);
});
