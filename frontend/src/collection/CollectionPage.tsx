import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { CollectionDesktop } from './CollectionDesktop';
import { CollectionMobile } from './CollectionMobile';
import { useCollectionScreen } from './useCollectionScreen';

/** `/collection`: below 1240 px the F3-g layout, from there the desktop one (F3-h). */
export function CollectionPage() {
  const desktop = useMediaQuery(up('xl'));
  const screen = useCollectionScreen(desktop);
  return desktop ? <CollectionDesktop s={screen} /> : <CollectionMobile s={screen} />;
}
