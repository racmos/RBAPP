import { act, render, screen } from '@testing-library/react';
import { I18nextProvider, useTranslation } from 'react-i18next';
import { describe, expect, it, vi } from 'vitest';
import { createI18n } from './index';
import { resources } from './resources';
import { useDocumentTitle } from './useDocumentTitle';

function Page({ titleKey }: { titleKey: 'login' | 'none' }) {
  const { t } = useTranslation('auth');
  useDocumentTitle(titleKey === 'login' ? t('login.title') : null);
  return <h1>{t('login.title')}</h1>;
}

describe('language switching (I18N-3)', () => {
  it('updates <html lang>, the labels and the title without a reload', async () => {
    const i18n = await createI18n('es');
    render(
      <I18nextProvider i18n={i18n}>
        <Page titleKey="login" />
      </I18nextProvider>,
    );
    expect(document.documentElement.lang).toBe('es');
    expect(screen.getByRole('heading')).toHaveTextContent(resources.es.auth.login.title);
    expect(document.title).toBe(`${resources.es.auth.login.title} · Rift Manager`);

    await act(() => i18n.changeLanguage('en'));
    expect(document.documentElement.lang).toBe('en');
    expect(screen.getByRole('heading')).toHaveTextContent(resources.en.auth.login.title);
    expect(document.title).toBe(`${resources.en.auth.login.title} · Rift Manager`);
    expect(resources.en.auth.login.title).not.toBe(resources.es.auth.login.title);
  });

  it('uses the bare product name when a page has no title', async () => {
    const i18n = await createI18n('en');
    render(
      <I18nextProvider i18n={i18n}>
        <Page titleKey="none" />
      </I18nextProvider>,
    );
    expect(document.title).toBe('Rift Manager');
  });

  it('starts in the language it is given', async () => {
    const i18n = await createI18n('en');
    expect(i18n.language).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });
});

describe('no missing keys at runtime (I18N-5)', () => {
  it('falls back to the es text when en lacks a key, and never renders the raw key', async () => {
    const withoutKey = structuredClone(resources);
    delete (withoutKey.en.auth.login as Partial<typeof withoutKey.en.auth.login>).title;
    const i18n = await createI18n('en', withoutKey);
    expect(i18n.t('auth:login.title')).toBe(resources.es.auth.login.title);
  });

  it('renders nothing rather than the key when no language has it', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const i18n = await createI18n('en');
    // @ts-expect-error -- the key is not in the typed catalog, so typecheck fails if typing is lost
    const text = i18n.t('auth:does.not.exist');
    expect(text).toBe('');
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('auth:does.not.exist'));
    warn.mockRestore();
  });

  it('types the resources: an unknown key is a compile error', async () => {
    const i18n = await createI18n('es');
    // @ts-expect-error -- unknown namespace key
    i18n.t('auth:does.not.exist');
    expect(i18n.t('auth:login.title')).toBe(resources.es.auth.login.title);
  });
});
