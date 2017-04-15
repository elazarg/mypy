"""Test cases for fine-grained incremental checking.

Each test cases runs a batch build followed by one or more fine-grained
incremental steps. We verify that each step produces the expected output.

See the comment at the top of test-data/unit/fine-grained.test for more
information.
"""

import os.path
import re
import shutil

from typing import List, Tuple, Dict

from mypy.server.update import FineGrainedBuildManager
from mypy.unit.config import test_temp_dir, test_data_prefix
from mypy.unit.helpers import assert_string_arrays_equal
from mypy.unit.data import parse_test_cases, DataDrivenTestCase, DataSuite
from mypy.unit.builder import perform_build

files = [
    'fine-grained.test'
]


class FineGrainedSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  None, test_temp_dir, True)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        main_src = '\n'.join(testcase.input)
        result = perform_build(main_src)
        messages, manager, graph = result.errors, result.manager, result.graph

        a = []
        if messages:
            a.extend(messages)

        fine_grained_manager = FineGrainedBuildManager(manager, graph)

        steps = find_steps()
        for changed_paths in steps:
            modules = []
            for module, path in changed_paths:
                new_path = re.sub(r'\.[0-9]+$', '', path)
                shutil.copy(path, new_path)
                modules.append(module)

            new_messages = fine_grained_manager.update(modules)
            new_messages = [re.sub('^tmp' + re.escape(os.sep), '', message)
                            for message in new_messages]

            a.append('==')
            a.extend(new_messages)

        # Normalize paths in test output (for Windows).
        a = [line.replace('\\', '/') for line in a]

        assert_string_arrays_equal(
            testcase.output, a,
            'Invalid output ({}, line {})'.format(testcase.file,
                                                  testcase.line))


def find_steps() -> List[List[Tuple[str, str]]]:
    """Return a list of build step representations.

    Each build step is a list of (module id, path) tuples, and each
    path is of form 'dir/mod.py.2' (where 2 is the step number).
    """
    steps = {}  # type: Dict[int, List[Tuple[str, str]]]
    for dn, dirs, files in os.walk(test_temp_dir):
        dnparts = dn.split(os.sep)
        assert dnparts[0] == test_temp_dir
        del dnparts[0]
        for filename in files:
            m = re.match(r'.*\.([0-9]+)$', filename)
            if m:
                num = int(m.group(1))
                assert num >= 2
                name = re.sub(r'\.py.*', '', filename)
                module = '.'.join(dnparts + [name])
                module = re.sub(r'\.__init__$', '', module)
                path = os.path.join(dn, filename)
                steps.setdefault(num, []).append((module, path))
    max_step = max(steps)
    return [steps[num] for num in range(2, max_step + 1)]
