import { useTranslation } from 'react-i18next';
import { useEnumLabel } from '@/i18n';
import { domainColor } from '@/lib/domains';
import type { AbilityToken } from './parseAbility';
import { parseAbility } from './parseAbility';
import styles from './AbilityText.module.css';

function Token({ token }: { token: AbilityToken }) {
  const { t } = useTranslation('cards');
  const { label } = useEnumLabel();

  switch (token.kind) {
    case 'text':
      return <>{token.text}</>;

    case 'keyword':
      return <span className={styles.keyword}>{token.text}</span>;

    case 'energy':
      return (
        <span className={styles.symbol}>
          <span className={styles.energy} aria-hidden="true">
            {token.value}
          </span>
          <span className="sr-only">{t('ability.energy', { count: token.value })}</span>
        </span>
      );

    case 'exhaust':
      return (
        <span className={styles.symbol}>
          <ExhaustIcon aria-hidden="true" />
          <span className="sr-only">{t('ability.exhaust')}</span>
        </span>
      );

    case 'might':
      return (
        <span className={styles.symbol}>
          <MightIcon aria-hidden="true" />
          <span className="sr-only">{t('ability.might')}</span>
        </span>
      );

    case 'rune': {
      const isRainbow = token.domain === 'rainbow';
      const domainName = isRainbow ? '' : token.domain;
      const domainLabel = isRainbow
        ? t('ability.runeAny')
        : t('ability.rune', { domain: label('domain', domainName) });
      return (
        <span className={styles.symbol}>
          <span
            className={[styles.rune, isRainbow && styles.runeRainbow].filter(Boolean).join(' ')}
            style={isRainbow ? undefined : { background: domainColor(domainName) }}
            aria-hidden="true"
          />
          <span className="sr-only">{domainLabel}</span>
        </span>
      );
    }

    case 'reminder':
      return (
        <em className={styles.reminder}>
          {token.children.map((child, index) => (
            <Token key={index} token={child} />
          ))}
        </em>
      );

    default:
      return null;
  }
}

function ExhaustIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg className={styles.icon} viewBox="0 0 24 24" {...props}>
      <path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 14a5 5 0 0 1-3.5-8.6l7.1 7.1A5 5 0 0 1 12 17Z" />
    </svg>
  );
}

function MightIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg className={styles.icon} viewBox="0 0 24 24" {...props}>
      <path d="M12 2l2.5 6.5L21 9l-5.5 4.5L17 21 12 17 7 21l1.5-7.5L3 9l6.5-.5L12 2Z" />
    </svg>
  );
}

type AbilityTextProps = {
  text: string | null | undefined;
};

/** Rendered card ability text with game symbols (F2-f S9). */
export function AbilityText({ text }: AbilityTextProps) {
  const { t } = useTranslation('cards');
  const tokens = parseAbility(text);

  if (tokens.length === 0) {
    return <span className={styles.empty}>{t('ability.empty')}</span>;
  }

  return (
    <span className={styles.text}>
      {tokens.map((token, index) => (
        <Token key={index} token={token} />
      ))}
    </span>
  );
}
