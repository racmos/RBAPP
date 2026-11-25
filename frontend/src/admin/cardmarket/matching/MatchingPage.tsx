import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router';
import { useSearchNavigation } from '@/catalog';
import { useCardmarketStatus } from '@/admin/cardmarket/queries';
import { PageHeader } from '@/components/ui/PageHeader';
import { SegmentedControl, type SegmentedOption } from '@/components/ui/SegmentedControl';
import { useDocumentTitle } from '@/i18n';
import { useOnline } from '@/lib/useOnline';
import { AutoMatchPanel } from './AutoMatchPanel';
import { ExpansionsPanel } from './ExpansionsPanel';
import {
  TABS,
  apiQuery,
  canonicalSearch,
  matchingSearch,
  matchingTabUrl,
  parseTab,
  parseView,
  viewSearch,
  type MatchingTab,
  type MatchingView,
  type ViewTab,
} from './format';
import { IgnoredPanel } from './IgnoredPanel';
import { LinkDialog, type LinkSubject } from './LinkDialog';
import { ConflictsPanel, LinkedPanel } from './LinkedPanel';
import { MissingCardsPanel } from './MissingCardsPanel';
import { useIgnored, useLinks } from './queries';
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
 * mapping of the Cardmarket expansions to our sets (CM-d) and the missing promo cards (CM-h).
 * Four tabs in the order of the work (CM-l): Prepare (Expansions | Missing cards), Auto-match,
 * To link (| Ignored) and Linked (| Conflicts). The tab, its view and its filters live in the
 * URL; an old `?tab=` is rewritten with a replace.
 */
export function MatchingPage() {
  const { t } = useTranslation('admin');
  const offline = !useOnline();
  const [urlParams] = useSearchParams();
  const { setSearchParams } = useSearchNavigation();
  const [subject, setSubject] = useState<LinkSubject | null>(null);
  // an old or unknown tab renders in its new form at once; the URL follows with a replace
  const canonical = canonicalSearch(urlParams);
  const params = canonical ?? urlParams;
  const canonicalText = canonical?.toString() ?? null;
  const tab = parseTab(params.get('tab'));
  useDocumentTitle(t('matching.title'));

  useEffect(() => {
    if (canonicalText !== null) {
      setSearchParams(new URLSearchParams(canonicalText), { replace: true });
    }
  }, [canonicalText, setSearchParams]);

  const choose = (next: MatchingTab) => setSearchParams(matchingSearch(next, []));
  const chooseView = <T extends ViewTab>(viewTab: T, view: MatchingView<T>) =>
    setSearchParams((previous) => viewSearch(viewTab, view, previous));

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
        {tab === 'prepare' && (
          <PrepareTab
            view={parseView('prepare', params.get('view'))}
            choose={(view) => chooseView('prepare', view)}
            panel={panel}
          />
        )}
        {tab === 'auto' && <AutoMatchPanel {...panel} />}
        {tab === 'link' && (
          <ToLinkTab
            view={parseView('link', params.get('view'))}
            choose={(view) => chooseView('link', view)}
            panel={panel}
          />
        )}
        {tab === 'linked' && (
          <LinkedTab
            view={parseView('linked', params.get('view'))}
            choose={(view) => chooseView('linked', view)}
            panel={panel}
          />
        )}
      </div>
      <LinkDialog
        subject={subject}
        offline={offline}
        onClose={() => setSubject(null)}
        onOpenLink={(id) => setSearchParams(matchingSearch('linked', [['q', String(id)]]))}
      />
    </>
  );
}

type TabProps<T extends ViewTab> = {
  view: MatchingView<T>;
  choose: (view: MatchingView<T>) => void;
  panel: PanelProps;
};

/** The segmented control of a merged tab, at the left of its toolbar (CM-l S2-S4). */
function Views<T extends ViewTab>({
  tab,
  view,
  choose,
  options,
}: {
  tab: T;
  view: MatchingView<T>;
  choose: (view: MatchingView<T>) => void;
  options: SegmentedOption<MatchingView<T>>[];
}) {
  const { t } = useTranslation('admin');
  return (
    <div className={styles.views}>
      <SegmentedControl
        label={t(`matching.views.label.${tab}`)}
        options={options}
        value={view}
        onChange={choose}
      />
    </div>
  );
}

/** Prepare: the expansions to map and the missing cards to create (CM-l S2). */
function PrepareTab({ view, choose, panel }: TabProps<'prepare'>) {
  const { t } = useTranslation('admin');
  return (
    <>
      <Views
        tab="prepare"
        view={view}
        choose={choose}
        options={[
          { value: 'expansions', label: t('matching.views.expansions') },
          { value: 'missing', label: t('matching.views.missing') },
        ]}
      />
      {view === 'expansions' ? <ExpansionsPanel {...panel} /> : <MissingCardsPanel {...panel} />}
    </>
  );
}

/** To link and the ignore list, whose size the control shows (CM-l S3). */
function ToLinkTab({ view, choose, panel }: TabProps<'link'>) {
  const { t } = useTranslation('admin');
  const ignored = useIgnored().data?.items.length;
  return (
    <>
      <Views
        tab="link"
        view={view}
        choose={choose}
        options={[
          { value: 'link', label: t('matching.views.link') },
          { value: 'ignored', label: t('matching.views.ignored'), count: ignored },
        ]}
      />
      {view === 'link' ? <ToLinkPanel {...panel} /> : <IgnoredPanel {...panel} />}
    </>
  );
}

/** Every link and the conflicts, their count in warning tone when there is any (CM-l S4). */
function LinkedTab({ view, choose, panel }: TabProps<'linked'>) {
  const { t } = useTranslation('admin');
  // the query of the first page of the Conflicts view (it takes no filter): one request for both
  const conflicts = useLinks(apiQuery('conflicts', new URLSearchParams())).data?.meta
    .conflict_slots;
  return (
    <>
      <Views
        tab="linked"
        view={view}
        choose={choose}
        options={[
          { value: 'all', label: t('matching.views.all') },
          {
            value: 'conflicts',
            label: t('matching.views.conflicts'),
            count: conflicts,
            tone: conflicts ? 'warning' : 'neutral',
          },
        ]}
      />
      {view === 'all' ? <LinkedPanel {...panel} /> : <ConflictsPanel {...panel} />}
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
      <Link to={matchingTabUrl('prepare', { view: 'expansions' })} className={styles.back}>
        {t('cardmarket.unmappedExpansions', { count: status.data.unmapped_expansions })}
      </Link>
    </p>
  );
}

/** The four tabs: arrows, Home and End move between them. */
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
