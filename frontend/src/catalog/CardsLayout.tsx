import { Outlet } from 'react-router';
import type { CardDetailOutletContext } from './context';

/** Layout for the catalog routes (F2-f S4). For now it only renders the page outlet. */
export function CardsLayout() {
  const context: CardDetailOutletContext = { presentation: 'page' };
  return <Outlet context={context} />;
}
