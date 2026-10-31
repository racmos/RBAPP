import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { I18nextProvider } from 'react-i18next';
import { createI18n } from '@/i18n';

/** Render under an i18n instance (English, the only language). */
export async function renderWithI18n(
  ui: ReactElement,
): Promise<RenderResult & { i18n: Awaited<ReturnType<typeof createI18n>> }> {
  const i18n = await createI18n();
  const wrap = ({ children }: { children: ReactNode }) => (
    <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
  );
  return { ...(render(ui, { wrapper: wrap }) as RenderResult), i18n };
}
