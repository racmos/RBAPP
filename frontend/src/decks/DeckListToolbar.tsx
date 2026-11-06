import { useTranslation } from 'react-i18next';
import { DebouncedInput } from '@/catalog';
import { Button } from '@/components/ui/Button';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { DECK_LIST_SORTS, hasDeckFilters, type DeckListParams } from './deckListParams';
import styles from './DecksPage.module.css';

type Props = {
  params: DeckListParams;
  modes: readonly string[];
  shown: number;
  total: number;
  onChange: (patch: Partial<DeckListParams>, options?: { replace?: boolean }) => void;
  onClear: () => void;
};

/** Search, mode, legality and sort over the loaded decks, with how many are shown. */
export function DeckListToolbar({ params, modes, shown, total, onChange, onClear }: Props) {
  const { t } = useTranslation('decks');
  return (
    <section className={styles.toolbar} aria-label={t('toolbar.label')}>
      <div className={styles.search}>
        <Field label={t('toolbar.search')}>
          {(control) => (
            <DebouncedInput
              {...control}
              type="search"
              value={params.q}
              placeholder={t('toolbar.searchPlaceholder')}
              onCommit={(q) => onChange({ q }, { replace: true })}
            />
          )}
        </Field>
      </div>
      <Field label={t('toolbar.mode')}>
        {(control) => (
          <Select
            {...control}
            value={params.mode}
            onChange={(e) => onChange({ mode: e.target.value as DeckListParams['mode'] })}
          >
            <option value="all">{t('toolbar.allModes')}</option>
            {modes.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label={t('toolbar.legality')}>
        {(control) => (
          <Select
            {...control}
            value={params.legal}
            onChange={(e) => onChange({ legal: e.target.value as DeckListParams['legal'] })}
          >
            <option value="all">{t('toolbar.anyLegality')}</option>
            <option value="yes">{t('toolbar.legalInMode')}</option>
            <option value="no">{t('toolbar.notLegalInMode')}</option>
          </Select>
        )}
      </Field>
      <Field label={t('toolbar.sort')}>
        {(control) => (
          <Select
            {...control}
            value={params.sort}
            onChange={(e) => onChange({ sort: e.target.value as DeckListParams['sort'] })}
          >
            {DECK_LIST_SORTS.map((sort) => (
              <option key={sort} value={sort}>
                {t(`toolbar.sortBy.${sort}`)}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <div className={styles.toolbarEnd}>
        {hasDeckFilters(params) && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            {t('toolbar.clear')}
          </Button>
        )}
        <p className={styles.shown} aria-live="polite">
          {t('toolbar.shown', { shown, count: total })}
        </p>
      </div>
    </section>
  );
}
