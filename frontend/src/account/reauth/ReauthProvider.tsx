import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { pushToast } from '@/components/ui/toastStore';
import { translateError } from '@/i18n';
import { ReauthDialog } from './ReauthDialog';
import {
  ReauthCancelled,
  withReauth as runWithReauth,
  type AskReauth,
  type ReauthMethod,
} from './withReauth';

const AskContext = createContext<AskReauth | null>(null);

type Pending = { id: number; methods: ReauthMethod[]; resolve: () => void; reject: () => void };

/**
 * Holds the one re-authentication dialog of the account area (F9-j S2, S3): `useReauth()`
 * below it opens the dialog when a call answers `reauth_required`.
 */
export function ReauthProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const ask = useCallback<AskReauth>(
    (methods) =>
      new Promise<void>((resolve, reject) => {
        setPending((previous) => {
          previous?.reject();
          return {
            id: (previous?.id ?? 0) + 1,
            methods,
            resolve,
            reject: () => reject(new ReauthCancelled()),
          };
        });
      }),
    [],
  );
  const finish = (outcome: 'done' | 'cancel') => {
    if (!pending) return;
    if (outcome === 'done') pending.resolve();
    else pending.reject();
    setPending(null);
  };

  return (
    <AskContext.Provider value={ask}>
      {children}
      {pending && (
        <ReauthDialog
          key={pending.id}
          methods={pending.methods}
          onDone={() => finish('done')}
          onCancel={() => finish('cancel')}
        />
      )}
    </AskContext.Provider>
  );
}

/** `withReauth(action)` bound to the account's dialog and its error toast (F9-j S2). */
export function useReauth() {
  const ask = useContext(AskContext);
  const { i18n } = useTranslation();
  return useCallback(
    <T,>(action: () => Promise<T>): Promise<T> => {
      if (!ask) throw new Error('useReauth needs a ReauthProvider');
      return runWithReauth(action, ask, (error) =>
        pushToast({ kind: 'error', message: translateError(error, i18n) }),
      );
    },
    [ask, i18n],
  );
}
