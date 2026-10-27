import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { createI18n } from '@/i18n';
import { AbilityText } from './AbilityText';

async function renderAbility(text: string | null, lang: 'es' | 'en' = 'es') {
  const i18n = await createI18n(lang);
  const { I18nextProvider } = await import('react-i18next');
  return render(
    <I18nextProvider i18n={i18n}>
      <AbilityText text={text} />
    </I18nextProvider>,
  );
}

describe('AbilityText (F2-f S9)', () => {
  it('renders plain text', async () => {
    await renderAbility('When I attack, deal 2.');
    expect(screen.getByText('When I attack, deal 2.')).toBeVisible();
  });

  it('renders a keyword pill without brackets', async () => {
    await renderAbility('[Accelerate]');
    expect(screen.getByText('Accelerate')).toBeVisible();
    expect(screen.queryByText('[Accelerate]')).not.toBeInTheDocument();
  });

  it('renders energy with a visible count and screen-reader text', async () => {
    await renderAbility(':rb_energy_3:');
    expect(screen.getByText('3')).toBeVisible();
    expect(screen.getByText('3 de energía')).toBeInTheDocument();
  });

  it('renders exhaust and might with screen-reader text', async () => {
    await renderAbility(':rb_exhaust:');
    expect(screen.getByText('agotar')).toBeInTheDocument();
    await renderAbility(':rb_might:');
    expect(screen.getByText('fuerza')).toBeInTheDocument();
  });

  it('renders a rune with the domain label', async () => {
    await renderAbility(':rb_rune_fury:');
    expect(screen.getByText('runa de Furia')).toBeInTheDocument();
  });

  it('renders the rainbow rune with the any-domain label', async () => {
    await renderAbility(':rb_rune_rainbow:');
    expect(screen.getByText('runa de cualquier dominio')).toBeInTheDocument();
  });

  it('renders reminder text in italic', async () => {
    await renderAbility('(then :rb_exhaust:)');
    expect(screen.getByText('then')).toBeInTheDocument();
    expect(screen.getByText('agotar')).toBeInTheDocument();
  });

  it('renders the empty message for null/empty text', async () => {
    await renderAbility(null);
    expect(screen.getByText('Sin texto')).toBeVisible();
  });

  it('translates sr-only labels into English', async () => {
    await renderAbility(':rb_energy_2:', 'en');
    expect(screen.getByText('2 energy')).toBeInTheDocument();
    await renderAbility(':rb_rune_calm:', 'en');
    expect(screen.getByText('Calm rune')).toBeInTheDocument();
  });

  it('falls back to keyword text for unknown rb symbols', async () => {
    await renderAbility(':rb_power:');
    expect(screen.getByText('power')).toBeVisible();
  });
});
