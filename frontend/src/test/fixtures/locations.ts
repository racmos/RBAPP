import type { LineLocations, StorageLocation } from '@/api/types';

const location = (overrides: Partial<StorageLocation>): StorageLocation => ({
  id: 1,
  code: 'B001-F001-P0001',
  description: null,
  position: 1,
  locked: false,
  deck_id: null,
  copies: 0,
  cards: 0,
  ...overrides,
});

/** Three locations in the user's order: a binder, a locked box and a mounted deck (F16-b). */
export const binder = location({
  id: 11,
  code: 'B001-F001-P0001',
  description: 'Red binder',
  position: 1,
  copies: 5,
  cards: 3,
});
export const lockedBox = location({
  id: 12,
  code: 'B001-F001-P0002',
  description: null,
  position: 2,
  locked: true,
  copies: 2,
  cards: 1,
});
export const deckLocation = location({
  id: 13,
  code: 'DECK-001',
  description: 'Ayla aggro',
  position: 3,
  locked: true,
  deck_id: 42,
  copies: 40,
  cards: 12,
});

export const storageLocations: StorageLocation[] = [binder, lockedBox, deckLocation];
export const UNASSIGNED_COPIES = 7;

/** Line 1201 of Ayla (3 copies): 1 in the binder, 1 in the locked box, 1 unassigned. */
export const aylaLineLocations: LineLocations = {
  locations: [
    { location_id: 11, code: binder.code, description: 'Red binder', locked: false, qty: 1 },
    { location_id: 12, code: lockedBox.code, description: null, locked: true, qty: 1 },
  ],
  unassigned: 1,
  total: 3,
};
