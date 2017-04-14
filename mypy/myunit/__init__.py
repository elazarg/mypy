import importlib
import sys
import time
import traceback

from typing import List, Tuple, Any, Callable, Union, cast
from types import TracebackType

from mypy.test.helpers import ProtoTestCase, SkipTestCaseException, typename


# TODO remove global state
is_verbose = False
is_quiet = False
patterns = []  # type: List[str]
times = []  # type: List[Tuple[float, str]]


class TestCase(ProtoTestCase):
    def __init__(self, name: str, suite: 'Suite' = None,
                 func: Callable[[], None] = None) -> None:
        super().__init__(name)
        self.func = func
        self.suite = suite

    def run(self) -> None:
        if self.func:
            self.func()

    def set_up(self) -> None:
        super().set_up()
        if self.suite:
            self.suite.set_up()

    def tear_down(self) -> None:
        if self.suite:
            self.suite.tear_down()
        super().tear_down()


class Suite:
    def __init__(self) -> None:
        self.prefix = typename(type(self)) + '.'

    def set_up(self) -> None:
        pass

    def tear_down(self) -> None:
        pass

    def cases(self) -> None:
        for m in dir(self):
            if m.startswith('test_'):
                t = getattr(self, m)
                yield TestCase(m, self, t)

    def run_case(self, testcase) -> None:
        testcase.run()

    def skip(self) -> None:
        raise SkipTestCaseException()


def add_suites_from_module(suites: List[Suite], mod_name: str) -> None:
    mod = importlib.import_module(mod_name)
    got_suite = False
    for suite in mod.__dict__.values():
        if isinstance(suite, type) and issubclass(suite, Suite) and suite is not Suite:
            got_suite = True
            suites.append(cast(Callable[[], Suite], suite)())
    if not got_suite:
        # Sanity check in case e.g. it uses unittest instead of a myunit.
        # The codecs tests do since they need to be python2-compatible.
        sys.exit('Test module %s had no test!' % mod_name)


class ListSuite(Suite):
    def __init__(self, suites: List[Suite]) -> None:
        for suite in suites:
            mod_name = type(suite).__module__.replace('.', '_')
            mod_name = mod_name.replace('mypy_', '')
            mod_name = mod_name.replace('test_', '')
            mod_name = mod_name.strip('_').replace('__', '_')
            type_name = type(suite).__name__
            name = 'test_%s_%s' % (mod_name, type_name)
            setattr(self, name, suite)
        super().__init__()


def main(args: List[str] = None) -> None:
    global patterns, is_verbose, is_quiet
    if not args:
        args = sys.argv[1:]
    is_verbose = False
    is_quiet = False
    suites = []  # type: List[Suite]
    patterns = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '-v':
            is_verbose = True
        elif a == '-q':
            is_quiet = True
        elif a == '-m':
            i += 1
            if i == len(args):
                sys.exit('-m requires an argument')
            add_suites_from_module(suites, args[i])
        elif not a.startswith('-'):
            patterns.append(a)
        else:
            sys.exit('Usage: python -m mypy.myunit [-v] [-q]'
                    + ' -m mypy.test.module [-m mypy.test.module ...] [filter ...]')
        i += 1
    if len(patterns) == 0:
        patterns.append('*')
    if not suites:
        sys.exit('At least one -m argument is required')

    t = ListSuite(suites)
    num_total, num_fail, num_skip = run_test_recursive(t, 0, 0, 0, '', 0)

    skip_msg = ''
    if num_skip > 0:
        skip_msg = ', {} skipped'.format(num_skip)

    if num_fail == 0:
        if not is_quiet:
            print('%d test cases run%s, all passed.' % (num_total, skip_msg))
            print('*** OK ***')
    else:
        sys.stderr.write('%d/%d test cases failed%s.\n' % (num_fail,
                                                           num_total,
                                                           skip_msg))
        sys.stderr.write('*** FAILURE ***\n')
        sys.exit(1)


