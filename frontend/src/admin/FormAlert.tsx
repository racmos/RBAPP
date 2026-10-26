/** A form-level error. `role="alert"` makes it announce the moment it is rendered. */
export function FormAlert({ message }: { message: string }) {
  return (
    <div role="alert" style={{ color: 'var(--red-text)', fontSize: 14 }}>
      {message}
    </div>
  );
}
