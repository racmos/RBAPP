import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import { createI18n } from './index';
import { useEnumLabel } from './enumLabel';

async function prepare() {
  await createI18n();
}

describe('useEnumLabel', () => {
  it('labels a known domain', async () => {
    await prepare();
    const { result } = renderHook(() => useEnumLabel());
    expect(result.current.label('domain', 'Fury')).toBe('Fury');
    expect(result.current.label('condition', 'NM')).toBe('Near Mint (NM)');
  });

  it('labels a known rarity', async () => {
    await prepare();
    const { result } = renderHook(() => useEnumLabel());
    expect(result.current.label('rarity', 'Rare')).toBe('Rare');
  });

  it('falls back to the raw value when the enum is missing', async () => {
    await prepare();
    const { result } = renderHook(() => useEnumLabel());
    expect(result.current.label('domain', 'Void')).toBe('Void');
  });

  it('composes a card type label from supertype and type', async () => {
    await prepare();
    const { result } = renderHook(() => useEnumLabel());
    expect(result.current.typeLabel('Champion', 'Unit')).toBe('Champion Unit');
  });
});
