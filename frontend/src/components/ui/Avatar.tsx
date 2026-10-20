import styles from './Avatar.module.css';

/** Up to two letters: first letters of the first two words, or the first two letters of one word. */
export function initialsOf(name: string): string {
  const words = name
    .trim()
    .split(/[\s._-]+/)
    .filter(Boolean);
  if (words.length === 0) return '?';
  const letters =
    words.length === 1
      ? Array.from(words[0]).slice(0, 2)
      : words.slice(0, 2).map((w) => Array.from(w)[0]);
  return letters.join('').toLocaleUpperCase();
}

type AvatarProps = {
  name: string;
  /** Accessible name. Without it the avatar is decoration (the surrounding control is named). */
  label?: string;
  size?: number;
  className?: string;
};

export function Avatar({ name, label, size = 30, className }: AvatarProps) {
  return (
    <span
      className={[styles.avatar, className].filter(Boolean).join(' ')}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.42) }}
      {...(label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true })}
    >
      {initialsOf(name)}
    </span>
  );
}
