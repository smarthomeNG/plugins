"""Reading and redacting shng logfiles for the ``get_logs`` tool."""

import logging
import os
import re
from collections import deque
from collections.abc import Sequence
from datetime import datetime

from lib.log import LogEntry, iter_log_entries

from .logformat import LogFormat, handler_log_format
from .paging import decode_cursor, encode_cursor
from .types import GetLogsResult, LogEntryInfo, ToolFailure

MAX_MESSAGE_CHARS = 4000
REDACTED = '***'

_HEADER = re.compile(r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(.*)$', re.DOTALL)

_SECRET_KEY = r'(?:pass(?:word|wd)?|token|secret|api[_-]?key|authorization|credential)'
# (pattern, replacement) pairs applied to every message; the first group, if any, is kept
_BUILTIN_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            rf'(\b[\w.-]*{_SECRET_KEY}[\w.-]*["\']?\s*[:=]\s*["\']?)(?:(?:Bearer|Basic)\s+)?[^\s"\',;&)}}\]]+',
            re.IGNORECASE,
        ),
        rf'\1{REDACTED}',
    ),
    (re.compile(r'\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}', re.IGNORECASE), rf'\1 {REDACTED}'),
    (re.compile(r'(?<=://)[^/\s:@]+:[^/\s@]+(?=@)'), REDACTED),
)


class LogReader:
    """Serves the entries of the logfiles in one directory, newest first, with secrets redacted."""

    def __init__(self, log_dir: str, redact_patterns: Sequence[str] = ()):
        """
        :param log_dir: directory holding the ``*.log`` files
        :param redact_patterns: regular expressions whose matches are replaced in every message, in addition to the
            built-in secret patterns
        :raises ValueError: if a pattern is not a valid regular expression
        """
        self._log_dir = log_dir
        try:
            self._extra_patterns = [re.compile(pattern) for pattern in redact_patterns]
        except re.error as e:
            raise ValueError(f'invalid log_redact pattern: {e}') from e

    def list_files(self) -> list[str]:
        """Return the names of the readable logfiles, ordered by name."""
        try:
            with os.scandir(self._log_dir) as entries:
                return sorted(
                    entry.name
                    for entry in entries
                    if entry.is_file() and entry.name.endswith('.log') and entry.name[0] != '.'
                )
        except OSError:
            return []

    def read(
        self,
        file: str,
        level: str | None = None,
        since: str | None = None,
        contains: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> GetLogsResult:
        """
        Return one page of the entries of a logfile, newest first.

        :param file: name from :meth:`list_files`
        :param level: minimum level name; entries without a recognizable level are dropped
        :param since: ISO timestamp; only entries logged at or after it, entries without a timestamp are dropped
        :param contains: case-insensitive text the redacted message must contain
        :param limit: maximum number of entries
        :param cursor: cursor of the previous page
        :raises ToolFailure: ``not_found`` for an unlisted file; ``bad_request`` for an unknown level, an invalid
            timestamp or an invalid cursor
        """
        if file not in self.list_files():
            raise ToolFailure('not_found', 'log file not found')
        levels = logging.getLevelNamesMapping()
        minimum = self._minimum_level(level, levels)
        earliest = self._parse_since(since)
        before = self._decode_line(cursor)
        needle = contains.lower() if contains is not None else None
        log_format = handler_log_format(self._log_dir, file)
        written_by = datetime.fromtimestamp(os.stat(os.path.join(self._log_dir, file)).st_mtime)

        window: deque[LogEntryInfo] = deque(maxlen=limit + 1)
        for entry in iter_log_entries(os.path.join(self._log_dir, file)):
            if before is not None and entry.end_line >= before:
                break
            info = self._describe(entry, levels, log_format, written_by)
            if minimum is not None and (info['level'] is None or levels[info['level']] < minimum):
                continue
            if earliest is not None and (info['ts'] is None or datetime.fromisoformat(info['ts']) < earliest):
                continue
            if needle is not None and needle not in info['message'].lower():
                continue
            window.append(info)

        page = list(window)[-limit:]
        has_older = len(window) > limit
        return {'entries': page[::-1], 'cursor': encode_cursor(str(page[0]['line'])) if has_older else None}

    def _describe(
        self, entry: LogEntry, levels: dict[str, int], log_format: LogFormat | None, written_by: datetime
    ) -> LogEntryInfo:
        """
        Split an entry into timestamp, level, logger and redacted message; unparsable entries keep only the text.

        :param log_format: format of the handler writing the file; None parses the default ISO format
        :param written_by: latest moment the file can contain, for dates without a year
        """
        first, *rest = entry.lines
        ts = level = logger = None
        message = entry.text
        if log_format is not None:
            parsed = log_format.parse(first, written_by)
            if parsed is not None:
                ts = parsed['ts'].isoformat(timespec='seconds') if parsed['ts'] is not None else None
                level, logger = parsed['level'], parsed['logger']
                message = parsed['message'] + ('\n' + ''.join(rest) if rest else '')
        else:
            header = _HEADER.match(first)
            if header is not None:
                tokens = header.group(3).split(None, 2)
                position = next((i for i in (0, 1) if len(tokens) > i and tokens[i] in levels), None)
                if position is not None:
                    ts = f'{header.group(1)}T{header.group(2)}'
                    level = tokens[position]
                    fields = header.group(3).split(None, position + 2)
                    logger = fields[position + 1] if len(fields) > position + 1 else None
                    head = fields[position + 2] if len(fields) > position + 2 else ''
                    message = head.rstrip('\n') + ('\n' + ''.join(rest) if rest else '')
        return {
            'line': entry.end_line,
            'ts': ts,
            'level': level,
            'logger': logger,
            'message': self._clean(message.rstrip('\n')),
        }

    def _clean(self, message: str) -> str:
        """Redact secrets and cut the message to the length cap."""
        for pattern, replacement in _BUILTIN_REDACTIONS:
            message = pattern.sub(replacement, message)
        for extra in self._extra_patterns:
            message = extra.sub(REDACTED, message)
        if len(message) > MAX_MESSAGE_CHARS:
            message = message[:MAX_MESSAGE_CHARS] + ' ... [truncated]'
        return message

    @staticmethod
    def _minimum_level(level: str | None, levels: dict[str, int]) -> int | None:
        if level is None:
            return None
        if level.upper() not in levels:
            raise ToolFailure('bad_request', f"unknown level '{level}'")
        return levels[level.upper()]

    @staticmethod
    def _parse_since(since: str | None) -> datetime | None:
        """Return the timestamp as naive local time, the form shng logs it in."""
        if since is None:
            return None
        try:
            moment = datetime.fromisoformat(since)
        except ValueError as e:
            raise ToolFailure('bad_request', 'since must be an ISO timestamp') from e
        return moment.astimezone().replace(tzinfo=None) if moment.tzinfo is not None else moment

    @staticmethod
    def _decode_line(cursor: str | None) -> int | None:
        if cursor is None:
            return None
        key = decode_cursor(cursor)
        if not key.isdecimal():
            raise ToolFailure('bad_request', 'invalid cursor')
        return int(key)
