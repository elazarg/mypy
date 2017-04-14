import sys
import re
import os
import tempfile

from typing import List, Dict, Tuple, Any

from mypy import defaults


# AssertStringArraysEqual displays special line alignment helper messages if
# the first different line has at least this many characters,
MIN_LINE_LENGTH_FOR_ALIGNMENT = 5


def assert_string_arrays_equal(expected: List[str], actual: List[str],
                               msg: str) -> None:
    """Assert that two string arrays are equal.

    Display any differences in a human-readable form.
    """

    actual = clean_up(actual)

    if actual != expected:
        num_skip_start = num_skipped_prefix_lines(expected, actual)
        num_skip_end = num_skipped_suffix_lines(expected, actual)

        sys.stderr.write('Expected:\n')

        # If omit some lines at the beginning, indicate it by displaying a line
        # with '...'.
        if num_skip_start > 0:
            sys.stderr.write('  ...\n')

        # Keep track of the first different line.
        first_diff = -1

        # Display only this many first characters of identical lines.
        width = 75

        for i in range(num_skip_start, len(expected) - num_skip_end):
            if i >= len(actual) or expected[i] != actual[i]:
                if first_diff < 0:
                    first_diff = i
                sys.stderr.write('  {:<45} (diff)'.format(expected[i]))
            else:
                e = expected[i]
                sys.stderr.write('  ' + e[:width])
                if len(e) > width:
                    sys.stderr.write('...')
            sys.stderr.write('\n')
        if num_skip_end > 0:
            sys.stderr.write('  ...\n')

        sys.stderr.write('Actual:\n')

        if num_skip_start > 0:
            sys.stderr.write('  ...\n')

        for j in range(num_skip_start, len(actual) - num_skip_end):
            if j >= len(expected) or expected[j] != actual[j]:
                sys.stderr.write('  {:<45} (diff)'.format(actual[j]))
            else:
                a = actual[j]
                sys.stderr.write('  ' + a[:width])
                if len(a) > width:
                    sys.stderr.write('...')
            sys.stderr.write('\n')
        if actual == []:
            sys.stderr.write('  (empty)\n')
        if num_skip_end > 0:
            sys.stderr.write('  ...\n')

        sys.stderr.write('\n')

        if first_diff >= 0 and first_diff < len(actual) and (
                len(expected[first_diff]) >= MIN_LINE_LENGTH_FOR_ALIGNMENT
                or len(actual[first_diff]) >= MIN_LINE_LENGTH_FOR_ALIGNMENT):
            # Display message that helps visualize the differences between two
            # long lines.
            show_align_message(expected[first_diff], actual[first_diff])

        raise AssertionFailure(msg)


class ProtoTestCase:
    def __init__(self, name: str) -> None:
        self.name = name
        self.prefix = typename(type(self)) + '.'
        self.old_cwd = None  # type: str
        self.tmpdir = None  # type: tempfile.TemporaryDirectory

    def set_up(self) -> None:
        self.old_cwd = os.getcwd()
        self.tmpdir = tempfile.TemporaryDirectory(
            prefix='mypy-test-',
            dir=os.path.abspath('tmp-test-dirs')
        )
        os.chdir(self.tmpdir.name)
        os.mkdir('tmp')

    def tear_down(self) -> None:
        os.chdir(self.old_cwd)
        self.tmpdir.cleanup()
        self.old_cwd = None
        self.tmpdir = None


def show_align_message(s1: str, s2: str) -> None:
    """Align s1 and s2 so that the their first difference is highlighted.

    For example, if s1 is 'foobar' and s2 is 'fobar', display the
    following lines:

      E: foobar
      A: fobar
           ^

    If s1 and s2 are long, only display a fragment of the strings around the
    first difference. If s1 is very short, do nothing.
    """

    # Seeing what went wrong is trivial even without alignment if the expected
    # string is very short. In this case do nothing to simplify output.
    if len(s1) < 4:
        return

    maxw = 72  # Maximum number of characters shown

    sys.stderr.write('Alignment of first line difference:\n')

    trunc = False
    while s1[:30] == s2[:30]:
        s1 = s1[10:]
        s2 = s2[10:]
        trunc = True

    if trunc:
        s1 = '...' + s1
        s2 = '...' + s2

    max_len = max(len(s1), len(s2))
    extra = ''
    if max_len > maxw:
        extra = '...'

    # Write a chunk of both lines, aligned.
    sys.stderr.write('  E: {}{}\n'.format(s1[:maxw], extra))
    sys.stderr.write('  A: {}{}\n'.format(s2[:maxw], extra))
    # Write an indicator character under the different columns.
    sys.stderr.write('     ')
    for j in range(min(maxw, max(len(s1), len(s2)))):
        if s1[j:j + 1] != s2[j:j + 1]:
            sys.stderr.write('^')  # Difference
            break
        else:
            sys.stderr.write(' ')  # Equal
    sys.stderr.write('\n')


def assert_string_arrays_equal_wildcards(expected: List[str],
                                         actual: List[str],
                                         msg: str) -> None:
    # Like above, but let a line with only '...' in expected match any number
    # of lines in actual.
    actual = clean_up(actual)

    while actual != [] and actual[-1] == '':
        actual = actual[:-1]

    # Expand "..." wildcards away.
    expected = match_array(expected, actual)
    assert_string_arrays_equal(expected, actual, msg)


