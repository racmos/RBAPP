import { useTranslation } from 'react-i18next';
import styles from './LanguageToggle.module.css';
import { storeLang } from './resolveLang';
import { LANGUAGES, type Lang } from './resources';

/**
 * Switch the language. It always writes the device choice `rb_lang` (R4); persisting it to the
 * account when signed in arrives with the preferences sync (unit e).
 */
export function LanguageToggle() {
  const { t, i18n } = useTranslation('prefs');

  const choose = (lang: Lang) => {
    storeLang(lang);
    void i18n.changeLanguage(lang);
  };

  return (
    <div role="group" aria-label={t('language.label')} className={styles.group}>
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
