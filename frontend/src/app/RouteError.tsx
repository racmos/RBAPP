import { useTranslation } from 'react-i18next';
import { isRouteErrorResponse, useRouteError } from 'react-router';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { NotFound } from '@/shell/NotFound';
import { isChunkLoadError } from './chunkReload';

/** The `errorElement` of the route tree: 404 view, stale-deploy reload, or a generic failure. */
export function RouteError({ reload = () => window.location.reload() }: { reload?: () => void }) {
  const error = useRouteError();
  const { t } = useTranslation('errors');
  const { t: common } = useTranslation('common');
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound />;

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
