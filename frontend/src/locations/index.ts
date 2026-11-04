/**
 * What the collection uses of the storage locations (F16): the queries and the labels. The
 * screen itself is loaded by the router from `@/locations/LocationsPage`, so the collection
 * chunk does not carry it.
 */
export { useLocationLabel } from './labels';
export {
  useLineLocations,
  useLocations,
  useMoveLineLocations,
  usePutLineLocations,
} from './queries';
