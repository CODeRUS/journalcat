#!/usr/bin/env python3

'''
Copyright 2016, Andrey Kozhevnikov coderusinbox@gmail.com
'''

# journalcat
# Script to highlight journalctl output for console
# With respect to Android AOSP project pidcat script


import argparse
import sys
import os
import re
import json
import subprocess
from subprocess import PIPE

from datetime import datetime
from datetime import timedelta

__version__ = '1.0.0'


class FakeStdinProcess():
    def __init__(self):
        self.stdout = sys.stdin

    def poll(self):
        return None


def get_term_size():
    def ioctl_GWINSZ(fd):
        try:
            import fcntl
            import termios
            import struct
            cr = struct.unpack('hh',
                               fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
            return cr
        except:
            pass
    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = ioctl_GWINSZ(fd)
            os.close(fd)
        except:
            pass
    if not cr:
        try:
            cr = (os.environ['LINES'], os.environ['COLUMNS'])
        except:
            return None
    return int(cr[1]), int(cr[0])


def indent_wrap(message, width, header_size, extra_content=''):
    if width == -1:
        return message
    message = message.replace('\t', '    ')
    wrap_area = width - header_size - len(extra_content) - 1
    messagebuf = ''
    current = 0
    while current < len(message):
        next = min(current + wrap_area, len(message))
        messagebuf += message[current:next]
        if current == 0:
            messagebuf += ' ' * (wrap_area - next + 1)
            messagebuf += extra_content
        if next < len(message):
            messagebuf += '\n'
            messagebuf += ' ' * header_size
        current = next
    return messagebuf


BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
RESET = '\033[0m'


def termcolor(fg=None, bg=None):
    codes = []
    if fg is not None:
        codes.append('3%d' % fg)
    if bg is not None:
        codes.append('10%d' % bg)
    return '\033[%sm' % ';'.join(codes) if codes else ''


def colorize(message, fg=None, bg=None):
    return termcolor(fg, bg) + message + RESET


def highlight_word(string, word):
    return string.replace(word, '\033[4m\033[1;36m{}\033[0m'.format(word))


QT_DEBUG_LINE = re.compile(r'^\[([A-Z])\] (.+?)\:(\d+) - (.*?)$')
QT_LOG_LEVELS = {
    'D': 7,
    'I': 6,
    'W': 4,
    'C': 2,
    'F': 1
}

PRIORITY_COLORS = [
    colorize('! ', fg=BLACK, bg=RED),        # "emerg"
    colorize('A ', fg=BLACK, bg=RED),        # "alert"
    colorize('C ', fg=BLACK, bg=RED),        # "crit"
    colorize('E ', fg=BLACK, bg=RED),        # "err"
    colorize('W ', fg=BLACK, bg=YELLOW),     # "warning"
    colorize('N ', fg=BLACK, bg=GREEN),      # "notice"
    colorize('I ', fg=BLACK, bg=GREEN),      # "info"
    colorize('D ', fg=BLACK, bg=BLUE),       # "debug"
]

parser = argparse.ArgumentParser(description='Print journalctl in a beauty way.\nFor specific options check \'journalctl --help\'')
parser.add_argument('-o', '--output', dest='output', type=str, help='Changing journal output mode is not available. It\'s always \'json\' for journalcat')

parser.add_argument('-hl', '--highlight', dest='highlight', action='append', help='Highlight word')
parser.add_argument('-g', '--grep', dest='grep', action='append', help='Filter lines only contains word')

parser.add_argument('-ts', '--timestamp', dest='timestamp', action='store_true', default=False, help='Print timestamp information')
parser.add_argument('-tf', '--timestamp-format', dest='timestamp_format', type=str, default='%H:%M:%S.%f', help='Print timestamp information (default: %(default)s)')

parser.add_argument('--code', dest='code', action='store_true', default=False, help='Print code line information')

parser.add_argument('--no-qt', dest='noqt', action='store_true', default=False, help='Do not strip Qt Debug data')
parser.add_argument('--no-pid', dest='nopid', action='store_true', default=False, help='Do not print PID data')
parser.add_argument('--no-id', dest='noid', action='store_true', default=False, help='Do not print syslog identifier data')
parser.add_argument('--pid', dest='pid', action='append', help='Print only messages for certain PID')
parser.add_argument('--id', dest='identifier', action='append', help='Print only messages for certain syslog identifier')

parser.add_argument('--file', dest='file', action='store', help='Save displayed information in plain text to file')

args, external = parser.parse_known_args()

if args.output:
    print('Changing journal output mode is not available. It\'s always \'json\' for journalcat')
    exit(1)

if sys.stdin.isatty():
    command = ['journalctl', '-o', 'json'] + external
    if args.pid:
        for pid in args.pid:
            command += ['_PID=%s' % pid]
    if args.identifier:
        for identifier in args.identifier:
            command += ['SYSLOG_IDENTIFIER=%s' % identifier]

    journal = subprocess.Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE)
