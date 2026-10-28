import { useTranslation } from 'react-i18next';
import { Field } from '@/components/ui/Field';
import { Select } from '@/components/ui/Select';
import { useEnumLabel } from '@/i18n';

/** Condition / language `Select` with an empty choice; keeps a stored value that is not listed. */
export function OptionSelect({
  kind,
  label,
  value,
  options,
  disabled,
  onChange,
}: {
  kind: 'condition' | 'language';
  label: string;
  value: string | null;
  options: string[];
  disabled: boolean;
  onChange: (next: string | null) => void;
}) {
  const { t } = useTranslation('collection');
  const { label: enumLabel } = useEnumLabel();
  const listed = value !== null && !options.includes(value) ? [value, ...options] : options;
  return (
    <Field label={label}>
      {(control) => (
        <Select
          {...control}
          value={value ?? ''}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value === '' ? null : event.target.value)}
        >
          <option value="">{t('line.noValue')}</option>
          {listed.map((option) => (
            <option key={option} value={option}>
              {enumLabel(kind, option)}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );
}
