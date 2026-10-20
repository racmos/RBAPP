import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithI18n } from '@/test/i18n';
import { LanguageToggle } from './LanguageToggle';

describe('LanguageToggle (I18N-3, R4)', () => {
  it('is a labelled group with the current language pressed', async () => {
    await renderWithI18n(<LanguageToggle />);
    expect(screen.getByRole('group', { name: 'Idioma' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Español' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('switches the UI, <html lang> and rb_lang without a reload', async () => {
    const { i18n } = await renderWithI18n(<LanguageToggle />);
    await userEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(i18n.language).toBe('en');
    expect(document.documentElement.lang).toBe('en');
    expect(localStorage.getItem('rb_lang')).toBe('en');
    expect(screen.getByRole('group', { name: 'Language' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('switches back and forth', async () => {
    await renderWithI18n(<LanguageToggle />, 'en');
    await userEvent.click(screen.getByRole('button', { name: 'Español' }));
    expect(localStorage.getItem('rb_lang')).toBe('es');
    expect(document.documentElement.lang).toBe('es');
  });

  it('writes only the device language: it sends no request', async () => {
    // Any request would fail the test: MSW errors on unhandled requests and this one has no handler.
    await renderWithI18n(<LanguageToggle />);
    await userEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(localStorage.getItem('rb_lang')).toBe('en');
  });

  it('tells the caller which language was chosen, after applying it', async () => {
    const onChoose = vi.fn();
    await renderWithI18n(<LanguageToggle onChoose={onChoose} />);
    await userEvent.click(screen.getByRole('button', { name: 'English' }));
    expect(onChoose).toHaveBeenCalledTimes(1);
    expect(onChoose).toHaveBeenCalledWith('en');
    expect(localStorage.getItem('rb_lang')).toBe('en');
  });
});
