import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { createI18n } from '@/i18n';
import { I18nextProvider } from 'react-i18next';
import { ValueDiff } from './ValueDiff';

async function renderDiff(props: Parameters<typeof ValueDiff>[0]) {
  const i18n = await createI18n();
  render(
    <I18nextProvider i18n={i18n}>
      <ValueDiff {...props} />
    </I18nextProvider>,
  );
}

describe('ValueDiff (F13-g S6)', () => {
  it('inline shows old struck through and new with accessible prefixes', async () => {
    await renderDiff({ oldValue: 'Alpha', newValue: 'Alfa', layout: 'inline' });
    const old = screen.getByText('Alpha');
    expect(old.tagName.toLowerCase()).toBe('del');
    expect(screen.getByText('Before:', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('Now:', { exact: false })).toBeInTheDocument();
  });

  it('stacked and side layouts render both values', async () => {
    await renderDiff({ oldValue: 'A', newValue: 'B', layout: 'stacked' });
    expect(screen.getByText('A')).toBeVisible();
    expect(screen.getByText('B')).toBeVisible();
  });

  it('empty and null values show the empty marker', async () => {
    await renderDiff({ oldValue: '', newValue: null, layout: 'inline' });
    expect(screen.getAllByText('(empty)')).toHaveLength(2);
  });
});
