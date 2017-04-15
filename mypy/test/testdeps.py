"""Test cases for generating node-level dependencies (for fine-grained incremental checking)"""

import os.path

from typing import List
from mypy.server.deps import get_dependencies

from mypy.unit.config import test_temp_dir, test_data_prefix
from mypy.unit.helpers import assert_string_arrays_equal
from mypy.unit.builder import perform_build
from mypy.unit.data import parse_test_cases, DataDrivenTestCase, DataSuite

files = [
    'deps.test'
]


class GetDependenciesSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        src = '\n'.join(testcase.input)
        result = perform_build(src)
        errors, files, type_map = result.errors, result.files, result.types
        a = errors
        deps = get_dependencies('__main__', files['__main__'], type_map)

        for source, targets in sorted(deps.items()):
            line = '%s -> %s' % (source, ', '.join(sorted(targets)))
            # Clean up output a bit
            line = line.replace('__main__', 'm')
            a.append(line)

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(testcase.file,
                                                  testcase.line))
