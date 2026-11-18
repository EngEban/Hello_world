"""Minimal, safe reader for PHP ``serialize()`` output found in WordPress tables.

Only scalars and arrays are supported. Objects (``O:``/``C:``) are never
instantiated: they make the parser return ``None`` for that value, which is
what WordPress data such as ``wp_capabilities`` or Rank Math sources needs.
"""


class PHPSerialError(ValueError):
    pass


def loads(value):
    if not isinstance(value, str) or not value:
        return None
    data = value.encode('utf-8')
    try:
        result, _ = _parse(data, 0)
    except (PHPSerialError, IndexError, ValueError):
        return None
    return result


def _read_until(data, pos, char):
    end = data.index(char, pos)
    return data[pos:end].decode('utf-8'), end + 1


def _parse(data, pos):
    kind = chr(data[pos])
    if kind == 'N':
        return None, pos + 2
    if data[pos + 1:pos + 2] != b':':
        raise PHPSerialError('bad token')
    pos += 2
    if kind == 'b':
        raw, pos = _read_until(data, pos, b';')
        return raw == '1', pos
    if kind == 'i':
        raw, pos = _read_until(data, pos, b';')
        return int(raw), pos
    if kind == 'd':
        raw, pos = _read_until(data, pos, b';')
        return float(raw), pos
    if kind == 's':
        raw, pos = _read_until(data, pos, b':')
        length = int(raw)
        if data[pos:pos + 1] != b'"':
            raise PHPSerialError('bad string')
        text = data[pos + 1:pos + 1 + length].decode('utf-8', errors='replace')
        return text, pos + 1 + length + 2
    if kind == 'a':
        raw, pos = _read_until(data, pos, b':')
        count = int(raw)
        if data[pos:pos + 1] != b'{':
            raise PHPSerialError('bad array')
        pos += 1
        result = {}
        for _ in range(count):
            key, pos = _parse(data, pos)
            item, pos = _parse(data, pos)
            result[key] = item
        return result, pos + 1
    raise PHPSerialError(f'unsupported type {kind}')
