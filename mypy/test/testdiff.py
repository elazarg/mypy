"""Test cases for AST diff (used for fine-grained incremental checking)"""

from mypy.server.astdiff import compare_symbol_tables
from mypy.unit.helpers import assert_string_arrays_equal
from mypy.unit.data import MypyDataItem
from mypy.unit.builder import perform_build


class ASTDiffSuite(MypyDataItem):
    files = [
        'diff.test'
    ]
    optional_out = True

    def run_case(self) -> None:
        first_src = '\n'.join(self.input)
        files_dict = dict(self.sub_files)
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
            self.output, a,
            'Invalid output ({}, line {})'.format(self.file,
                                                  self.line))
