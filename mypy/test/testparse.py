"""Tests for the mypy parser."""

from mypy.unit.helpers import assert_string_arrays_equal, AssertionFailure

from mypy import defaults
from mypy.errors import CompileError
from mypy.options import Options
from mypy.parse import parse
from mypy.unit.data import MypyDataItem


class ParserSuite(MypyDataItem):
    files = ['parse.test',
             'parse-python2.test']

    def run_case(self) -> None:
        """Perform a single parser test case.

        The argument contains the description of the test case.
        """
        options = Options()

        if self.file.endswith('python2.test'):
            options.python_version = defaults.PYTHON2_VERSION
        else:
            options.python_version = defaults.PYTHON3_VERSION

        try:
            n = parse(bytes('\n'.join(self.input), 'ascii'),
                      fnam='main',
                      errors=None,
                      options=options)
            a = str(n).split('\n')
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(self.output, a,
                                   'Invalid parser output ({}, line {})'.format(
                                       self.file, self.line))


# The file name shown in test case output. This is displayed in error
# messages, and must match the file name in the test case descriptions.
INPUT_FILE_NAME = 'file'


class ParseErrorSuite(MypyDataItem):
    files = ['parse-errors.test']

    def run_case(self) -> None:
        try:
            # Compile temporary file. The test file contains non-ASCII characters.
            parse(bytes('\n'.join(self.input), 'utf-8'), INPUT_FILE_NAME, None, Options())
            raise AssertionFailure('No errors reported')
        except CompileError as e:
            # Verify that there was a compile error and that the error messages
            # are equivalent.
            assert_string_arrays_equal(
                self.output, e.messages,
                'Invalid compiler output ({}, line {})'.format(self.file,
                                                               self.line))
