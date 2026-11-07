import { useRef, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router';
import { useSearchNavigation } from '@/catalog';
import { useCardmarketStatus } from '@/admin/cardmarket/queries';
import { PageHeader } from '@/components/ui/PageHeader';
import { useDocumentTitle } from '@/i18n';
import { useOnline } from '@/lib/useOnline';
import { AutoMatchPanel } from './AutoMatchPanel';
import { ExpansionsPanel } from './ExpansionsPanel';
import { TABS, parseTab, type MatchingTab } from './format';
import { IgnoredPanel } from './IgnoredPanel';
import { LinkDialog, type LinkSubject } from './LinkDialog';
import { ConflictsPanel, LinkedPanel } from './LinkedPanel';
import { ToLinkPanel } from './ToLinkPanel';
import styles from './MatchingPage.module.css';

/** What every panel gets: the URL filters, their setters and the link dialog. */
export type PanelProps = {
  params: URLSearchParams;
  /** Set (or clear, with null or '') one filter; the page goes back to 1. */
  setParam: (key: string, value: string | null) => void;
  setPage: (page: number) => void;
  offline: boolean;
  openDialog: (subject: LinkSubject) => void;
};

/**
 * Cardmarket matching workbench (CM-b): link the products the daily load could not match,
 * unlink or relink the wrong ones, the conflicts, the ignore list, the auto-match and the
 * mapping of the Cardmarket expansions to our sets (CM-d).
 * The tab and its filters live in the URL.
 */
export function MatchingPage() {
  const { t } = useTranslation('admin');
  const offline = !useOnline();
  const [params] = useSearchParams();
  const { setSearchParams } = useSearchNavigation();
  const [subject, setSubject] = useState<LinkSubject | null>(null);
  const tab = parseTab(params.get('tab'));
  useDocumentTitle(t('matching.title'));

  const choose = (next: MatchingTab) =>
    setSearchParams(new URLSearchParams(next === 'link' ? {} : { tab: next }));

  const setParam = (key: string, value: string | null) =>
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value === null || value === '') next.delete(key);
        else next.set(key, value);
        next.delete('page');
        return next;
      },
      { replace: true },
    );
  const setPage = (page: number) =>
    setSearchParams((previous) => {
      const next = new URLSearchParams(previous);
      if (page > 1) next.set('page', String(page));
      else next.delete('page');
      return next;
    });

  const panel: PanelProps = { params, setParam, setPage, offline, openDialog: setSubject };

  return (
    <>
      <PageHeader title={t('matching.title')} subtitle={t('matching.subtitle')} />
      <div className={styles.top}>
        <Link to="/admin/cardmarket" className={styles.back}>
          {t('matching.back')}
        </Link>
        <Counters />
      </div>
      <Tabs tab={tab} choose={choose} />
      <div
        role="tabpanel"
        id={`matching-panel-${tab}`}
        aria-labelledby={`matching-tab-${tab}`}
        className={styles.panel}
      >
        {/* the auto-match tab has its own visible section headings */}
        {tab !== 'auto' && <h2 className="sr-only">{t(`matching.tabs.${tab}`)}</h2>}
        {tab === 'link' && <ToLinkPanel {...panel} />}
        {tab === 'linked' && <LinkedPanel {...panel} />}
        {tab === 'conflicts' && <ConflictsPanel {...panel} />}
        {tab === 'ignored' && <IgnoredPanel {...panel} />}
        {tab === 'auto' && <AutoMatchPanel {...panel} />}
        {tab === 'expansions' && <ExpansionsPanel {...panel} />}
      </div>
      <LinkDialog
        subject={subject}
        offline={offline}
        onClose={() => setSubject(null)}
        onOpenLink={(id) => setSearchParams(new URLSearchParams({ tab: 'linked', q: String(id) }))}
      />
    </>
  );
}

function Counters() {
  const { t } = useTranslation('admin');
  const status = useCardmarketStatus();
  if (!status.data) return null;
  return (
    <p className={styles.counters}>
      <span>{t('cardmarket.unmatched', { count: status.data.unmatched })}</span>
      <Link to="/admin/cardmarket/matching?tab=expansions" className={styles.back}>
        {t('cardmarket.unmappedExpansions', { count: status.data.unmapped_expansions })}
      </Link>
    </p>
  );
}

/** The six sections as tabs: arrows, Home and End move between them. */
function Tabs({ tab, choose }: { tab: MatchingTab; choose: (tab: MatchingTab) => void }) {
  const { t } = useTranslation('admin');
  const refs = useRef<Partial<Record<MatchingTab, HTMLButtonElement | null>>>({});

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = TABS.indexOf(tab);
    let next: MatchingTab | undefined;
    if (event.key === 'ArrowRight') next = TABS[(index + 1) % TABS.length];
    else if (event.key === 'ArrowLeft') next = TABS[(index - 1 + TABS.length) % TABS.length];
    else if (event.key === 'Home') next = TABS[0];
    else if (event.key === 'End') next = TABS[TABS.length - 1];
    if (!next) return;
    event.preventDefault();
    choose(next);
    refs.current[next]?.focus();
  };

  return (
    <div role="tablist" aria-label={t('matching.tabsLabel')} className={styles.tabs}>
      {TABS.map((name) => (
        <button
          key={name}
          ref={(node) => {
            refs.current[name] = node;
          }}
          type="button"
          role="tab"
          id={`matching-tab-${name}`}
          aria-controls={`matching-panel-${name}`}
          aria-selected={tab === name}
          tabIndex={tab === name ? 0 : -1}
          className={styles.tab}
          onClick={() => choose(name)}
          onKeyDown={onKeyDown}
        >
          {t(`matching.tabs.${name}`)}
        </button>
      ))}
    </div>
  );
}
