import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { isRouteErrorResponse, useLocation, useNavigate, useRouteError } from 'react-router';
import { ApiError } from '@/api/errors';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { NotFound } from '@/shell/NotFound';
import { isChunkLoadError } from './chunkReload';

/**
 * The server could not be reached while booting and there was no signed-in hint to fall back on
 * (PWA-7): say so, and retry the loaders when asked.
 */
function Unreachable() {
  const { t } = useTranslation('errors');
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const retry = async () => {
    await queryClient.resetQueries({ predicate: (query) => query.state.status === 'error' });
    await navigate(location.pathname + location.search + location.hash, { replace: true });
  };
  return (
    <main
      style={{ display: 'grid', placeItems: 'center', minHeight: '60dvh', padding: 'var(--pad)' }}
    >
      <ErrorState message={t('network')} onRetry={() => void retry()} />
    </main>
  );
}

/** The `errorElement` of the route tree: 404 view, offline boot, stale-deploy reload, or a generic failure. */
export function RouteError({ reload = () => window.location.reload() }: { reload?: () => void }) {
  const error = useRouteError();
  const { t } = useTranslation('errors');
  const { t: common } = useTranslation('common');
  if (isRouteErrorResponse(error) && error.status === 404) {
    return (
      <main style={{ minHeight: '60dvh', padding: 'var(--pad)' }}>
        <NotFound />
      </main>
    );
  }

  if (error instanceof ApiError && (error.kind === 'network' || error.kind === 'timeout')) {
    return <Unreachable />;
  }

  const message = isChunkLoadError(error) ? t('route.chunk') : t('route.body');
  return (
    <main
      style={{ display: 'grid', placeItems: 'center', minHeight: '60dvh', padding: 'var(--pad)' }}
    >
      <div style={{ textAlign: 'center' }}>
        <h1>{t('route.title')}</h1>
        <ErrorState message={message} />
        <Button onClick={reload}>{common('actions.reload')}</Button>
      </div>
    </main>
  );
}
