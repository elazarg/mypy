"""Utilities for processing .test files containing test case descriptions."""

import os
import os.path
import posixpath
import re
import shutil

import tempfile

from itertools import groupby
from abc import abstractmethod
from os import remove, rmdir

import pytest  # type: ignore  # no pytest in typeshed
from typing import List, Tuple, Set, Optional, Dict, Iterator, Any, NamedTuple

from mypy.unit import config
from mypy.unit.helpers import typename


def expand_includes(a: List[str], base_path: str) -> List[str]:
    """Expand @includes within a list of lines.

    Replace all lies starting with @include with the contents of the
    file name following the prefix. Look for the files in base_path.
    """

    res = []  # type: List[str]
    for s in a:
        if s.startswith('@include '):
            fn = s.split(' ', 1)[1].strip()
            with open(os.path.join(base_path, fn)) as f:
                res.extend(f.readlines())
        else:
            res.append(s)
    return res


def expand_errors(input: List[str], output: List[str], fnam: str) -> None:
    """Transform comments such as '# E: message' or
    '# E:3: message' in input.

    The result is lines like 'fnam:line: error: message'.
    """

    for i in range(len(input)):
        # The first in the split things isn't a comment
        for possible_err_comment in input[i].split('#')[1:]:
            m = re.search(
                '^([ENW]):((?P<col>\d+):)? (?P<message>.*)$',
                possible_err_comment.strip())
            if m:
                if m.group(1) == 'E':
                    severity = 'error'
                elif m.group(1) == 'N':
                    severity = 'note'
                elif m.group(1) == 'W':
                    severity = 'warning'
                col = m.group('col')
                if col is None:
                    output.append(
                        '{}:{}: {}: {}'.format(fnam, i + 1, severity, m.group('message')))
                else:
                    output.append('{}:{}:{}: {}: {}'.format(
                        fnam, i + 1, col, severity, m.group('message')))


def fix_win_path(line: str) -> str:
    r"""Changes paths to Windows paths in error messages.

    E.g. foo/bar.py -> foo\bar.py.
    """
    m = re.match(r'^([\S/]+):(\d+:)?(\s+.*)', line)
    if not m:
        return line
    else:
        filename, lineno, message = m.groups()
        return '{}:{}{}'.format(filename.replace('/', '\\'),
                                lineno or '', message)


def fix_cobertura_filename(line: str) -> str:
    r"""Changes filename paths to Linux paths in Cobertura output files.

    E.g. filename="pkg\subpkg\a.py" -> filename="pkg/subpkg/a.py".
    """
    m = re.search(r'<class .* filename="(?P<filename>.*?)"', line)
    if not m:
        return line
    return '{}{}{}'.format(line[:m.start(1)],
                           m.group('filename').replace('\\', '/'),
                           line[m.end(1):])


"""Parsed test caseitem.

An item is of the form
  [id arg]
  .. data ..
"""
TestItem = NamedTuple('TestItem', [
    ('id', str),
    ('arg', Optional[str]),
    ('data', List[str]),
    ('line', int),
    ('lastline', int),
])


def strip_list(l: List[str]) -> List[str]:
    """Return a stripped copy of l.

    Strip whitespace at the end of all lines, and strip all empty
    lines from the end of the array.
    """

    r = []  # type: List[str]
    for s in l:
        # Strip spaces at end of line
        r.append(re.sub(r'\s+$', '', s))

    while len(r) > 0 and r[-1] == '':
        r.pop()

    return r


def collapse_line_continuation(l: List[str]) -> List[str]:
    r = []  # type: List[str]
    cont = False
    for s in l:
        ss = re.sub(r'\\$', '', s)
        if cont:
            r[-1] += re.sub('^ +', '', ss)
        else:
            r.append(ss)
        cont = s.endswith('\\')
    return r


def parse_test_data(l: List[str]) -> Iterator[TestItem]:
    """Parse a list of lines that represent a sequence of test items."""

    data = []  # type: List[str]

    id = None  # type: Optional[str]
    arg = None  # type: Optional[str]

    i = 0
    i0 = 0
    while i < len(l):
        s = l[i].strip()

        if l[i].startswith('[') and s.endswith(']') and not s.startswith('[['):
            if id:
                data = collapse_line_continuation(data)
                data = strip_list(data)
                yield TestItem(id, arg, strip_list(data), i0 + 1, i)
            i0 = i
            id = s[1:-1]
            arg = None
            if ' ' in id:
                arg = id[id.index(' ') + 1:]
                id = id[:id.index(' ')]
            data = []
        elif l[i].startswith('[['):
            data.append(l[i][1:])
        elif not l[i].startswith('--'):
            data.append(l[i])
        elif l[i].startswith('----'):
            data.append(l[i][2:])
        i += 1

    # Process the last item.
    if id:
        data = collapse_line_continuation(data)
        data = strip_list(data)
        yield TestItem(id, arg, data, i0 + 1, i)

##
#
# pytest setup
#
##


# This function name is special to pytest.  See
# http://doc.pytest.org/en/latest/writing_plugins.html#initialization-command-line-and-configuration-hooks
def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup('mypy')
    group.addoption('--update-data', action='store_true', default=False,
                    help='Update test data to reflect actual output'
                         ' (supported only for certain tests)')


