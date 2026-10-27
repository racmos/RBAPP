import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

type EnumKind = 'domain' | 'type' | 'supertype' | 'rarity' | 'mode';

/** Translate game enumeration values; missing keys fall back to the raw value. */
export function useEnumLabel() {
  const { t } = useTranslation('enums');

  const label = useCallback(
    (kind: EnumKind, value: string): string => {
      const key = `${kind}.${value}`;
      // Typed resources reject dynamic keys; cast to string for runtime lookup.
      const translated = (t as (k: string) => string)(key);
      // The configured missing-key handler returns '' for missing keys.
      return translated === '' ? value : translated;
    },
    [t],
  );

  const typeLabel = useCallback(
    (supertype: string | null, type: string): string => {
      const superLabel = supertype ? label('supertype', supertype) : '';
      const typeLabelValue = label('type', type);
      return supertype ? `${superLabel} ${typeLabelValue}` : typeLabelValue;
    },
    [label],
  );

  return { label, typeLabel };
}
