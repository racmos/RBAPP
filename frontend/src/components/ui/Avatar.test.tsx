/** F9-i S11 (AC4): the avatar shows the photo when it has one, in the right size, and falls
    back to the initials when the image does not load. */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Avatar, avatarImageUrl } from './Avatar';

const SRC = '/riftbound/api/v1/users/7/avatar?v=3';

describe('Avatar (F9-i S11)', () => {
  it('shows the initials without a photo', () => {
    const { container } = render(<Avatar name="Ada Lovelace" />);
    expect(container.querySelector('img')).toBeNull();
    expect(container).toHaveTextContent('AL');
  });

  it('shows the photo, decorative without a label', () => {
    const { container } = render(<Avatar name="ada" src={SRC} />);
    const img = container.querySelector('img');
    expect(img).not.toBeNull();
    expect(img).toHaveAttribute('alt', '');
    expect(img).toHaveAttribute('src', `${SRC}&size=64`);
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true');
    expect(container).not.toHaveTextContent('AD');
  });

  it('names the photo with the label', () => {
    render(<Avatar name="ada" label="Profile photo of Ada" src={SRC} size={80} />);
    const img = screen.getByRole('img', { name: 'Profile photo of Ada' });
    expect(img.tagName).toBe('IMG');
    expect(img).toHaveAttribute('src', `${SRC}&size=256`);
  });

  it('picks the 64 px file up to 64 px and the 256 px file above', () => {
    expect(avatarImageUrl(SRC, 30)).toBe(`${SRC}&size=64`);
    expect(avatarImageUrl(SRC, 64)).toBe(`${SRC}&size=64`);
    expect(avatarImageUrl(SRC, 65)).toBe(`${SRC}&size=256`);
    expect(avatarImageUrl('/riftbound/api/v1/users/7/avatar', 42)).toBe(
      '/riftbound/api/v1/users/7/avatar?size=64',
    );
  });

  it('falls back to the initials when the image fails to load', () => {
    const { container } = render(<Avatar name="ada" label="Profile photo of ada" src={SRC} />);
    fireEvent.error(container.querySelector('img') as HTMLImageElement);
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByRole('img', { name: 'Profile photo of ada' })).toHaveTextContent('AD');
  });

  it('tries again when the photo changes', () => {
    const { container, rerender } = render(<Avatar name="ada" src={SRC} />);
    fireEvent.error(container.querySelector('img') as HTMLImageElement);
    expect(container.querySelector('img')).toBeNull();
    rerender(<Avatar name="ada" src="/riftbound/api/v1/users/7/avatar?v=4" />);
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      '/riftbound/api/v1/users/7/avatar?v=4&size=64',
    );
  });
});
