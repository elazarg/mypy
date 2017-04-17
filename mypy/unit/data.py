"""Utilities for processing .test files containing test case descriptions."""

import os
import os.path
import posixpath
import re
import shutil

from itertools import groupby
from abc import abstractmethod
from os import remove, rmdir

import pytest  # type: ignore  # no pytest in typeshed
from typing import Callable, List, Tuple, Set, Optional, Dict, Iterator, Any, Iterable

from mypy.unit.helpers import ProtoTestCase, SkipTestCaseException
from mypy.unit.parse_datatest import parse_test_data, TestItem


def parse_test_cases(
        path: str,
        perform: Optional[Callable[['DataDrivenTestCase'], None]],
        base_path: str = '.',
        optional_out: bool = False,
        include_path: str = None,
        native_sep: bool = False) -> List['DataDrivenTestCase']:
    """Parse a file with test case descriptions.

    Return an array of test cases.
    """
    if not include_path:
        include_path = os.path.dirname(path)
    with open(path, encoding='utf-8') as f:
        l = f.read().split('\n')
    c = -1

    def next_case(x: TestItem):
        nonlocal c
        if x.id == 'case':
            c += 1
        return c

    p = groupby(parse_test_data(l), key=next_case)
    out = []  # type: List[DataDrivenTestCase]
    for i, items in p:
        out.append(DataDrivenTestCase(path, list(items),
                                      perform, base_path, optional_out, include_path, native_sep))
    return out


class DataDrivenTestCase(ProtoTestCase):
    input = None  # type: List[str]
    output = None  # type: List[str]
    output_files = None  # type: List[str]

    file = ''
    line = 0
    lastline = 0

    # (file path, file content) tuples
    files = None  # type: List[Tuple[str, str]]
    expected_stale_modules = None  # type: Optional[Set[str]]
    expected_rechecked_modules = None  # type: Optional[Set[str]]

    clean_up = None  # type: List[Tuple[bool, str]]

    def __init__(self,
                 file: str,
                 items: List[TestItem],
                 perform: Callable[['DataDrivenTestCase'], None],
                 base_path: str = '.',
                 optional_out: bool = False,
                 include_path: str = None,
                 native_sep: bool = False,
                 ) -> None:
        super().__init__(items[0].arg)
        self.file = file
        self.items = items
        self.perform = perform

        self.base_path = base_path
        self.optional_out = optional_out
        self.include_path = include_path
        self.native_sep = native_sep

    def prepare_test_case(self) -> None:
        """Process the parsed items.

        Each item has a header of form [id args], optionally followed by lines of text."""
        ok = True  # TODO: FIX
        if self.native_sep:
            join = os.path.join
        else:
            join = posixpath.join  # type: ignore
        main = self.items[0]
        self.files = []  # type: List[Tuple[str, str]] # path and contents for output files
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
                    self.files.append(file_entry)
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
                    self.files.append((join(self.base_path, fnam), f.read()))
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
            for file_path, contents in self.files:
                expand_errors(contents.split('\n'), self.output, file_path)
        else:
            raise ValueError(
                '{}, line {}: Error in test case description'.format(
                    self.file, main.line))

    def set_up(self) -> None:
        super().set_up()
        self.prepare_test_case()
        encountered_files = set()
        self.clean_up = []
        for path, content in self.files:
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

    def run(self) -> None:
        if self.name.endswith('-skip'):
            raise SkipTestCaseException()
        else:
            self.perform(self)

    def tear_down(self) -> None:
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
        super().tear_down()

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
        if issubclass(obj, DataSuite):
            return MypyDataSuite(name, parent=collector)


class MypyDataSuite(pytest.Class):  # type: ignore  # inheriting from Any
    def collect(self) -> Iterator['MypyDataCase']:
        for case in self.obj.cases():
            yield MypyDataCase(case.name, self, case)


class MypyDataCase(pytest.Item):  # type: ignore  # inheriting from Any
    def __init__(self, name: str, parent: MypyDataSuite, obj: DataDrivenTestCase) -> None:
        self.skip = False
        if name.endswith('-skip'):
            self.skip = True
            name = name[:-len('-skip')]

        super().__init__(name, parent)
        self.obj = obj

    def runtest(self) -> None:
        if self.skip:
            pytest.skip()
        update_data = self.config.getoption('--update-data', False)
        self.parent.obj(update_data=update_data).run_case(self.obj)

    def setup(self) -> None:
        self.obj.set_up()

    def teardown(self) -> None:
        self.obj.tear_down()

    def reportinfo(self) -> Tuple[str, int, str]:
        return self.obj.file, self.obj.line, self.obj.name

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

        return "data: {}:{}:\n{}".format(self.obj.file, self.obj.line, excrepr)


class DataSuite:
    def __init__(self, *, update_data: bool = False) -> None:
        self.update_data = update_data

    @classmethod
    def cases(cls) -> Iterable[DataDrivenTestCase]:
        """This implementation is required in order to cope with pytest's magic"""
        return []

    @abstractmethod
    def run_case(self, testcase: DataDrivenTestCase) -> None:
        raise NotImplementedError
