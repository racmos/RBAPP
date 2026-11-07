import { describe, expect, it } from 'vitest';
import { cardInput, toForm } from './CardEditor';

describe('cardInput (the body of a card write, shared with CM-c)', () => {
  it('keeps the name, turns blank texts into null and parses the numbers', () => {
    const form = {
      ...toForm(null),
      set_id: 'OGN',
      card_id: '066',
      name: 'Ahri, Alluring',
      domain: 'Calm',
      energy: ' 3 ',
      power: '',
      might: '0',
      rarity: 'Common',
    };
    // the keys stay out: a PATCH never sends them, a create adds them in front
    expect(cardInput(form)).toStrictEqual({
      name: 'Ahri, Alluring',
      domain: 'Calm',
      type: null,
      tags: null,
      energy: 3,
      power: null,
      might: 0,
      ability: null,
      rarity: 'Common',
      artist: null,
      image_url: null,
    });
  });
});
