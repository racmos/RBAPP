import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { contrast } from '@/lib/contrast';
import { domainColor } from '@/lib/domains';
import { useEnumLabel } from '@/i18n';
import { DOMAIN_GLYPHS } from './CardArtPlaceholder';
import styles from './DomainPips.module.css';

type DomainPipsProps = {
  domains: string[];
  size?: number;
  className?: string;
};

function glyphInk(background: string): string {
  const white = contrast('#ffffff', background);
  const dark = contrast('#06222c', background);
  return white >= dark ? '#ffffff' : '#06222c';
}

export function DomainPips({ domains, size = 20, className }: DomainPipsProps) {
  const { i18n } = useTranslation();
  const { label } = useEnumLabel();

  const ariaLabel = useMemo(() => {
    if (domains.length === 0) return '';
    const translated = domains.map((d) => label('domain', d));
    return new Intl.ListFormat(i18n.language, { type: 'conjunction' }).format(translated);
  }, [domains, i18n.language, label]);

  if (domains.length === 0) return null;

  return (
    <span
      className={[styles.group, className].filter(Boolean).join(' ')}
      role="img"
      aria-label={ariaLabel}
    >
      {domains.map((domain) => {
        const color = domainColor(domain);
        const glyph = DOMAIN_GLYPHS[domain] ?? DOMAIN_GLYPHS.Colorless;
        return (
          <span
            key={domain}
            className={styles.pip}
            style={{
              width: size,
              height: size,
              background: color,
              color: glyphInk(color),
            }}
            aria-hidden="true"
          >
            <svg viewBox="0 0 24 24" className={styles.glyph}>
              <path d={glyph} fill="currentColor" />
            </svg>
          </span>
        );
      })}
    </span>
  );
}
