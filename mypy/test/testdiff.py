"""Test cases for AST diff (used for fine-grained incremental checking)"""

import os.path

from typing import List

from mypy.server.astdiff import compare_symbol_tables
from mypy.unit.config import test_temp_dir, test_data_prefix
from mypy.unit.helpers import assert_string_arrays_equal
from mypy.unit.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.unit.builder import perform_build

files = [
    'diff.test'
]


class ASTDiffSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        first_src = '\n'.join(testcase.input)
        files_dict = dict(testcase.files)
        second_src = files_dict['tmp/next.py']

        result1 = perform_build(first_src)
        messages1, files1 = result1.errors, result1.files
        result2 = perform_build(second_src)
        messages2, files2 = result2.errors, result2.files

        a = []
        if messages1:
            a.extend(messages1)
        if messages2:
            a.append('== next ==')
            a.extend(messages2)

        diff = compare_symbol_tables(
            '__main__',
            files1['__main__'].names,
            files2['__main__'].names)
        for trigger in sorted(diff):
            a.append(trigger)

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(testcase.file,
                                                  testcase.line))
