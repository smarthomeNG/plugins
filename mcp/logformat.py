"""Parsing logfile lines with the format string of the logging handler that wrote them."""

import logging
import os
import re
from datetime import datetime, timedelta

from typing_extensions import TypedDict

# strptime directive -> regular expression matching what it parses
_DATE_DIRECTIVES: dict[str, str] = {
    'Y': r'\d{4}',
    'y': r'\d{2}',
    'm': r'\d{2}',
    'd': r'\d{2}',
    'H': r'\d{2}',
    'I': r'\d{2}',
    'M': r'\d{2}',
    'S': r'\d{2}',
    'f': r'\d{1,6}',
    'j': r'\d{3}',
    'p': r'[AaPp][Mm]',
    'a': r'[^\W\d_]+',
    'A': r'[^\W\d_]+',
    'b': r'[^\W\d_]+',
    'B': r'[^\W\d_]+',
    'z': r'[+-]\d{4}',
    '%': '%',
}
_STANDARD_LEVELS = frozenset({'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'})
_DEFAULT_DATEFMT = '%Y-%m-%d %H:%M:%S,%f'
_DAY_DIRECTIVES = frozenset('dj')
_YEAR_DIRECTIVES = frozenset('Yy')
_PLACEHOLDER_YEAR = 2000
_YEAR_SEARCH_DEPTH = 5

_FORMAT_TOKEN = re.compile(
    r'%\((?P<key>\w+)\)(?P<flags>[-+ #0]*)(?P<width>\d*)(?:\.(?P<precision>\d+))?(?P<conversion>[sd])|%%|%'
)
_DIRECTIVE = re.compile(r'%(.)|(\s+)|([^%\s]+)', re.DOTALL)


class ParsedLine(TypedDict):
    """The fields of one logfile line; ``ts`` is None if the format carries no full date."""

    ts: datetime | None
    level: str
    logger: str | None
    message: str


class LogFormat:
    """Parses the first line of a logfile entry written with a given ``logging`` percent-style format."""

    def __init__(self, line: re.Pattern[str], date_format: str | None):
        """
        :param line: pattern with the groups ``levelname`` and optionally ``asctime``, ``name`` and ``message``
        :param date_format: strptime format of the ``asctime`` group, None if the pattern has no such group
        """
        self._line = line
        self._date_format = date_format

    @classmethod
    def from_logging(cls, fmt: str, datefmt: str | None) -> 'LogFormat | None':
        """
        Build the parser for a ``logging.Formatter`` format.

        :param fmt: percent-style format string with at least ``%(levelname)s``
        :param datefmt: the formatter's ``datefmt``; None selects the ``logging`` default
        :return: None if the format has no level, uses another style or a field or date directive that cannot be
            matched
        """
        date_regex = date_format = None
        if '%(asctime)' in fmt:
            date_format = datefmt or _DEFAULT_DATEFMT
            date_regex = _date_regex(date_format)
            if date_regex is None:
                return None
        pattern = _line_regex(fmt, date_regex)
        if pattern is None:
            return None
        return cls(pattern, date_format)

    def parse(self, line: str, reference: datetime) -> ParsedLine | None:
        """
        Split a line into timestamp, level, logger and message.

        :param line: the first physical line of an entry
        :param reference: when the line was written at the latest; supplies the year if the date format has none
        :return: None if the line is not in this format or names an unknown level
        """
        text = line.rstrip('\r\n')
        match = self._line.match(text)
        if match is None:
            return None
        groups = match.groupdict()
        level = _level_name(groups['levelname'])
        if level is None:
            return None
        ts = self._timestamp(groups['asctime'], reference) if groups.get('asctime') is not None else None
        return {
            'ts': ts,
            'level': level,
            'logger': groups.get('name'),
            'message': groups['message'] if groups.get('message') is not None else text,
        }

    def _timestamp(self, text: str, reference: datetime) -> datetime | None:
        """Return the moment ``text`` names, or None if it cannot be placed on a calendar date."""
        assert self._date_format is not None
        directives = {match.group(1) for match in _DIRECTIVE.finditer(self._date_format) if match.group(1)}
        if not directives & _DAY_DIRECTIVES and not {'m', 'b', 'B'} & directives:
            return None
        has_year = bool(directives & _YEAR_DIRECTIVES)
        try:
            if has_year:
                return datetime.strptime(text, self._date_format)
            moment = datetime.strptime(f'{text} {_PLACEHOLDER_YEAR}', f'{self._date_format} %Y')
        except ValueError:
            return None
        return _latest_year_not_after(moment, reference)


