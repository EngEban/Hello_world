import { COUNTRY_OPTIONS } from './countries';

export default function CountrySelect({ value, onChange, name = 'country', required = false, invalid = false, id, className = '' }) {
  return <select
    id={id}
    name={name}
    value={value || ''}
    onChange={onChange}
    required={required}
    autoComplete="country"
    aria-invalid={invalid || undefined}
    className={className}
  >
    <option value="">{required ? 'Select your country' : 'Not specified'}</option>
    {COUNTRY_OPTIONS.map(option => <option key={option.code} value={option.code}>{option.name}</option>)}
  </select>;
}
