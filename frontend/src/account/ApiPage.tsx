import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { createApiKey, deleteApiKey } from '@/api/endpoints';
import type { ApiKeyInfo } from '@/api/types';
import { useOffline } from '@/auth';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { ErrorState } from '@/components/ui/ErrorState';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { SettingsCard } from '@/components/ui/SettingsCard';
import { Skeleton } from '@/components/ui/Skeleton';
import { pushToast } from '@/components/ui/toastStore';
import { translateError, useDocumentTitle } from '@/i18n';
import { formatDate, formatRelative } from '@/lib/format';
import { AccountHeader } from './AccountNav';
import { useCopy } from './copy';
import { apiKeyQuery } from './queries';
import { isReauthCancelled } from './reauth/withReauth';
import { useReauth } from './reauth/ReauthProvider';
import styles from './SecurityPage.module.css';

/** The example uses a placeholder, never the real key (F9-j S11). */
const PLACEHOLDER = 'rb_live_<your key>';

/** "Your new API key" (F9-j S10): shown once; the key leaves the state when it closes. */
function NewKeyDialog({ apiKey, onClose }: { apiKey: string; onClose: () => void }) {
  const { t } = useTranslation('account');
  const copy = useCopy();
  return (
    <Modal open title={t('api.newTitle')} onClose={onClose}>
      <div className={styles.form}>
        <Field label={t('api.title')}>
          {(control) => (
            <Input
              {...control}
              value={apiKey}
              readOnly
              spellCheck={false}
              className={styles.mono}
              onFocus={(event) => event.currentTarget.select()}
            />
          )}
        </Field>
        <p className={styles.warning}>{t('api.warning')}</p>
        <div className={styles.actions}>
          <Button variant="ghost" onClick={() => void copy(apiKey)}>
            {t('api.copy')}
          </Button>
          <Button onClick={onClose}>{t('api.done')}</Button>
        </div>
      </div>
    </Modal>
  );
}

type Confirm = 'replace' | 'revoke' | null;

/** The key card (F9-j S10): none / prefix and dates, create or replace, revoke. */
function KeyCard({ offline }: { offline: boolean }) {
  const { t, i18n } = useTranslation('account');
  const { t: tCommon } = useTranslation('common');
  const queryClient = useQueryClient();
  const withReauth = useReauth();
  const query = useQuery({ ...apiKeyQuery, enabled: !offline });
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [pending, setPending] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);

  const store = (info: ApiKeyInfo | null) => {
    queryClient.setQueryData(apiKeyQuery.queryKey, info);
    // `GET /me` carries the same summary (F9-h S6).
    void queryClient.invalidateQueries({ queryKey: ['me'], exact: true });
  };
  const fail = (error: unknown) => {
    if (!isReauthCancelled(error)) {
      pushToast({ kind: 'error', message: translateError(error, i18n) });
    }
  };

  const create = async () => {
    setConfirm(null);
    setPending(true);
    try {
      const created = await withReauth(createApiKey);
      store(created.api_key);
      setNewKey(created.key);
    } catch (error) {
      fail(error);
    } finally {
      setPending(false);
    }
  };

  const revoke = async () => {
    setConfirm(null);
    setPending(true);
    try {
      store(await deleteApiKey());
      pushToast({ kind: 'success', message: t('api.revoked') });
    } catch (error) {
      fail(error);
    } finally {
      setPending(false);
    }
  };

  let body;
  if (query.data === null) {
    body = (
      <>
        <p className={styles.text}>{t('api.none')}</p>
        <div className={styles.actions}>
          <Button onClick={() => void create()} pending={pending} disabled={offline}>
            {t('api.create')}
          </Button>
        </div>
      </>
    );
  } else if (query.data) {
    const info = query.data;
    body = (
      <>
        <p className={`${styles.text} ${styles.mono}`}>{t('api.key', { prefix: info.prefix })}</p>
        <p className={styles.hint}>{t('api.created', { date: formatDate(info.created_at) })}</p>
        <p className={styles.hint}>
          {info.last_used_at
            ? t('api.lastUsed', { when: formatRelative(info.last_used_at) })
            : t('api.neverUsed')}
        </p>
        <div className={styles.actions}>
          <Button
            variant="ghost"
            onClick={() => setConfirm('replace')}
            pending={pending}
            disabled={offline}
          >
            {t('api.replace')}
          </Button>
          <Button
            variant="danger"
            onClick={() => setConfirm('revoke')}
            disabled={offline || pending}
          >
            {t('api.revoke')}
          </Button>
        </div>
      </>
    );
  } else if (query.isError) {
    body = (
      <ErrorState
        message={translateError(query.error, i18n)}
        onRetry={() => void query.refetch()}
      />
    );
  } else if (!offline) {
    body = <Skeleton label={tCommon('loadingRegion')} lines={3} />;
  }

  return (
    <SettingsCard title={t('api.title')}>
      <div className={styles.form}>
        <p className={styles.text}>{t('api.intro')}</p>
        {body}
      </div>
      <ConfirmDialog
        open={confirm !== null}
        title={confirm === 'revoke' ? t('api.revokeTitle') : t('api.replaceTitle')}
        message={confirm === 'revoke' ? t('api.revokeBody') : t('api.replaceBody')}
        confirmLabel={confirm === 'revoke' ? t('api.revokeConfirm') : t('api.replaceConfirm')}
        cancelLabel={tCommon('actions.cancel')}
        danger
        onConfirm={() => void (confirm === 'revoke' ? revoke() : create())}
        onCancel={() => setConfirm(null)}
      />
      {newKey && <NewKeyDialog apiKey={newKey} onClose={() => setNewKey(null)} />}
    </SettingsCard>
  );
}

/** The `curl` example (F9-j S11): the runtime origin and a placeholder key. */
function ExampleCard() {
  const { t } = useTranslation('account');
  const copy = useCopy();
  const command = `curl -H "Authorization: Bearer ${PLACEHOLDER}" ${window.location.origin}/riftbound/api/v1/collection`;
  return (
    <SettingsCard title={t('api.exampleTitle')}>
      <div className={styles.form}>
        <pre className={styles.example}>
          <code>{command}</code>
        </pre>
        <p className={styles.hint}>{t('api.exampleNote')}</p>
        <div className={styles.actions}>
          <Button variant="ghost" size="sm" onClick={() => void copy(command)}>
            {t('api.copyExample')}
          </Button>
        </div>
      </div>
    </SettingsCard>
  );
}

/**
 * `/account/api` (F9-j S10, S11): the personal read-only key and how to use it. Offline the
 * cached info stays and the key actions are disabled (S16).
 */
export function ApiPage() {
  const { t } = useTranslation('account');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('sections.api'));
  const offline = useOffline();
  return (
    <>
      <AccountHeader title={t('sections.api')} subtitle={t('api.subtitle')} />
      {offline && <p className={styles.offline}>{tCommon('offline.editDisabled')}</p>}
      <div className={styles.apiGrid}>
        <KeyCard offline={offline} />
        <ExampleCard />
      </div>
    </>
  );
}
