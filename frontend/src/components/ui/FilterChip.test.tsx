import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { createI18n } from '@/i18n';
import { ChipGroup, FilterChip } from './FilterChip';

async function renderChip(props: React.ComponentProps<typeof FilterChip>) {
  const i18n = await createI18n('es');
  const { I18nextProvider } = await import('react-i18next');
  return render(
    <I18nextProvider i18n={i18n}>
      <FilterChip {...props} />
    </I18nextProvider>,
  );
}

describe('FilterChip (F2-h S11)', () => {
  it('renders a toggle button with aria-pressed and count', async () => {
    await renderChip({ label: 'Fury', pressed: true, count: 5, onClick: vi.fn() });
    const button = screen.getByRole('button', { name: 'Fury (5)' });
    expect(button).toHaveAttribute('aria-pressed', 'true');
  });

  it('calls onClick when pressed', async () => {
    const onClick = vi.fn();
    await renderChip({ label: 'Fury', onClick });
    await userEvent.click(screen.getByRole('button', { name: 'Fury' }));
    expect(onClick).toHaveBeenCalled();
  });

  it('renders a remove button with the caller aria-label', async () => {
    const onRemove = { 'aria-label': 'Remove Fury filter', onClick: vi.fn() };
    await renderChip({ label: 'Fury', onRemove });
    expect(screen.getByRole('button', { name: 'Fury' })).toBeVisible();
    const remove = screen.getByRole('button', { name: 'Remove Fury filter' });
    expect(remove).toBeVisible();
    await userEvent.click(remove);
    expect(onRemove.onClick).toHaveBeenCalled();
  });

  it('computes a contrasting foreground for a domain colour', async () => {
    const { container } = await renderChip({ label: 'Fury', color: '#e7504a' });
    const chip = container.querySelector('[class*="chip"]') as HTMLElement;
    expect(chip).toHaveStyle({ color: '#06222c' });
  });
});

describe('ChipGroup (F2-h S11)', () => {
  it('names the group with the legend', async () => {
    const i18n = await createI18n('es');
    const { I18nextProvider } = await import('react-i18next');
    render(
      <I18nextProvider i18n={i18n}>
        <ChipGroup legend="Domains">
          <FilterChip label="Fury" />
          <FilterChip label="Chaos" />
        </ChipGroup>
      </I18nextProvider>,
    );
    expect(screen.getByRole('group', { name: 'Domains' })).toBeVisible();
  });
});
