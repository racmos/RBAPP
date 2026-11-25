import { useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { listAdminCards, listAdminProducts } from '@/api/endpoints';
import { DebouncedInput } from '@/catalog';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { TableScroll } from '@/components/ui/TableScroll';
import {
  IMAGE_ACCEPT,
  MAX_BATCH_FILES,
  lookupKey,
  matchFiles,
  type ImageTab,
  type ImageTarget,
  type MatchStatus,
} from './matchFiles';
import { runBatch } from './runBatch';
import { uploadErrorText } from './UploadDialog';
import { cardTarget, productTarget, sendImage, type UploadTarget } from './uploadImage';
import styles from './ImagesPage.module.css';

/** A catalog item a file can go to: what the matcher compares and what the upload needs. */
type Found = { target: ImageTarget; upload: UploadTarget };
type Sent = { state: 'uploading' | 'done' | 'failed'; error?: string };

const STATUS_TONE: Record<MatchStatus | Sent['state'], 'success' | 'warning' | 'danger' | 'muted'> =
  {
    ready: 'success',
    no_match: 'warning',
    several: 'warning',
    too_large: 'danger',
    not_image: 'danger',
    uploading: 'muted',
    done: 'success',
    failed: 'danger',
  };

/** Search the catalog of a tab; `exact` keeps only the item whose key is `query`. */
async function searchCatalog(tab: ImageTab, query: string, signal?: AbortSignal): Promise<Found[]> {
  if (tab === 'cards') {
    const data = await listAdminCards({ q: query, per_page: '50' }, signal);
    return data.items.map((card) => ({
      target: { kind: 'card', key: card.key, name: card.name },
      upload: cardTarget(card),
    }));
  }
  const data = await listAdminProducts(
    new URLSearchParams({ q: query, per_page: '50' }).toString(),
    signal,
  );
  return data.items.map((product) => ({
    target: { kind: 'product', key: String(product.id), name: product.name },
    upload: productTarget(product),
  }));
}

/** The item whose key is exactly `key` (`SET-id` any case, or the product id), if any. */
async function resolveKey(tab: ImageTab, key: string, signal?: AbortSignal) {
  const found = await searchCatalog(tab, key, signal);
  return found.find((item) => item.target.key.toLowerCase() === key.toLowerCase()) ?? null;
}

/**
 * Upload several images (F13-h S6): each file is matched by its name to a card or a product of
 * the tab, the admin checks the table (and assigns the unmatched files by hand), then the ready
 * files are sent two at a time; one failure never stops the others.
 */
export function BulkUploadDialog({
  tab,
  offline,
  onClose,
}: {
  tab: ImageTab;
  offline: boolean;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation('admin');
  const { t: common } = useTranslation('common');
  const input = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [tooMany, setTooMany] = useState(false);
  const [manual, setManual] = useState<Record<number, Found>>({});
  const [assigning, setAssigning] = useState<number | null>(null);
  const [sent, setSent] = useState<Record<number, Sent>>({});
  const [done, setDone] = useState<number | null>(null);
  const sending = done !== null && Object.values(sent).some((one) => one.state === 'uploading');

  const keys = useMemo(
    () =>
      [
        ...new Set(files.map((file) => lookupKey(file.name, tab)).filter((key) => key !== null)),
      ].sort(),
    [files, tab],
  );
  const resolved = useQuery({
    queryKey: ['admin', 'images', 'resolve', tab, keys.join(',')],
    queryFn: async ({ signal }) => {
      const entries = await Promise.all(
        keys.map(async (key) => [key, await resolveKey(tab, key, signal)] as const),
      );
      return new Map(entries);
    },
    enabled: keys.length > 0,
  });

  const byKey = new Map<string, Found>();
  for (const found of [...(resolved.data?.values() ?? []), ...Object.values(manual)]) {
    if (found) byKey.set(found.target.key, found);
  }
  const rows = matchFiles(
    files,
    tab,
    (key) => resolved.data?.get(key)?.target ?? null,
    Object.fromEntries(Object.entries(manual).map(([index, found]) => [index, found.target])),
  );
  const ready = rows.flatMap((row, index) => (row.status === 'ready' ? [index] : []));
  const started = done !== null;
  const failed = Object.values(sent).filter((one) => one.state === 'failed').length;
  const uploaded = Object.values(sent).filter((one) => one.state === 'done').length;

  const choose = (list: FileList | null) => {
    const picked = Array.from(list ?? []);
    setTooMany(picked.length > MAX_BATCH_FILES);
    setFiles(picked.slice(0, MAX_BATCH_FILES));
    setManual({});
    setSent({});
    setDone(null);
    setAssigning(null);
  };

  const confirm = async () => {
    setDone(0);
    setSent(Object.fromEntries(ready.map((index) => [index, { state: 'uploading' }])));
    await runBatch(
      ready,
      async (index) => {
        const target = rows[index].target;
        const found = target && byKey.get(target.key);
        if (!found) throw new Error('no target');
        try {
          await sendImage(found.upload, files[index]);
          setSent((current) => ({ ...current, [index]: { state: 'done' } }));
        } catch (error) {
          setSent((current) => ({
            ...current,
            [index]: { state: 'failed', error: uploadErrorText(error, i18n) },
          }));
          throw error;
        }
      },
      { concurrency: 2, onSettled: (count) => setDone(count) },
    );
  };

  return (
    <Modal open onClose={onClose} title={t('images.bulk.title')} size="lg" dismissible={!sending}>
      <div className={styles.preview}>
        <p className={styles.hint}>{t(`images.bulk.hint.${tab}`)}</p>
        <div>
          <Button
            variant="ghost"
            disabled={offline || sending}
            onClick={() => input.current?.click()}
          >
            {t('images.bulk.choose')}
          </Button>
          <input
            ref={input}
            type="file"
            accept={IMAGE_ACCEPT}
            multiple
            hidden
            tabIndex={-1}
            onChange={(event) => {
              choose(event.target.files);
              event.target.value = '';
            }}
          />
        </div>
        {tooMany && (
          <p role="alert" className={styles.hint}>
            {t('images.bulk.tooMany', { max: MAX_BATCH_FILES })}
          </p>
        )}
        {resolved.isFetching && <p className={styles.hint}>{t('images.bulk.checking')}</p>}
        {files.length > 0 && (
          <TableScroll>
            <table className={styles.bulkTable}>
              <caption className="sr-only">{t('images.bulk.caption')}</caption>
              <thead>
                <tr>
                  <th scope="col">{t('images.bulk.columns.file')}</th>
                  <th scope="col">{t('images.bulk.columns.target')}</th>
                  <th scope="col">{t('images.bulk.columns.status')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => {
                  const state = sent[index];
                  const status = state?.state ?? row.status;
                  return (
                    <tr key={`${row.file.name}-${index}`}>
                      <td className={styles.fileName}>{row.file.name}</td>
                      <td>
                        {row.target ? `${row.target.key} · ${row.target.name}` : '—'}
                        {!started && (row.status === 'no_match' || row.status === 'several') && (
                          <div>
                            <Button
                              size="sm"
                              variant="ghost"
                              aria-label={t('images.bulk.assignFor', { file: row.file.name })}
                              aria-expanded={assigning === index}
                              onClick={() => setAssigning(assigning === index ? null : index)}
                            >
                              {t('images.bulk.assign')}
                            </Button>
                            {assigning === index && (
                              <TargetSearch
                                tab={tab}
                                onPick={(found) => {
                                  setManual((current) => ({ ...current, [index]: found }));
                                  setAssigning(null);
                                }}
                              />
                            )}
                          </div>
                        )}
                      </td>
                      <td>
                        <Badge tone={STATUS_TONE[status]}>
                          {t(`images.bulk.status.${status}`)}
                        </Badge>
                        {state?.error && <div className={styles.hint}>{state.error}</div>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableScroll>
        )}
        {started && (
          <>
            <progress
              className={styles.progress}
              max={ready.length || 1}
              value={done ?? 0}
              aria-label={t('images.bulk.progress', { done: done ?? 0, total: ready.length })}
            />
            <p role="status" className={styles.hint}>
              {sending
                ? t('images.bulk.progress', { done: done ?? 0, total: ready.length })
                : t('images.bulk.summary', { ok: uploaded, failed })}
            </p>
          </>
        )}
        <div className={styles.previewActions}>
          <Button variant="ghost" disabled={sending} onClick={onClose}>
            {common('actions.close')}
          </Button>
          {!started && (
            <Button
              disabled={offline || ready.length === 0 || resolved.isFetching}
              onClick={() => void confirm()}
            >
              {t('images.bulk.confirm', { count: ready.length })}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}

/** A search over the tab's catalog to assign a file by hand (S6). */
function TargetSearch({ tab, onPick }: { tab: ImageTab; onPick: (found: Found) => void }) {
  const { t } = useTranslation('admin');
  const [query, setQuery] = useState('');
  const results = useQuery({
    queryKey: ['admin', 'images', 'search', tab, query],
    queryFn: ({ signal }) => searchCatalog(tab, query, signal),
    enabled: query.length > 0,
  });
  return (
    <div className={styles.search}>
      <DebouncedInput
        aria-label={t(`images.bulk.search.${tab}`)}
        placeholder={t(`images.bulk.search.${tab}`)}
        value={query}
        onCommit={(next) => setQuery(next.trim())}
      />
      {results.data && results.data.length === 0 && (
        <p className={styles.hint}>{t('images.bulk.noResults')}</p>
      )}
      {results.data && results.data.length > 0 && (
        <ul className={styles.results}>
          {results.data.slice(0, 8).map((found) => (
            <li key={found.target.key}>
              <Button
                size="sm"
                variant="ghost"
                aria-label={t('images.bulk.pick', {
                  name: `${found.target.key} ${found.target.name}`,
                })}
                onClick={() => onPick(found)}
              >
                {found.target.key} · {found.target.name}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