def clean_up(a: List[str]) -> List[str]:
    """Remove common directory prefix from all strings in a.

    This uses a naive string replace; it seems to work well enough. Also
    remove trailing carriage returns.
    """
    res = []
    for s in a:
        prefix = os.sep
        ss = s
        for p in prefix, prefix.replace(os.sep, '/'):
            if p != '/' and p != '//' and p != '\\' and p != '\\\\':
                ss = ss.replace(p, '')
        # Ignore spaces at end of line.
        ss = re.sub(' +$', '', ss)
        res.append(re.sub('\\r$', '', ss))
    return res


def match_array(pattern: List[str], target: List[str]) -> List[str]:
    """Expand '...' wildcards in pattern by matching against target."""

    res = []  # type: List[str]
    i = 0
    j = 0

    while i < len(pattern):
        if pattern[i] == '...':
            # Wildcard in pattern.
            if i + 1 == len(pattern):
                # Wildcard at end of pattern; match the rest of target.
                res.extend(target[j:])
                # Finished.
                break
            else:
                # Must find the instance of the next pattern line in target.
                jj = j
                while jj < len(target):
                    if target[jj] == pattern[i + 1]:
                        break
                    jj += 1
                if jj == len(target):
                    # No match. Get out.
                    res.extend(pattern[i:])
                    break
                res.extend(target[j:jj])
                i += 1
                j = jj
        elif (j < len(target) and (pattern[i] == target[j]
                                   or (i + 1 < len(pattern)
                                       and j + 1 < len(target)
                                       and pattern[i + 1] == target[j + 1]))):
            # In sync; advance one line. The above condition keeps sync also if
            # only a single line is different, but loses it if two consecutive
            # lines fail to match.
            res.append(pattern[i])
            i += 1
            j += 1
        else:
            # Out of sync. Get out.
            res.extend(pattern[i:])
            break
    return res


def num_skipped_prefix_lines(a1: List[str], a2: List[str]) -> int:
    num_eq = 0
    while num_eq < min(len(a1), len(a2)) and a1[num_eq] == a2[num_eq]:
        num_eq += 1
    return max(0, num_eq - 4)


def num_skipped_suffix_lines(a1: List[str], a2: List[str]) -> int:
    num_eq = 0
    while (num_eq < min(len(a1), len(a2))
           and a1[-num_eq - 1] == a2[-num_eq - 1]):
        num_eq += 1
    return max(0, num_eq - 4)


def testfile_pyversion(path: str) -> Tuple[int, int]:
    if path.endswith('python2.test'):
        return defaults.PYTHON2_VERSION
    else:
        return defaults.PYTHON3_VERSION


def testcase_pyversion(path: str, testcase_name: str) -> Tuple[int, int]:
    if testcase_name.endswith('python2'):
        return defaults.PYTHON2_VERSION
    else:
        return testfile_pyversion(path)


def normalize_error_messages(messages: List[str]) -> List[str]:
    """Translate an array of error messages to use / as path separator."""

    a = []
    for m in messages:
        a.append(m.replace(os.sep, '/'))
    return a


class SkipTestCaseException(Exception):
    """Exception used to signal skipped test cases."""
    pass


class AssertionFailure(Exception):
    """Exception used to signal failed test cases."""
    def __init__(self, s: str = None) -> None:
        if s:
            super().__init__(s)
        else:
            super().__init__()


def assert_true(b: bool, msg: str = None) -> None:
    if not b:
        raise AssertionFailure(msg)


def assert_false(b: bool, msg: str = None) -> None:
    if b:
        raise AssertionFailure(msg)


def good_repr(obj: object) -> str:
    if isinstance(obj, str):
        if obj.count('\n') > 1:
            bits = ["'''\\"]
            for line in obj.split('\n'):
                # force repr to use ' not ", then cut it off
                bits.append(repr('"' + line)[2:-1])
            bits[-1] += "'''"
            return '\n'.join(bits)
    return repr(obj)


def assert_equal(a: object, b: object, fmt: str = '{} != {}') -> None:
    if a != b:
        raise AssertionFailure(fmt.format(good_repr(a), good_repr(b)))


def assert_not_equal(a: object, b: object, fmt: str = '{} == {}') -> None:
    if a == b:
        raise AssertionFailure(fmt.format(good_repr(a), good_repr(b)))


def assert_raises(typ: type, *rest: Any) -> None:
    """Usage: assert_raises(exception class[, message], function[, args])

    Call function with the given arguments and expect an exception of the given
    type.

    TODO use overloads for better type checking
    """
    # Parse arguments.
    msg = None  # type: str
    if isinstance(rest[0], str) or rest[0] is None:
        msg = rest[0]
        rest = rest[1:]
    f = rest[0]
    args = []  # type: List[Any]
    if len(rest) > 1:
        args = rest[1]
        assert len(rest) <= 2

    # Perform call and verify the exception.
    try:
        f(*args)
    except BaseException as e:
        if isinstance(e, KeyboardInterrupt):
            raise
        assert_type(typ, e)
        if msg:
            assert_equal(e.args[0], msg, 'Invalid message {}, expected {}')
    else:
        raise AssertionFailure('No exception raised')


def assert_type(typ: type, value: object) -> None:
    if type(value) != typ:
        raise AssertionFailure('Invalid type {}, expected {}'.format(
            typename(type(value)), typename(typ)))


def typename(t: type) -> str:
    if '.' in str(t):
        return str(t).split('.')[-1].rstrip("'>")
    else:
        return str(t)[8:-2]


def fail() -> None:
    raise AssertionFailure()
