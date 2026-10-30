import { useTranslation } from 'react-i18next';
import type { ProductFacets } from '@/api/types';
import { useGameMeta } from '@/catalog';
import { Select } from '@/components/ui/Select';
import { sortSetIdsNewestFirst } from '@/lib/sets';
import type { ProductsParams } from './params';

type SetSelectProps = {
  params: ProductsParams;
  setParams: (patch: Partial<ProductsParams>) => void;
  facets: ProductFacets;
};

/** One set or all of them; each option carries the set name and its product count. */
export function SetSelect({ params, setParams, facets }: SetSelectProps) {
  const { t } = useTranslation('products');
  const gameMeta = useGameMeta();
  const setNames = new Map((gameMeta.data?.sets ?? []).map((set) => [set.id, set.name]));
  const setIds = sortSetIdsNewestFirst(
    [...new Set([...Object.keys(facets.set), ...(params.set ?? [])])],
    gameMeta.data?.sets ?? [],
  );
  return (
    <Select
      value={params.set?.[0] ?? ''}
      onChange={(event) =>
        setParams({ set: event.target.value ? [event.target.value] : undefined })
      }
    >
      <option value="">{t('filters.allSets')}</option>
      {setIds.map((id) => (
        <option key={id} value={id}>
          {setNames.get(id) ? `${id} · ${setNames.get(id)}` : id}
          {facets.set[id] !== undefined ? ` (${facets.set[id]})` : ''}
        </option>
      ))}
    </Select>
  );
}
