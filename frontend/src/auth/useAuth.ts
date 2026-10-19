import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';
import { logout as logoutRequest } from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import { pushToast } from '@/components/ui/toastStore';
import { storeLang, translateError } from '@/i18n';
import { resetToAnonymous } from './signOut';
import { sessionQuery } from './session';

/** The cached session (always defined under a guarded route: the loader filled the cache). */
export function useSession() {
  const { data } = useQuery(sessionQuery);
  return data ?? null;
}

/**
 * Sign out (FAUTH-5). A 200 and a 401 ("already signed out") are the same outcome; any other
 * failure keeps the user signed in and says so.
 */
export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { i18n } = useTranslation();

  const mutation = useMutation({
    mutationFn: logoutRequest,
    onSettled: async (_data, error) => {
      if (error && !(error instanceof ApiError && error.status === 401)) {
        pushToast({ kind: 'error', message: translateError(error, i18n) });
        return;
      }
      storeLang(i18n.language === 'en' ? 'en' : 'es');
      resetToAnonymous(queryClient);
      await navigate('/login');
    },
  });

  return { logout: () => mutation.mutate(), pending: mutation.isPending };
}