def run_test_recursive(test: Any, num_total: int, num_fail: int, num_skip: int,
                       prefix: str, depth: int) -> Tuple[int, int, int]:
    """The first argument may be TestCase, Suite or (str, Suite)."""
    if isinstance(test, TestCase):
        name = prefix + test.name
        for pattern in patterns:
            if match_pattern(name, pattern):
                match = True
                break
        else:
            match = False
        if match:
            is_fail, is_skip = run_single_test(name, test)
            if is_fail: num_fail += 1
            if is_skip: num_skip += 1
            num_total += 1
    else:
        suite = None  # type: Suite
        suite_prefix = ''
        if isinstance(test, list) or isinstance(test, tuple):
            suite = test[1]
            suite_prefix = test[0]
        else:
            suite = test
            suite_prefix = test.prefix

        for stest in suite.cases():
            new_prefix = prefix
            if depth > 0:
                new_prefix = prefix + suite_prefix
            num_total, num_fail, num_skip = run_test_recursive(
                stest, num_total, num_fail, num_skip, new_prefix, depth + 1)
    return num_total, num_fail, num_skip


def run_single_test(name: str, test: Any) -> Tuple[bool, bool]:
    if is_verbose:
        sys.stderr.write(name)
        sys.stderr.flush()

    time0 = time.time()
    test.set_up()  # FIX: check exceptions
    exc_traceback = None  # type: Any
    try:
        test.run()
    except BaseException as e:
        if isinstance(e, KeyboardInterrupt):
            raise
        exc_type, exc_value, exc_traceback = sys.exc_info()
    test.tear_down()  # FIX: check exceptions
    times.append((time.time() - time0, name))

    if exc_traceback:
        if isinstance(exc_value, SkipTestCaseException):
            if is_verbose:
                sys.stderr.write(' (skipped)\n')
            return False, True
        else:
            handle_failure(name, exc_type, exc_value, exc_traceback)
            return True, False
    elif is_verbose:
        sys.stderr.write('\n')

    return False, False


def handle_failure(name: str,
                   exc_type: type,
                   exc_value: BaseException,
                   exc_traceback: TracebackType,
                   ) -> None:
    # Report failed test case.
    if is_verbose:
        sys.stderr.write('\n\n')
    msg = ''
    if exc_value.args and exc_value.args[0]:
        msg = ': ' + str(exc_value)
    else:
        msg = ''
    if not isinstance(exc_value, SystemExit):
        # We assume that before doing exit() (which raises SystemExit) we've printed
        # enough context about what happened so that a stack trace is not useful.
        # In particular, uncaught exceptions during semantic analysis or type checking
        # call exit() and they already print out a stack trace.
        sys.stderr.write('Traceback (most recent call last):\n')
        tb = traceback.format_tb(exc_traceback)
        tb = clean_traceback(tb)
        for s in tb:
            sys.stderr.write(s)
    else:
        sys.stderr.write('\n')
    exception = typename(exc_type)
    sys.stderr.write('{}{}\n\n'.format(exception, msg))
    sys.stderr.write('{} failed\n\n'.format(name))


def match_pattern(s: str, p: str) -> bool:
    if len(p) == 0:
        return len(s) == 0
    elif p[0] == '*':
        if len(p) == 1:
            return True
        else:
            for i in range(len(s) + 1):
                if match_pattern(s[i:], p[1:]):
                    return True
            return False
    elif len(s) == 0:
        return False
    else:
        return s[0] == p[0] and match_pattern(s[1:], p[1:])


def clean_traceback(tb: List[str]) -> List[str]:
    # Remove clutter from the traceback.
    start = 0
    for i, s in enumerate(tb):
        if '\n    test.run()\n' in s or '\n    self.func()\n' in s:
            start = i + 1
    tb = tb[start:]
    for f in ['assert_equal', 'assert_not_equal', 'assert_type',
              'assert_raises', 'assert_true']:
        if tb != [] and ', in {}\n'.format(f) in tb[-1]:
            tb = tb[:-1]
    return tb
