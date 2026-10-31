import { useId, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { DebouncedInput } from '@/catalog';
import { PageHeader } from '@/components/ui/PageHeader';
import { SegmentedControl, type SegmentedOption } from '@/components/ui/SegmentedControl';
import { SettingsCard, SettingsRow } from '@/components/ui/SettingsCard';
import { Slider } from '@/components/ui/Slider';
import { useDocumentTitle } from '@/i18n';
import { up } from '@/lib/breakpoints';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { usePrefs, type Prefs } from '@/prefs';
import { BackgroundPreview } from './BackgroundPreview';
import styles from './InterfacePage.module.css';

const AUTO = 'auto';
type Auto<T extends string> = T | typeof AUTO;

/** A setting: its name and hint, and the control named by it. */
function Setting({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: (labelledBy: string) => ReactNode;
}) {
  const id = useId();
  return (
    <SettingsRow>
      <div className={styles.text}>
        <span id={id} className={styles.label}>
          {label}
        </span>
        <p className={styles.hint}>{hint}</p>
      </div>
      {children(id)}
    </SettingsRow>
  );
}

/** `null` (Auto) <-> the control's "auto" value. */
const toControl = <T extends string>(value: T | null): Auto<T> => value ?? AUTO;
const fromControl = <T extends string>(value: Auto<T>): T | null => (value === AUTO ? null : value);

/**
 * `/account/interface` (SHELL-7): density, accent, background and default collection view. Every
 * control applies live and saves optimistically (PREF-8); at `xl` a live preview sits beside them.
 * The app is English-only, so there is no language setting.
 */
export function InterfacePage() {
  const { t } = useTranslation('prefs');
  const { t: tCollection } = useTranslation('collection');
  const { prefs, effective, set, flush, offline } = usePrefs();
  const wide = useMediaQuery(up('xl'));
  useDocumentTitle(t('interface.title'));

  const density: SegmentedOption<Auto<NonNullable<Prefs['density']>>>[] = [
    { value: AUTO, label: t('interface.density.auto') },
    { value: 'compact', label: t('interface.density.compact') },
    { value: 'regular', label: t('interface.density.regular') },
    { value: 'comfy', label: t('interface.density.comfy') },
  ];
  const accent: SegmentedOption<NonNullable<Prefs['accent']>>[] = [
    { value: 'cyan', label: t('interface.accent.cyan') },
    { value: 'orange', label: t('interface.accent.orange') },
  ];
  const view: SegmentedOption<Auto<NonNullable<Prefs['collection_view']>>>[] = [
    { value: AUTO, label: t('interface.collectionView.auto') },
    { value: 'table', label: t('interface.collectionView.table') },
    { value: 'grid', label: t('interface.collectionView.grid') },
  ];

  return (
    <>
      <PageHeader title={t('interface.title')} subtitle={t('interface.subtitle')} />
      <div className={styles.layout}>
        <SettingsCard title={t('interface.appearance')} description={t('interface.appearanceHint')}>
          <Setting label={t('interface.density.label')} hint={t('interface.density.hint')}>
            {(labelledBy) => (
              <SegmentedControl
                labelledBy={labelledBy}
                options={density}
                value={toControl(prefs.density)}
                onChange={(value) => set('density', fromControl(value))}
                disabled={offline}
              />
            )}
          </Setting>

          <Setting label={t('interface.accent.label')} hint={t('interface.accent.hint')}>
            {(labelledBy) => (
              <SegmentedControl
                labelledBy={labelledBy}
                options={accent}
                value={effective.accent}
                onChange={(value) => set('accent', value)}
                disabled={offline}
              />
            )}
          </Setting>

          <SettingsRow>
            <div className={styles.slider}>
              <Slider
                label={t('interface.background.label')}
                value={effective.bgIntensity}
                min={0}
                max={100}
                unit="%"
                onChange={(value) => set('bg_intensity', value, { debounce: true })}
                onCommit={flush}
                disabled={offline}
              />
              <p className={styles.hint}>{t('interface.background.hint')}</p>
            </div>
          </SettingsRow>

          <Setting
            label={t('interface.collectionView.label')}
            hint={t('interface.collectionView.hint')}
          >
            {(labelledBy) => (
              <SegmentedControl
                labelledBy={labelledBy}
                options={view}
                value={toControl(prefs.collection_view)}
                onChange={(value) => set('collection_view', fromControl(value))}
                disabled={offline}
              />
            )}
          </Setting>
        </SettingsCard>

        <SettingsCard title={tCollection('settings.title')}>
          <Setting
            label={tCollection('settings.playsetSize')}
            hint={tCollection('settings.playsetHint')}
          >
            {(labelledBy) => (
              <DebouncedInput
                type="number"
                inputMode="numeric"
                aria-labelledby={labelledBy}
                min={1}
                max={9}
                disabled={offline}
                value={prefs.playset_size === null ? '' : String(prefs.playset_size)}
                onCommit={(next) => {
                  if (next === '') return set('playset_size', null);
                  const size = Number(next);
                  if (Number.isInteger(size) && size >= 1 && size <= 9) set('playset_size', size);
                }}
              />
            )}
          </Setting>
        </SettingsCard>

        {wide && <BackgroundPreview />}
      </div>
    </>
  );
}
