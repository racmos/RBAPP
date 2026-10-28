import type { CollectionScreen } from './useCollectionScreen';

export function CollectionDesktop({ s }: { s: CollectionScreen }) {
  return <div>{s.t('title')}</div>;
}
