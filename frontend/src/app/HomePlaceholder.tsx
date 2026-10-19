import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Brand } from '@/components/ui/Brand';
import { useLogout, useSession } from '@/auth/useAuth';
import { useDocumentTitle } from '@/i18n';

/** Temporary home of unit d: proves the guarded route and offers logout until the shell lands (unit e). */
export function HomePlaceholder() {
  const { t } = useTranslation('nav');
  const session = useSession();
  const { logout, pending } = useLogout();
  useDocumentTitle(null);

  return (
    <main
      style={{
        display: 'grid',
        placeItems: 'center',
        gap: '1.25rem',
        minHeight: '100dvh',
        padding: 'var(--pad)',
        textAlign: 'center',
      }}
    >
      <Brand variant="wordmark" />
      <h1>{t('welcome', { username: session?.user?.username ?? '' })}</h1>
      <p>{t('underConstruction')}</p>
      <Button variant="ghost" pending={pending} onClick={logout}>
        {t('logout')}
      </Button>
    </main>
  );
}