# This function name is special to pytest.  See
# http://doc.pytest.org/en/latest/writing_plugins.html#collection-hooks
def pytest_pycollect_makeitem(collector: Any, name: str, obj: Any) -> Any:
    if isinstance(obj, type):
        if issubclass(obj, MypyDataItem):
            return MypyDataSuite(name, parent=collector)


class Cases:
    i = -1

    def __call__(self, x: TestItem) -> int:
        if x.id == 'case':
            self.i += 1
        return self.i


class MypyDataSuite(pytest.Class):  # type: ignore  # inheriting from Any
    def collect(self) -> Iterator['MypyDataItem']:
        for filename in self.obj.files:
            path = os.path.join(config.test_data_prefix, filename)
            with open(path, encoding='utf-8') as f:
                lines = f.read().split('\n')
            for i, items in groupby(parse_test_data(lines), key=Cases()):
                yield self.obj(self, path, list(items))


class MypyDataItem(pytest.Item):
    files = []

    base_path = config.test_temp_dir
    optional_out = False
    include_path = None
    native_sep = False

    @abstractmethod
    def run_case(self) -> None:
        raise NotImplementedError

    # Private
    input = None  # type: List[str]
    output = None  # type: List[str]
    output_files = None  # type: List[str]

    file = ''
    line = 0
    lastline = 0

    # (file path, file content) tuples
    sub_files = None  # type: List[Tuple[str, str]]
    expected_stale_modules = None  # type: Optional[Set[str]]
    expected_rechecked_modules = None  # type: Optional[Set[str]]

    clean_up = None  # type: List[Tuple[bool, str]]

    def __init__(self, parent: MypyDataSuite, file: str, items: List[TestItem]) -> None:
        self.name = items[0].arg
        self.skip = False
        if self.name.endswith('-skip'):
            self.skip = True
            self.name = self.name[:-len('-skip')]

        super().__init__(self.name, parent)

        if not self.include_path:
            self.include_path = os.path.dirname(file)

        self.prefix = typename(type(self)) + '.'
        self.old_cwd = None  # type: str
        self.tmpdir = None  # type: tempfile.TemporaryDirectory

        self.update_data = self.config.getoption('--update-data', False)

        self.file = file
        self.items = items

    def prepare_test_case(self) -> None:
        """Process the parsed items.

        Each item has a header of form [id args], optionally followed by lines of text."""
        ok = True  # TODO: FIX
        if self.native_sep:
            join = os.path.join
        else:
            join = posixpath.join  # type: ignore
        main = self.items[0]
        self.sub_files = []  # type: List[Tuple[str, str]] # path and contents for output files
        self.output = []  # type: List[str]  # Regular output errors
        self.output2 = []  # type: List[str]  # Output errors for incremental, second run
        self.output_files = []  # type: List[str]
        self.expected_stale_modules = None  # type: Optional[Set[str]]  # module names
        self.expected_rechecked_modules = None  # type: Optional[Set[str]]  # module names
        self.lastline = 0
        for id, arg, data, line, lastline in self.items[1:]:
            if id == 'file' or id == 'outfile':
                # Record an extra file needed for the test case.
                assert arg is not None
                file_entry = (join(self.base_path, arg), '\n'.join(data))
                if id == 'file':
                    self.sub_files.append(file_entry)
                elif id == 'outfile':
                    self.output_files.append(file_entry)
            elif id in ('builtins', 'builtins_py2'):
                # Use a custom source file for the std module.
                assert arg is not None
                mpath = join(os.path.dirname(self.file), arg)
                if id == 'builtins':
                    fnam = 'builtins.pyi'
                else:
                    # Python 2
                    fnam = '__builtin__.pyi'
                with open(mpath) as f:
                    self.sub_files.append((join(self.base_path, fnam), f.read()))
            elif id == 'stale':
                if arg is None:
                    self.expected_stale_modules = set()
                else:
                    self.expected_stale_modules = {item.strip() for item in arg.split(',')}
            elif id == 'rechecked':
                if arg is None:
                    self.expected_rechecked_modules = set()
                else:
                    self.expected_rechecked_modules = {item.strip() for item in arg.split(',')}
            elif id == 'out' or id == 'out1':
                self.output = data
                if self.native_sep and os.path.sep == '\\':
                    self.output = [fix_win_path(line) for line in self.output]
                ok = True
            elif id == 'out2':
                self.output2 = data
                if self.native_sep and os.path.sep == '\\':
                    self.output2 = [fix_win_path(line) for line in self.output2]
                ok = True
            else:
                raise ValueError(
                    'Invalid section header {} in {} at line {}'.format(
                        id, self.file, line))

        if self.expected_rechecked_modules is None:
            # If the set of rechecked modules isn't specified, make it the same as the set of
            # modules with a stale public interface.
            self.expected_rechecked_modules = self.expected_stale_modules
        if (self.expected_stale_modules is not None
                and self.expected_rechecked_modules is not None
                and not self.expected_stale_modules.issubset(self.expected_rechecked_modules)):
            raise ValueError(
                'Stale modules must be a subset of rechecked modules ({})'.format(self.file))

        if self.optional_out:
            ok = True

        if ok:
            self.input = expand_includes(main.data, self.include_path)
            expand_errors(self.input, self.output, 'main')
            for file_path, contents in self.sub_files:
                expand_errors(contents.split('\n'), self.output, file_path)
        else:
            raise ValueError(
                '{}, line {}: Error in test case description'.format(
                    self.file, main.line))

    def setup(self) -> None:
        self.old_cwd = os.getcwd()
        self.tmpdir = tempfile.TemporaryDirectory(
            prefix='mypy-test-',
            dir=os.path.abspath('tmp-test-dirs')
        )
        os.chdir(self.tmpdir.name)
        os.mkdir('tmp')

        self.prepare_test_case()
        encountered_files = set()
        self.clean_up = []
        for path, content in self.sub_files:
            dir = os.path.dirname(path)
            for d in self.add_dirs(dir):
                self.clean_up.append((True, d))
            with open(path, 'w') as f:
                f.write(content)
            self.clean_up.append((False, path))
            encountered_files.add(path)
            if path.endswith(".next"):
                # Make sure new files introduced in the second run are accounted for
                renamed_path = path[:-5]
                if renamed_path not in encountered_files:
                    encountered_files.add(renamed_path)
                    self.clean_up.append((False, renamed_path))
        for path, _ in self.output_files:
            # Create directories for expected output and mark them to be cleaned up at the end
            # of the test case.
            dir = os.path.dirname(path)
            for d in self.add_dirs(dir):
                self.clean_up.append((True, d))
            self.clean_up.append((False, path))

    def add_dirs(self, dir: str) -> List[str]:
        """Add all subdirectories required to create dir.

        Return an array of the created directories in the order of creation.
        """
        if dir == '' or os.path.isdir(dir):
            return []
        else:
            dirs = self.add_dirs(os.path.dirname(dir)) + [dir]
            os.mkdir(dir)
            return dirs

    def runtest(self) -> None:
        if self.skip:
            pytest.skip()
        self.run_case()

    def teardown(self) -> None:
        # First remove files.
        for is_dir, path in reversed(self.clean_up):
            if not is_dir:
                remove(path)
        # Then remove directories.
        for is_dir, path in reversed(self.clean_up):
            if is_dir:
                pycache = os.path.join(path, '__pycache__')
                if os.path.isdir(pycache):
                    shutil.rmtree(pycache)
                try:
                    rmdir(path)
                except OSError as error:
                    print(' ** Error removing directory %s -- contents:' % path)
                    for item in os.listdir(path):
                        print('  ', item)
                    # Most likely, there are some files in the
                    # directory. Use rmtree to nuke the directory, but
                    # fail the test case anyway, since this seems like
                    # a bug in a test case -- we shouldn't leave
                    # garbage lying around. By nuking the directory,
                    # the next test run hopefully passes.
                    path = error.filename
                    # Be defensive -- only call rmtree if we're sure we aren't removing anything
                    # valuable.
                    if path.startswith('tmp/') and os.path.isdir(path):
                        shutil.rmtree(path)
                    raise

        os.chdir(self.old_cwd)
        self.tmpdir.cleanup()
        self.old_cwd = None
        self.tmpdir = None

    def update_testcase_output(self, output: List[str]) -> None:
        testcase_path = os.path.join(self.old_cwd, self.file)
        with open(testcase_path) as f:
            data_lines = f.read().splitlines()
        test = '\n'.join(data_lines[self.line:self.lastline])

        mapping = {}  # type: Dict[str, List[str]]
        for old, new in zip(self.output, output):
            PREFIX = 'error:'
            ind = old.find(PREFIX)
            if ind != -1 and old[:ind] == new[:ind]:
                old, new = old[ind + len(PREFIX):], new[ind + len(PREFIX):]
            mapping.setdefault(old, []).append(new)

        for old in mapping:
            if test.count(old) == len(mapping[old]):
                betweens = test.split(old)

                # Interleave betweens and mapping[old]
                from itertools import chain
                interleaved = [betweens[0]] + \
                    list(chain.from_iterable(zip(mapping[old], betweens[1:])))
                test = ''.join(interleaved)

        data_lines[self.line:self.lastline] = [test]
        data = '\n'.join(data_lines)
        with open(testcase_path, 'w') as f:
            print(data, file=f)

    def reportinfo(self) -> Tuple[str, int, str]:
        return self.file, self.line, self.name

    def repr_failure(self, excinfo: Any) -> str:
        if excinfo.errisinstance(SystemExit):
            # We assume that before doing exit() (which raises SystemExit) we've printed
            # enough context about what happened so that a stack trace is not useful.
            # In particular, uncaught exceptions during semantic analysis or type checking
            # call exit() and they already print out a stack trace.
            excrepr = excinfo.exconly()
        else:
            self.parent._prunetraceback(excinfo)
            excrepr = excinfo.getrepr(style='short')

        return "data: {}:{}:\n{}".format(self.file, self.line, excrepr)
