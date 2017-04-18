"""Test cases for generating node-level dependencies (for fine-grained incremental checking)"""

from mypy.server.deps import get_dependencies

from mypy.unit.config import test_temp_dir
from mypy.unit.helpers import assert_string_arrays_equal
from mypy.unit.builder import perform_build
from mypy.unit.data import MypyDataItem


class GetDependenciesSuite(MypyDataItem):
    files = [
        'deps.test'
    ]
    optional_out = True
    base_path = test_temp_dir

    def run_case(self) -> None:
        src = '\n'.join(self.input)
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
            self.output, a,
            'Invalid output ({}, line {})'.format(self.file, self.line))
