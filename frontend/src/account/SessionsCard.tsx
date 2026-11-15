import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { revokeOtherSessions, revokeSession } from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import type { DeviceSession } from '@/api/types';
import { useLogout } from '@/auth';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { ErrorState } from '@/components/ui/ErrorState';
import { SettingsCard } from '@/components/ui/SettingsCard';
import { Skeleton } from '@/components/ui/Skeleton';
import { TableScroll } from '@/components/ui/TableScroll';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { formatDate, formatRelative } from '@/lib/format';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { sessionsQuery } from './queries';
import styles from './SecurityPage.module.css';

const METHODS = {
  password: 'sessions.methods.password',
  discord: 'sessions.methods.discord',
  google: 'sessions.methods.google',
} as const;

type Confirm = { kind: 'one'; session: DeviceSession } | { kind: 'others' } | null;

function useMethodLabel() {
  const { t } = useTranslation('account');
  return (method: string) =>
    method in METHODS ? t(METHODS[method as keyof typeof METHODS]) : method;
}

type RowProps = {
  session: DeviceSession;
  offline: boolean;
  signingOut: boolean;
  onSignOut: (session: DeviceSession) => void;
};

/** Below md: one card per device (F9-j S9). */
function DeviceItem({ session, offline, signingOut, onSignOut }: RowProps) {
  const { t } = useTranslation('account');
  const method = useMethodLabel();
  return (
    <li className={styles.item}>
      <div className={styles.row}>
        <p className={styles.device}>{session.device}</p>
        {session.current && <Badge tone="accent">{t('sessions.thisDevice')}</Badge>}
      </div>
      <div className={styles.row}>
        <span className={styles.meta}>
          {t('sessions.method', { method: method(session.auth_method) })}
        </span>
        {session.mfa && <Badge>{t('sessions.mfa')}</Badge>}
      </div>
      {session.ip_prefix && (
        <p className={styles.meta}>{t('sessions.network', { ip: session.ip_prefix })}</p>
      )}
      <p className={styles.meta}>
        {t('sessions.lastActive', { when: formatRelative(session.last_seen_at) })}
      </p>
      <p className={styles.meta}>
        {t('sessions.signedIn', { date: formatDate(session.created_at) })}
      </p>
      {session.remember && session.expires_at && (
        <p className={styles.meta}>
          {t('sessions.until', { date: formatDate(session.expires_at) })}
        </p>
      )}
      <div className={styles.actions}>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onSignOut(session)}
          disabled={offline}
          pending={session.current && signingOut}
        >
          {t('sessions.signOut')}
        </Button>
      </div>
    </li>
  );
}

/** From md: one table row per device (F9-j S9). */
function DeviceRow({ session, offline, signingOut, onSignOut }: RowProps) {
  const { t } = useTranslation('account');
  const method = useMethodLabel();
  return (
    <tr>
      <td>
        <div className={styles.row}>
          <span className={styles.device}>{session.device}</span>
          {session.current && <Badge tone="accent">{t('sessions.thisDevice')}</Badge>}
        </div>
      </td>
      <td>
        <div className={styles.row}>
          <span>{method(session.auth_method)}</span>
          {session.mfa && <Badge>{t('sessions.mfa')}</Badge>}
        </div>
      </td>
      <td className={styles.mono}>{session.ip_prefix ?? '—'}</td>
      <td className={styles.nowrap}>{formatRelative(session.last_seen_at)}</td>
      <td>
        <span className={styles.nowrap}>{formatDate(session.created_at)}</span>
        {session.remember && session.expires_at && (
          <p className={styles.meta}>
            {t('sessions.until', { date: formatDate(session.expires_at) })}
          </p>
        )}
      </td>
      <td>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onSignOut(session)}
          disabled={offline}
          pending={session.current && signingOut}
        >
          {t('sessions.signOut')}
        </Button>
      </td>
    </tr>
  );
}

/**
 * "Signed-in devices" (F9-j S9): `GET /me/sessions` as cards below md and a table from md.
 * Another device is signed out after a confirmation; this one goes through the logout flow.
 */
export function SessionsCard({ offline }: { offline: boolean }) {
  const { t, i18n } = useTranslation('account');
  const { t: tCommon } = useTranslation('common');
  const queryClient = useQueryClient();
  const wide = useMediaQuery(up('md'));
  const query = useQuery({ ...sessionsQuery, enabled: !offline });
  const { logout, pending: signingOut } = useLogout();
  const [confirm, setConfirm] = useState<Confirm>(null);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['me'] });

  const signOut = (session: DeviceSession) => {
    if (session.current) logout();
    else setConfirm({ kind: 'one', session });
  };

  const run = async (current: NonNullable<Confirm>) => {
    setConfirm(null);
    try {
      if (current.kind === 'one') {
        await revokeSession(current.session.id);
        pushToast({ kind: 'success', message: t('sessions.signedOut') });
      } else {
        const count = await revokeOtherSessions();
        pushToast({ kind: 'success', message: t('sessions.othersDone', { count }) });
      }
    } catch (error) {
      // Already gone (ended elsewhere or expired): the fresh list says it all.
      if (!(error instanceof ApiError && error.status === 404)) {
        pushToast({ kind: 'error', message: translateError(error, i18n) });
      }
    } finally {
      refresh();
    }
  };

  const sessions = query.data;
  let content;
  if (sessions) {
    const rowProps = { offline, signingOut, onSignOut: signOut };
    content = wide ? (
      <TableScroll>
        <table className={styles.table}>
          <caption className="sr-only">{t('sessions.title')}</caption>
          <thead>
            <tr>
              <th scope="col">{t('sessions.columns.device')}</th>
              <th scope="col">{t('sessions.columns.method')}</th>
              <th scope="col">{t('sessions.columns.network')}</th>
              <th scope="col">{t('sessions.columns.lastActive')}</th>
              <th scope="col">{t('sessions.columns.signedIn')}</th>
              <th scope="col">{t('sessions.columns.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <DeviceRow key={session.id} session={session} {...rowProps} />
            ))}
          </tbody>
        </table>
      </TableScroll>
    ) : (
      <ul className={styles.list}>
        {sessions.map((session) => (
          <DeviceItem key={session.id} session={session} {...rowProps} />
        ))}
      </ul>
    );
  } else if (query.isError) {
    content = (
      <ErrorState
        message={translateError(query.error, i18n)}
        onRetry={() => void query.refetch()}
      />
    );
  } else if (!offline) {
    content = <Skeleton label={tCommon('loadingRegion')} lines={4} />;
  }
  const others = sessions?.some((session) => !session.current) ?? false;

  return (
    <SettingsCard title={t('sessions.title')} description={t('sessions.hint')}>
      <div className={styles.form}>
        {content}
        {others && (
          <div className={styles.actions}>
            <Button
              variant="danger"
              onClick={() => setConfirm({ kind: 'others' })}
              disabled={offline}
            >
              {t('sessions.signOutOthers')}
            </Button>
          </div>
        )}
      </div>
      <ConfirmDialog
        open={confirm !== null}
        title={confirm?.kind === 'others' ? t('sessions.othersTitle') : t('sessions.signOutTitle')}
        message={
          confirm?.kind === 'one'
            ? t('sessions.signOutBody', { device: confirm.session.device })
            : t('sessions.othersBody')
        }
        confirmLabel={
          confirm?.kind === 'others' ? t('sessions.othersConfirm') : t('sessions.signOut')
        }
        cancelLabel={tCommon('actions.cancel')}
        danger
        onConfirm={() => confirm && void run(confirm)}
        onCancel={() => setConfirm(null)}
      />
    </SettingsCard>
  );
}
