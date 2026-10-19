import { ICONS, type IconName } from './icons';

type IconProps = {
  name: IconName;
  /** Accessible name. Without it the icon is decorative and hidden from assistive technology. */
  title?: string;
  size?: number;
  className?: string;
};

export function Icon({ name, title, size = 18, className }: IconProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...(title ? { role: 'img', 'aria-label': title } : { 'aria-hidden': true })}
    >
      {title && <title>{title}</title>}
      {ICONS[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
