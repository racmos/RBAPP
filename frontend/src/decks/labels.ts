import type { DeckCard } from '@/api/types';

/**
 * How a deck names a card: a legend stores its bare name and has its champion as the first tag,
 * so it reads `Tag, Name` ("Riven, The Exile") unless the name already starts with the tag, as
 * the text export writes it (F5-e).
 */
export function cardLabel(card: Pick<DeckCard, 'name' | 'type' | 'tags'>): string {
  const tag = card.tags[0];
  if (card.type !== 'Legend' || !tag || card.name.startsWith(tag)) return card.name;
  return `${tag}, ${card.name}`;
}

export const refKey = (ref: { set: string; id: string }) => `${ref.set}-${ref.id}`;
