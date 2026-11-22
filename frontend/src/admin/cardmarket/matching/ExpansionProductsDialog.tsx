import { useTranslation } from 'react-i18next';
import type {
  CardmarketExpansion,
  CardmarketExpansionItem,
  CardmarketExpansionSet,
} from '@/api/endpoints';
import { Modal } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { ExpansionProducts } from './ExpansionProducts';
import { useExpansions } from './queries';

/**
 * The list row of an expansion the expansions list does not have: what the product knows of it
 * (the products dialog reads its own figures from the products endpoint).
 */
function itemFrom(
  expansion: CardmarketExpansion,
  sets: CardmarketExpansionSet[],
): CardmarketExpansionItem {
  return {
    id: expansion.id,
    name: expansion.name,
    products_count: 0,
    singles_count: 0,
    sealed_count: 0,
    mapped_set_id: expansion.set_id,
    mapped_set_name: sets.find((set) => set.id === expansion.set_id)?.name ?? null,
    sample_products: [],
    price_range: null,
    first_seen: null,
    suggested_set_id: null,
    suggested_set_name: null,
    suggested_confidence: null,
    suggested_count: null,
    linked_count: 0,
  };
}

function Body({ expansion, offline }: { expansion: CardmarketExpansion; offline: boolean }) {
  const { t } = useTranslation('admin');
  // the row of the Expansions tab (cached when it was open), every expansion of the latest load
  const query = useExpansions(false);
  if (query.isPending && !offline) {
    return <Skeleton label={t('matching.expansions.products.list')} lines={6} />;
  }
  const item =
    query.data?.items.find((one) => one.id === expansion.id) ??
    itemFrom(expansion, query.data?.sets ?? []);
  return <ExpansionProducts item={item} offline={offline} />;
}

/**
 * "Expansion products" of a product to link (CM-i): the products dialog of the Expansions tab
 * (CM-f/CM-g) for the product's expansion, read-only (no map form), opened on top of whatever
 * is open so its state stays; focus goes back to the opener on close.
 */
export function ExpansionProductsDialog({
  expansion,
  offline,
  onClose,
}: {
  expansion: CardmarketExpansion | null;
  offline: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation('admin');
  const name = expansion
    ? (expansion.name ?? t('matching.expansions.unnamed', { id: expansion.id }))
    : '';
  return (
    <Modal
      open={expansion !== null}
      title={expansion ? t('matching.expansions.products.title', { name }) : ''}
      size="xl"
      fullScreenBelow="md"
      onClose={onClose}
    >
      {expansion && <Body key={expansion.id} expansion={expansion} offline={offline} />}
    </Modal>
  );
}