else:
    journal = FakeStdinProcess()

f = None
if args.file:
    dirname = os.path.dirname(os.path.abspath(__file__))
    f = open(os.path.join(dirname, args.file), 'w')

epoch = datetime(1970, 1, 1)

while journal.poll() is None:
    try:
        buf = journal.stdout.readline()
        if sys.stdin.isatty():
            line = buf.decode('utf-8', 'replace').strip()
        else:
            line = buf.strip()
    except KeyboardInterrupt:
        break
    if len(line) == 0:
        break

    width, h = get_term_size()

    data = json.loads(line)

    if 'MESSAGE' in data:
        message = data['MESSAGE']
        if type(message) is not str:
            continue
        else:
            message = message.strip().replace('\n', '')
    else:
        continue

    priority = int(data['PRIORITY']) if 'PRIORITY' in data else 7
    if not args.noqt and 'CODE_FUNC' in data:
        code_func = data['CODE_FUNC']
        code_line = data['CODE_LINE']
        qt_debug_line = QT_DEBUG_LINE.match(message)
        if qt_debug_line is not None:
            qt_priority, code_func, code_line, message = qt_debug_line.groups()
            priority = QT_LOG_LEVELS[qt_priority]

    if args.grep and (len(args.grep) > 0):
        filter_in = False
        for grep_word in args.grep:
            if message.find(grep_word) >= 0:
                filter_in = True
        if not filter_in:
            continue

    header = PRIORITY_COLORS[priority]
    header_size = 3
    extra_size = 0

    if args.highlight and len(args.highlight) > 0:
        extra_size += 1
        hl_found = False
        for hl_word in args.highlight:
            if message.find(hl_word) >= 0:
                hl_found = True
                message = highlight_word(message, hl_word)
        if hl_found:
            header += colorize(' ', bg=GREEN)
        else:
            header += ' '

    if args.timestamp:
        timestamp = epoch + timedelta(microseconds=int(data['__REALTIME_TIMESTAMP']))
        timestamp = timestamp.strftime(args.timestamp_format)
        header += ' ' + timestamp
        extra_size += len(timestamp) + 1

    header += ' '
    linebuf = ''

    extra_content = ''

    if not args.nopid or not args.noid:
        extra_content += '('
        if not args.noid and 'SYSLOG_IDENTIFIER' in data:
            extra_content += data['SYSLOG_IDENTIFIER']
            if not args.nopid and '_PID' in data:
                extra_content += ':' + data['_PID']
        elif not args.nopid and '_PID' in data:
            extra_content += data['_PID']
        extra_content += ')'

    if args.code and 'CODE_FUNC' in data:
        linebuf += code_func + ':' + code_line

        if 'CODE_FILE' in data:
            code_file = data['CODE_FILE']
            linebuf += '(%s)' % code_file

        linebuf += ' '

    linebuf += message
    linebuf = header + indent_wrap(linebuf, width, header_size + extra_size, extra_content)

    try:
        print(linebuf)
    except:
        pass

    if f:
        timestamp = epoch + timedelta(microseconds=int(data['__REALTIME_TIMESTAMP']))
        timestamp = timestamp.strftime(args.timestamp_format)
        filebuf = timestamp
        if 'SYSLOG_IDENTIFIER' in data:
            filebuf += ' ' + data['SYSLOG_IDENTIFIER']
            if '_PID' in data:
                filebuf += ':' + data['_PID'] + ' '
            else:
                filebuf += ' '
        elif '_PID' in data:
            filebuf += ' ' + data['_PID'] + ' '
        filebuf += message
        f.write(filebuf + '\n')
        f.flush()

if f:
    f.close()
