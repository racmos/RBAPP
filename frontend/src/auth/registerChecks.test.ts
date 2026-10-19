import { describe, expect, it } from 'vitest';
import { checkRegister } from './registerChecks';

const valid = { username: 'new_user', email: 'new@example.com', password: 'longenough1' };
const codes = (values: Partial<typeof valid>) =>
  checkRegister({ ...valid, ...values }).map(({ field, code }) => `${field}:${code}`);

describe('checkRegister (mirrors RegisterRequest, FAUTH-4)', () => {
  it('accepts valid input and the boundary lengths', () => {
    expect(checkRegister(valid)).toEqual([]);
    expect(checkRegister({ username: 'abc', email: 'a@b.co', password: '12345678' })).toEqual([]);
    expect(
      checkRegister({
        username: 'a.b-c_9'.padEnd(32, 'x'),
        email: 'a@b.co',
        password: 'x'.repeat(128),
      }),
    ).toEqual([]);
  });

  it('requires every field', () => {
    expect(codes({ username: '', email: '', password: '' })).toEqual([
      'username:required',
      'email:required',
      'password:required',
    ]);
    expect(codes({ username: '   ' })).toEqual(['username:required']);
  });

  it.each(['ab', 'a'.repeat(33), 'with space', 'bad!', 'ñandú'])(
    'rejects the username %j',
    (username) => {
      expect(codes({ username })).toEqual(['username:invalid_format']);
    },
  );

  it.each(['plain', 'a@b', '@b.co', 'a b@c.co', 'a@b@c.co'])('rejects the email %j', (email) => {
    expect(codes({ email })).toEqual(['email:invalid_format']);
  });

  it('rejects an email over 120 characters with the limit as a param', () => {
    const details = checkRegister({ ...valid, email: `${'a'.repeat(120)}@b.co` });
    expect(details).toEqual([
      expect.objectContaining({ field: 'email', code: 'too_long', params: { max: 120 } }),
    ]);
  });

  it('reports the password length bounds with params', () => {
    expect(checkRegister({ ...valid, password: '1234567' })).toEqual([
      expect.objectContaining({ field: 'password', code: 'too_short', params: { min: 8 } }),
    ]);
    expect(checkRegister({ ...valid, password: 'x'.repeat(129) })).toEqual([
      expect.objectContaining({ field: 'password', code: 'too_long', params: { max: 128 } }),
    ]);
  });

  it('keeps the field order: username, email, password', () => {
    expect(codes({ username: 'a', email: 'b', password: 'c' })).toEqual([
      'username:invalid_format',
      'email:invalid_format',
      'password:too_short',
    ]);
  });
});
