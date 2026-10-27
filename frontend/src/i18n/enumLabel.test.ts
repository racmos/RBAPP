import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import { createI18n } from './index';
import { useEnumLabel } from './enumLabel';

async function prepare(lang: 'es' | 'en') {
  await createI18n(lang);
}

describe('useEnumLabel', () => {
  it('translates a known domain in Spanish', async () => {
    await prepare('es');
    const { result } = renderHook(() => useEnumLabel());
    expect(result.current.label('domain', 'Fury')).toBe('Furia');
  });

  it('translates a known rarity in English', async () => {
    await prepare('en');
    const { result } = renderHook(() => useEnumLabel());
    expect(result.current.label('rarity', 'Rare')).toBe('Rare');
  });

  it('falls back to the raw value when the enum is missing', async () => {
    await prepare('es');
    const { result } = renderHook(() => useEnumLabel());
    expect(result.current.label('domain', 'Void')).toBe('Void');
  });

  it('composes a card type label from supertype and type', async () => {
    await prepare('en');
    const { result } = renderHook(() => useEnumLabel());
    expect(result.current.typeLabel('Champion', 'Unit')).toBe('Champion Unit');
  });
});
