import PhoneInput, { isSupportedCountry } from 'react-phone-number-input';
import flags from 'react-phone-number-input/flags';
import labels from 'react-phone-number-input/locale/en.json';
import 'react-phone-number-input/style.css';

// International phone input: the value is always E.164 (e.g. +447911123456).
// Flags are bundled SVGs, so nothing is loaded from a third-party CDN (CSP).
export default function PhoneField({ value, onChange, defaultCountry = '', invalid = false, id }) {
  const country = defaultCountry && isSupportedCountry(defaultCountry) ? defaultCountry : undefined;
  return <PhoneInput
    // A new default country only matters while the field is empty; re-mounting
    // keeps the controlled value either way.
    key={country || 'intl'}
    id={id}
    name="phone_number"
    autoComplete="tel"
    international
    flags={flags}
    labels={labels}
    defaultCountry={country}
    value={value || undefined}
    onChange={next => onChange(next || '')}
    className={`rp-phone${invalid ? ' has-error' : ''}`}
    aria-invalid={invalid || undefined}
  />;
}
