import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { createI18n } from '@/i18n';
import { Pagination } from './Pagination';

async function renderPagination(page: number, pages: number) {
  const onChange = vi.fn();
  const i18n = await createI18n('es');
  const { I18nextProvider } = await import('react-i18next');
  render(
    <I18nextProvider i18n={i18n}>
      <Pagination page={page} pages={pages} onChange={onChange} />
    </I18nextProvider>,
  );
  return onChange;
}

describe('Pagination (F13-f S2)', () => {
  it('labels the nav, disables prev on the first page and calls onChange', async () => {
    const onChange = await renderPagination(1, 3);
    expect(screen.getByRole('navigation', { name: 'Paginación' })).toBeVisible();
    expect(screen.getByText('Página 1 de 3')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
    expect(onChange).toHaveBeenCalledWith(2);
  });

  it('disables next on the last page', async () => {
    const onChange = await renderPagination(3, 3);
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeEnabled();
    await userEvent.click(screen.getByRole('button', { name: 'Anterior' }));
    expect(onChange).toHaveBeenCalledWith(2);
  });
});
