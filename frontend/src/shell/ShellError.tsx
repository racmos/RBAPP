import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { isRouteErrorResponse, useLocation, useNavigate, useRouteError } from 'react-router';
import { isChunkLoadError } from '@/lib/chunkError';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { NotFound } from './NotFound';

/**
 * The `errorElement` of the pages inside the shell (SHELL-8): the page fails, the topbar and the
 * bottom navigation stay. Retry resets every failed query and renders the page again, which fetches it afresh; a
 * stale-deploy chunk error asks for a reload instead.
 */
export function ShellError({ reload = () => window.location.reload() }: { reload?: () => void }) {
  const error = useRouteError();
  const { t } = useTranslation('errors');
  const { t: common } = useTranslation('common');
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();

  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />;

  if (isChunkLoadError(error)) {
    return (
      <>
        <ErrorState message={t('route.chunk')} />
        <div style={{ textAlign: 'center' }}>
          <Button onClick={reload}>{common('actions.reload')}</Button>
        </div>
      </>
    );
  }

  const retry = async () => {
    // Back to the initial state, so the page fetches once when it renders again (a refetch here
    // plus the fetch on mount would ask twice).
    await queryClient.resetQueries({ predicate: (query) => query.state.status === 'error' });
    await navigate(location.pathname + location.search + location.hash, { replace: true });
  };

  return <ErrorState message={t('route.body')} onRetry={() => void retry()} />;
}
