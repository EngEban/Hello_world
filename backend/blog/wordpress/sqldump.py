"""Read rows from a MySQL/MariaDB dump (mysqldump, phpMyAdmin, Adminer, WP-CLI ``wp db export``).

No MySQL server or driver is needed: the dump is scanned statement by
statement, and only ``CREATE TABLE`` column lists and ``INSERT``/``REPLACE``
rows are interpreted. Nothing in the dump is ever executed.
"""
import re

_STATEMENT = re.compile(
    r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(?P<create>\w+)[`"]?\s*\('
    r'|(?:INSERT|REPLACE)(?:\s+(?:IGNORE|LOW_PRIORITY|DELAYED|HIGH_PRIORITY))*\s+INTO\s+[`"]?(?P<insert>\w+)[`"]?\s*',
    re.IGNORECASE,
)
_COLUMN_LINE = re.compile(r'^\s*[`"](?P<name>[^`"]+)[`"]\s+\w', re.MULTILINE)
_COLUMN_LIST = re.compile(r'\(\s*(?P<cols>[`"]?\w+[`"]?(?:\s*,\s*[`"]?\w+[`"]?)*)\s*\)\s*VALUES\s*', re.IGNORECASE)
_VALUES = re.compile(r'VALUES\s*', re.IGNORECASE)
_VALUE = re.compile(
    r"\s*(?:'(?P<str>(?:[^'\\]|\\.|'')*)'"
    r"|_(?:binary|utf8mb4|utf8|latin1)\s*'(?P<bstr>(?:[^'\\]|\\.|'')*)'"
    r"|(?P<null>NULL)"
    r"|(?P<hex>0x[0-9A-Fa-f]*)"
    r"|(?P<num>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?))\s*",
    re.DOTALL | re.IGNORECASE,
)
_ESCAPES = {'0': '\x00', 'b': '\b', 'n': '\n', 'r': '\r', 't': '\t', 'Z': '\x1a', '\\': '\\', "'": "'", '"': '"'}
_ESCAPE = re.compile(r"\\(.)|''", re.DOTALL)


class SQLDumpError(ValueError):
    pass


def _unescape(raw):
    def replace(match):
        char = match.group(1)
        if char is None:
            return "'"
        if char in '%_':
            return '\\' + char  # MySQL keeps the backslash for these two
        return _ESCAPES.get(char, char)
    return _ESCAPE.sub(replace, raw)


def _parse_tuple(text, pos):
    if text[pos] != '(':
        raise SQLDumpError(f'Expected "(" at offset {pos}')
    pos += 1
    values = []
    while True:
        match = _VALUE.match(text, pos)
        if not match:
            raise SQLDumpError(f'Unreadable value at offset {pos}: {text[pos:pos + 40]!r}')
        if match.group('str') is not None:
            values.append(_unescape(match.group('str')))
        elif match.group('bstr') is not None:
            values.append(_unescape(match.group('bstr')))
        elif match.group('null'):
            values.append(None)
        elif match.group('hex'):
            values.append(bytes.fromhex(match.group('hex')[2:]).decode('utf-8', errors='replace'))
        else:
            values.append(match.group('num'))
        pos = match.end()
        if text[pos] == ',':
            pos += 1
            continue
        if text[pos] == ')':
            return values, pos + 1
        raise SQLDumpError(f'Unexpected {text[pos]!r} at offset {pos}')


def read_tables(path, wanted):
    """Return ``{table: [row_dict, ...]}`` for the requested table names."""
    with open(path, encoding='utf-8', errors='replace') as handle:
        text = handle.read()
    wanted = set(wanted)
    columns, rows = {}, {name: [] for name in wanted}
    pos = 0
    while True:
        match = _STATEMENT.search(text, pos)
        if not match:
            break
        if match.group('create'):
            table = match.group('create')
            end = text.find(';', match.end())
            # CREATE TABLE bodies end with ") ENGINE=...;" — find the real end.
            close = re.compile(r'^\)[^\n]*;\s*$', re.MULTILINE).search(text, match.end())
            end = close.end() if close else (end if end != -1 else len(text))
            body = text[match.end():end]
            columns[table] = [
                column.group('name') for column in _COLUMN_LINE.finditer(body)
            ]
            pos = end
            continue
        table = match.group('insert')
        pos = match.end()
        column_list = _COLUMN_LIST.match(text, pos)
        if column_list:
            table_columns = [name.strip(' `"') for name in column_list.group('cols').split(',')]
            pos = column_list.end()
        else:
            values_kw = _VALUES.match(text, pos)
            if not values_kw:
                raise SQLDumpError(f'Unsupported INSERT for {table} at offset {pos}')
            pos = values_kw.end()
            table_columns = columns.get(table)
        while True:
            values, pos = _parse_tuple(text, pos)
            if table in wanted:
                if not table_columns or len(table_columns) != len(values):
                    raise SQLDumpError(f'Column list for {table} is missing or does not match its rows.')
                rows[table].append(dict(zip(table_columns, values)))
            while pos < len(text) and text[pos] in ' \t\r\n':
                pos += 1
            if pos < len(text) and text[pos] == ',':
                pos += 1
                while text[pos] in ' \t\r\n':
                    pos += 1
                continue
            break
        # Skip "ON DUPLICATE KEY UPDATE ..." or trailing ";".
        semicolon = text.find(';', pos)
        pos = semicolon + 1 if semicolon != -1 else len(text)
    return rows, columns


def detect_prefix(path):
    """Find the WordPress table prefix (``wp_`` by default) from CREATE TABLE names."""
    with open(path, encoding='utf-8', errors='replace') as handle:
        head = handle.read()
    names = set(re.findall(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"]?(\w+?)posts[`"]?\s*\(', head, re.IGNORECASE))
    for prefix in sorted(names, key=len):
        if re.search(rf'[`"]?{re.escape(prefix)}postmeta[`"]?', head):
            return prefix
    return 'wp_'
