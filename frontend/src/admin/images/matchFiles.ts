/**
 * Bulk image upload matching (F13-h S6): each file is matched by its file name stem to a card
 * (`ogn_66`, `OGN-66`, `plat_sfd189`: case-insensitive, `-` and `_` alike) or a product (its
 * id). Pure: the catalog lookup is passed in, so the dialog resolves the keys first.
 */

/** The largest file the server accepts (`image_upload.MAX_FILE_BYTES`). */
export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_BATCH_FILES = 50;
export const IMAGE_ACCEPT = 'image/png,image/jpeg,image/webp';

const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);
const IMAGE_EXTENSION = /\.(png|jpe?g|webp)$/i;
const CARD_STEM = /^([a-z0-9]+)[-_]([a-z0-9]+)$/;
const PRODUCT_STEM = /^[0-9]+$/;

export type ImageTab = 'cards' | 'products';
export type FileLike = { name: string; size: number; type: string };
export type MatchStatus = 'ready' | 'no_match' | 'several' | 'too_large' | 'not_image';

/** A card (`key` = `SET-id`) or a product (`key` = its id) a file can be uploaded to. */
export type ImageTarget = { kind: 'card' | 'product'; key: string; name: string };

export type MatchRow<F extends FileLike = FileLike> = {
  file: F;
  /** The catalog key read from the file name, or null when the name gives none. */
  key: string | null;
  target: ImageTarget | null;
  status: MatchStatus;
  /** The target was chosen by hand. */
  manual: boolean;
};

const stemOf = (name: string) => name.replace(/\.[^.]*$/, '').toLowerCase();

/** `SET-id` (set upper case, id lower case) for the cards tab, the product id for the other. */
export function lookupKey(name: string, tab: ImageTab): string | null {
  const stem = stemOf(name);
  if (tab === 'products') {
    if (!PRODUCT_STEM.test(stem)) return null;
    const id = Number(stem);
    return Number.isSafeInteger(id) && id > 0 ? String(id) : null;
  }
  const match = CARD_STEM.exec(stem);
  return match ? `${match[1].toUpperCase()}-${match[2]}` : null;
}

/** PNG, JPEG or WebP by its type, or by its extension when the browser gives no type. */
export const isImageFile = (file: FileLike): boolean =>
  file.type ? IMAGE_TYPES.has(file.type) : IMAGE_EXTENSION.test(file.name);

/**
 * One row per file, in order: `not_image`, `too_large`, `no_match` (no key, or no item with
 * it), `several` (two or more files for the same item), else `ready`. `manual` maps a file's
 * index to a target chosen by hand, which wins over the name.
 */
export function matchFiles<F extends FileLike>(
  files: readonly F[],
  tab: ImageTab,
  resolve: (key: string) => ImageTarget | null | undefined,
  manual: Readonly<Record<number, ImageTarget>> = {},
): MatchRow<F>[] {
  const rows = files.map((file, index): MatchRow<F> => {
    const key = lookupKey(file.name, tab);
    const chosen = manual[index];
    const target = chosen ?? (key ? (resolve(key) ?? null) : null);
    let status: MatchStatus = 'ready';
    if (!isImageFile(file)) status = 'not_image';
    else if (file.size > MAX_IMAGE_BYTES) status = 'too_large';
    else if (!target) status = 'no_match';
    return { file, key, target, status, manual: chosen !== undefined };
  });
  const counts = new Map<string, number>();
  for (const row of rows) {
    if (row.status === 'ready' && row.target) {
      const id = `${row.target.kind}:${row.target.key}`;
      counts.set(id, (counts.get(id) ?? 0) + 1);
    }
  }
  return rows.map((row) =>
    row.status === 'ready' &&
    row.target &&
    (counts.get(`${row.target.kind}:${row.target.key}`) ?? 0) > 1
      ? { ...row, status: 'several' }
      : row,
  );
}
