import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { ProductsDesktop } from './ProductsDesktop';
import { ProductsMobile } from './ProductsMobile';
import { useProductsScreen } from './useProductsScreen';

/** `/products`: below 1240 px the F14-e layout, from there the desktop one (F14-f). */
export function ProductsPage() {
  const desktop = useMediaQuery(up('xl'));
  const screen = useProductsScreen();
  return desktop ? <ProductsDesktop s={screen} /> : <ProductsMobile s={screen} />;
}
