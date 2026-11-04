import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useOffline } from '@/auth';
import { pushToast } from '@/components/ui/toastStore';
import { translateError, useDocumentTitle } from '@/i18n';
import { useLocations, useReorderLocations } from './queries';

/** Everything the two layouts of `/locations` share: the list, the order, the open sheets. */
export function useLocationsScreen() {
  const { t, i18n } = useTranslation('locations');
  useDocumentTitle(t('title'));
  const offline = useOffline();
  const query = useLocations();
  const reorder = useReorderLocations();
  const [editing, setEditing] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);

  const items = query.data?.items ?? [];
  const unassigned = query.data?.unassigned ?? 0;
  const editingLocation = editing === null ? undefined : items.find((item) => item.id === editing);

  /** Puts the location `id` at `index` and saves the whole order (F16-R2). */
  const moveTo = (id: number, index: number) => {
    const from = items.findIndex((item) => item.id === id);
    if (offline || from < 0 || index < 0 || index >= items.length || from === index) return;
    const ids = items.map((item) => item.id);
    ids.splice(from, 1);
    ids.splice(index, 0, id);
    reorder.mutate(ids, {
      onError: (error) => pushToast({ kind: 'error', message: translateError(error, i18n) }),
    });
  };
  const moveBy = (id: number, delta: -1 | 1) =>
    moveTo(id, items.findIndex((item) => item.id === id) + delta);

  return {
    t,
    offline,
    query,
    items,
    unassigned,
    moveTo,
    moveBy,
    editing: editingLocation,
    setEditing,
    creating,
    setCreating,
  };
}

export type LocationsScreen = ReturnType<typeof useLocationsScreen>;
