import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { LocationSheet, NewLocationSheet } from './LocationSheets';
import { LocationsDesktop } from './LocationsDesktop';
import { LocationsMobile } from './LocationsMobile';
import { useLocationsScreen } from './useLocationsScreen';

/** `/locations`: below 1240 px the list (F16-c), from there the table and the wide panel (F16-d). */
export function LocationsPage() {
  const desktop = useMediaQuery(up('xl'));
  const screen = useLocationsScreen();
  const { offline, editing, setEditing, creating, setCreating } = screen;
  return (
    <>
      {desktop ? <LocationsDesktop s={screen} /> : <LocationsMobile s={screen} />}
      {creating && <NewLocationSheet offline={offline} onClose={() => setCreating(false)} />}
      {editing && (
        <LocationSheet
          key={editing.id}
          location={editing}
          offline={offline}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}