def _date_regex(date_format: str) -> str | None:
    """Return a regular expression for what ``date_format`` produces, None if it uses an unsupported directive."""
    parts: list[str] = []
    for match in _DIRECTIVE.finditer(date_format):
        directive, space, literal = match.groups()
        if directive is not None:
            if directive not in _DATE_DIRECTIVES:
                return None
            parts.append(_DATE_DIRECTIVES[directive])
        elif space is not None:
            parts.append(r'\s+')
        else:
            parts.append(re.escape(literal))
    return ''.join(parts)


def _line_regex(fmt: str, date_regex: str | None) -> re.Pattern[str] | None:
    """
    Compile a percent-style ``logging`` format into a line pattern, None if it cannot be matched.

    Trailing whitespace of the format is optional in the line.
    """
    parts: list[str] = ['^']
    seen: set[str] = set()
    position = 0
    for match in _FORMAT_TOKEN.finditer(fmt):
        parts.append(_literal_regex(fmt[position : match.start()]))
        position = match.end()
        key = match.group('key')
        if key is None:
            if match.group(0) != '%%':
                return None
            parts.append('%')
            continue
        padded = bool(match.group('width'))
        field = _field_regex(key, match.group('conversion'), date_regex, key in seen)
        if field is None:
            return None
        seen.add(key)
        parts.append(rf'\s*{field}\s*' if padded else field)
    parts.append(_literal_regex(fmt[position:].rstrip()))
    parts.append(r'\s*$')
    if 'levelname' not in seen:
        return None
    return re.compile(''.join(parts))


def _field_regex(key: str, conversion: str, date_regex: str | None, repeated: bool) -> str | None:
    """Return the pattern for one ``%(key)`` field; named groups only for the fields the parser reports."""
    if key in ('asctime', 'levelname', 'name', 'message') and repeated:
        return None
    if key == 'asctime':
        return rf'(?P<asctime>{date_regex})'
    if key in ('levelname', 'name'):
        return rf'(?P<{key}>\S+)'
    if key == 'message':
        return r'(?P<message>.*?)'
    return r'-?\d+' if conversion == 'd' else r'.*?'


def _literal_regex(text: str) -> str:
    """Escape literal format text, letting every whitespace run match any whitespace."""
    return ''.join(r'\s+' if chunk.isspace() else re.escape(chunk) for chunk in re.split(r'(\s+)', text) if chunk)


def _level_name(token: str) -> str | None:
    """
    Return the level named by ``token``, which may be a name or its leading letters.

    Leading letters shared by several levels resolve to the standard ``logging`` level among them, so ``D`` is
    ``DEBUG`` although shng also defines ``DBGHIGH``. Returns None if the token matches no level or no single one.
    """
    levels = logging.getLevelNamesMapping()
    if token in levels:
        return logging.getLevelName(levels[token])
    candidates = {name: value for name, value in levels.items() if value and name.startswith(token.upper())}
    standard = candidates.keys() & _STANDARD_LEVELS
    if len(standard) == 1:
        return next(iter(standard))
    values = set(candidates.values())
    return logging.getLevelName(values.pop()) if len(values) == 1 else None


def _latest_year_not_after(moment: datetime, reference: datetime) -> datetime | None:
    """Place a year-less moment in the latest year that does not put it after ``reference`` (plus a day of slack)."""
    for year in range(reference.year, reference.year - _YEAR_SEARCH_DEPTH, -1):
        try:
            candidate = moment.replace(year=year)
        except ValueError:
            continue
        if candidate <= reference + timedelta(days=1):
            return candidate
    return None


def handler_log_format(log_dir: str, file: str) -> LogFormat | None:
    """
    Return the parser for the format a ``logging`` file handler writes ``file`` with.

    A rotated file such as ``name.2026-10-27.log`` belongs to the handler of ``name.log``.

    :param log_dir: directory holding the logfiles
    :param file: file name inside ``log_dir``
    :return: None if no handler writes the file or its format cannot be parsed
    """
    directory = os.path.realpath(log_dir)
    stem, extension = os.path.splitext(file)
    for handler in _file_handlers():
        base_dir, base_name = os.path.split(handler.baseFilename)
        if os.path.realpath(base_dir) != directory:
            continue
        base_stem, base_extension = os.path.splitext(base_name)
        if base_extension != extension or not (stem == base_stem or stem.startswith(f'{base_stem}.')):
            continue
        formatter = handler.formatter
        if formatter is None or not isinstance(formatter._style, logging.PercentStyle):
            continue
        log_format = LogFormat.from_logging(formatter._fmt or '', formatter.datefmt)
        if log_format is not None:
            return log_format
    return None


def _file_handlers() -> list[logging.FileHandler]:
    """Return every file handler attached to the root logger or a named logger."""
    loggers = [
        logging.root,
        *(logger for logger in logging.Logger.manager.loggerDict.values() if isinstance(logger, logging.Logger)),
    ]
    handlers = {
        id(handler): handler
        for logger in loggers
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
    }
    return list(handlers.values())
