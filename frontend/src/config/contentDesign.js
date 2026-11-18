const ALLOWED_FONTS = new Set([
  'Arial, sans-serif',
  'Georgia, serif',
  'Comfortaa, Arial, sans-serif',
  'Tahoma, sans-serif',
  '"Times New Roman", serif',
]);
const HEX_COLOR = /^#[0-9a-f]{3}(?:[0-9a-f]{3})?$/i;

function allowedColor(value, fallback) {
  return typeof value === 'string' && HEX_COLOR.test(value) ? value : fallback;
}

function allowedNumber(value, fallback, min, max) {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric >= min && numeric <= max ? numeric : fallback;
}

function contrast(a, b) {
  const luminance = hex => {
    const expanded = hex.length === 4 ? hex.slice(1).split('').map(char => char + char).join('') : hex.slice(1);
    const channels = [0, 2, 4].map(index => parseInt(expanded.slice(index, index + 2), 16) / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
  };
  const values = [luminance(a), luminance(b)].sort((a, b) => b - a);
  return (values[0] + .05) / (values[1] + .05);
}

export function contentDesignStyle(item) {
  const design = item.design_settings || {};
  const background = allowedColor(design.background_color, '#ffffff');
  const requestedText = allowedColor(design.text_color, '#243752');
  const text = contrast(requestedText, background) >= 4.5 ? requestedText : contrast('#243752', background) >= 4.5 ? '#243752' : '#ffffff';
  return {
    '--content-accent': allowedColor(design.accent_color, '#126ac6'),
    backgroundColor: background,
    color: text,
    fontFamily: ALLOWED_FONTS.has(design.font_family) ? design.font_family : 'Arial, sans-serif',
    fontSize: `${allowedNumber(design.font_size, 17, 12, 30)}px`,
    lineHeight: allowedNumber(design.line_height, 1.75, 1, 3),
    maxWidth: `${allowedNumber(design.content_width, 920, 560, 1400)}px`,
  };
}

// Legacy per-post fonts remain stored, but published reading surfaces share
// one editorial type system. Colors and other supported design options remain.
export function publicationReadingStyle(item) {
  return {
    ...contentDesignStyle(item),
    fontFamily: '"RB", Arial, sans-serif',
    fontSize: '18px',
    lineHeight: 1.85,
  };
}
