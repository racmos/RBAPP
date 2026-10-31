import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { I18nextProvider } from 'react-i18next';
import { createQueryClient } from '@/app/queryClient';
import type { Session } from '@/api/types';
import { ANONYMOUS, sessionQuery } from '@/auth';
import { ToastStack } from '@/components/ui/Toast';
import { createI18n } from '@/i18n';
import { PrefsProvider } from '@/prefs';
import { NO_PREFS, USER } from './msw/handlers';
import { setViewport } from './viewport';

export const SIGNED_IN: Session = { authenticated: true, user: USER, prefs: NO_PREFS as never };

type Options = { session?: Session; width?: number };

/** A component under the query cache, i18n and the preferences, with a seeded session. */
export async function renderWithPrefs(
  ui: ReactElement,
  { session = ANONYMOUS, width }: Options = {},
): Promise<
  RenderResult & { queryClient: QueryClient; i18n: Awaited<ReturnType<typeof createI18n>> }
> {
  if (width !== undefined) setViewport(width);
  const queryClient = createQueryClient();
  queryClient.setQueryData(sessionQuery.queryKey, session);
  const i18n = await createI18n();
  const result = render(
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <PrefsProvider>
          {ui}
          <ToastStack />
        </PrefsProvider>
      </I18nextProvider>
    </QueryClientProvider>,
  );
  return { ...result, queryClient, i18n };
}
