import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearToasts, dismissToast, getToasts, pushToast } from './toastStore';

describe('toastStore onExpire (F13-h S7)', () => {
  afterEach(() => clearToasts());

  it('runs once when the toast goes away without its action', () => {
    const onExpire = vi.fn();
    const id = pushToast({ kind: 'success', message: 'Saved.', onExpire });
    dismissToast(id);
    dismissToast(id);
    expect(onExpire).toHaveBeenCalledTimes(1);
    expect(getToasts()).toEqual([]);
  });

  it('never runs when the action dismissed the toast', () => {
    const onExpire = vi.fn();
    const id = pushToast({ kind: 'success', message: 'Saved.', onExpire });
    dismissToast(id, { byAction: true });
    expect(onExpire).not.toHaveBeenCalled();
  });
});
