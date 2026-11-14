import { useState } from 'react';
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

/** The stored file that fits the box: 64 px up to 64 px, 256 px above (F9-i S11). */
export function avatarImageUrl(src: string, size: number): string {
  return `${src}${src.includes('?') ? '&' : '?'}size=${size <= 64 ? 64 : 256}`;
}

type AvatarProps = {
  name: string;
  /** Accessible name. Without it the avatar is decoration (the surrounding control is named). */
  label?: string;
  size?: number;
  /** The photo (`avatar_url`); the initials show without it or when it fails to load. */
  src?: string | null;
  className?: string;
};

export function Avatar({ name, label, size = 30, src, className }: AvatarProps) {
  // The photo that failed to load; a new photo is tried again.
  const [failed, setFailed] = useState<string | null>(null);
  const photo = src && src !== failed ? avatarImageUrl(src, size) : null;
  const box = { width: size, height: size };

  if (photo) {
    return (
      <span
        className={[styles.avatar, className].filter(Boolean).join(' ')}
        style={box}
        {...(label ? {} : { 'aria-hidden': true })}
      >
        <img
          className={styles.image}
          src={photo}
          alt={label ?? ''}
          width={size}
          height={size}
          onError={() => setFailed(src ?? null)}
        />
      </span>
    );
  }
  return (
    <span
      className={[styles.avatar, className].filter(Boolean).join(' ')}
      style={{ ...box, fontSize: Math.round(size * 0.42) }}
      {...(label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true })}
    >
      {initialsOf(name)}
    </span>
  );
}
