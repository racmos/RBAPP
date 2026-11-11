import { useTranslation } from 'react-i18next';
import { ApiError } from '@/api/errors';
import { translateError } from '@/i18n';

/** The 409 `wishlist_limit` in the words of the screen: a full list, or too many lists. */
export function useWishlistError() {
  const { t, i18n } = useTranslation('wishlists');
  return (error: unknown): string => {
    if (error instanceof ApiError && error.code === 'wishlist_limit') {
      const max = Number(error.params?.max ?? (error.params?.scope === 'lists' ? 20 : 100));
      return error.params?.scope === 'lists'
        ? t('errors.tooManyLists', { max })
        : t('errors.listFull', { max });
    }
    return translateError(error, i18n);
  };
}
