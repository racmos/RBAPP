import { useTranslation } from 'react-i18next';
import styles from './LanguageToggle.module.css';
import { storeLang } from './resolveLang';
import { LANGUAGES, type Lang } from './resources';

type LanguageToggleProps = {
  /** Called after the language is applied; the preferences feature uses it to save to the account. */
  onChoose?: (lang: Lang) => void;
  className?: string;
};

/**
 * Switch the language. It always writes the device choice `rb_lang` (R4); saving it to the
 * account when signed in is the caller's business (`onChoose`, see `AccountLanguageToggle`).
 */
export function LanguageToggle({ onChoose, className }: LanguageToggleProps) {
  const { t, i18n } = useTranslation('prefs');

  const choose = (lang: Lang) => {
    storeLang(lang);
    void i18n.changeLanguage(lang);
    onChoose?.(lang);
  };

  return (
    <div
      role="group"
      aria-label={t('language.label')}
      className={[styles.group, className].filter(Boolean).join(' ')}
    >
      {LANGUAGES.map((lang) => (
        <button
          key={lang}
          type="button"
          lang={lang}
          className={styles.option}
          aria-label={t(`language.${lang}`)}
          aria-pressed={i18n.language === lang}
          onClick={() => choose(lang)}
        >
          {lang.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
