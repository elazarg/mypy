"""Semantic analyzer test cases"""

import os.path

from typing import Dict, List

from mypy import build
from mypy.build import BuildSource
from mypy.errors import CompileError
from mypy.nodes import TypeInfo
from mypy.options import Options
from mypy.unit.data import MypyDataItem
from mypy.unit.config import test_temp_dir
from mypy.unit.helpers import (
    assert_string_arrays_equal, normalize_error_messages, casefile_pyversion,
)
from mypy.unit.builder import perform_build


# Semantic analyzer test cases: dump parse tree


def get_semanal_options() -> Options:
    options = Options()
    options.use_builtins_fixtures = True
    options.semantic_analysis_only = True
    options.show_traceback = True
    return options


class SemAnalSuite(MypyDataItem):

    # Semantic analysis test case description files.
    files = ['semanal-basic.test',
             'semanal-expressions.test',
             'semanal-classes.test',
             'semanal-types.test',
             'semanal-typealiases.test',
             'semanal-modules.test',
             'semanal-statements.test',
             'semanal-abstractclasses.test',
             'semanal-namedtuple.test',
             'semanal-typeddict.test',
             'semanal-classvar.test',
             'semanal-python2.test']

    optional_out = True

    def run_case(self) -> None:
        """Perform a semantic analysis test case.

        The testcase argument contains a description of the test case
        (inputs and output).
        """

        try:
            src = '\n'.join(self.input)
            options = get_semanal_options()
            options.python_version = casefile_pyversion(self.file)
            result = build.build(sources=[BuildSource('main', None, src)],
                                 options=options,
                                 alt_lib_path=test_temp_dir)
            a = result.errors
            if a:
                raise CompileError(a)
            # Include string representations of the source files in the actual
            # output.
            for fnam in sorted(result.files.keys()):
                f = result.files[fnam]
                # Omit the builtins module and files with a special marker in the
                # path.
                # TODO the test is not reliable
                if (not f.path.endswith((os.sep + 'builtins.pyi',
                                         'typing.pyi',
                                         'mypy_extensions.pyi',
                                         'abc.pyi',
                                         'collections.pyi'))
                        and not os.path.basename(f.path).startswith('_')
                        and not os.path.splitext(
                            os.path.basename(f.path))[0].endswith('_')):
                    a += str(f).split('\n')
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            self.output, a,
            'Invalid semantic analyzer output ({}, line {})'.format(self.file,
                                                                    self.line))


# Semantic analyzer error test cases


class SemAnalErrorSuite(MypyDataItem):

    # Paths to files containing test case descriptions.
    files = ['semanal-errors.test']
    base_path = test_temp_dir
    optional_out = True

    def run_case(self) -> None:
        """Perform a test case."""

        try:
            src = '\n'.join(self.input)
            res = build.build(sources=[BuildSource('main', None, src)],
                              options=get_semanal_options(),
                              alt_lib_path=test_temp_dir)
            a = res.errors
            assert a, 'No errors reported in {}, line {}'.format(self.file, self.line)
        except CompileError as e:
            # Verify that there was a compile error and that the error messages
            # are equivalent.
            a = e.messages
        assert_string_arrays_equal(
            self.output, normalize_error_messages(a),
            'Invalid compiler output ({}, line {})'.format(self.file, self.line))


# SymbolNode table export test cases


class SemAnalSymtableSuite(MypyDataItem):

    # Test case descriptions
    files = ['semanal-symtable.test']

    def run_case(self) -> None:
        """Perform a test case."""
        try:
            # Build test case input.
            src = '\n'.join(self.input)
            result = build.build(sources=[BuildSource('main', None, src)],
                                 options=get_semanal_options(),
                                 alt_lib_path=test_temp_dir)
            # The output is the symbol table converted into a string.
            a = result.errors
            if a:
                raise CompileError(a)
            for f in sorted(result.files.keys()):
                if f not in ('builtins', 'typing', 'abc'):
                    a.append('{}:'.format(f))
                    for s in str(result.files[f].names).split('\n'):
                        a.append('  ' + s)
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            self.output, a,
            'Invalid semantic analyzer output ({}, line {})'.format(
                self.file, self.line))


class SemAnalTypeInfoSuite(MypyDataItem):

    # Type info export test cases

    semanal_typeinfo_files = ['semanal-typeinfo.test']

    def run_case(self) -> None:
        """Perform a test case."""
        try:
            # Build test case input.
            src = '\n'.join(self.input)
            result = build.build(sources=[BuildSource('main', None, src)],
                                 options=get_semanal_options(),
                                 alt_lib_path=test_temp_dir)
            a = result.errors
            if a:
                raise CompileError(a)

            # Collect all TypeInfos in top-level modules.
            typeinfos = TypeInfoMap()
            for f in result.files.values():
                for n in f.names.values():
                    if isinstance(n.node, TypeInfo):
                        typeinfos[n.fullname] = n.node

            # The output is the symbol table converted into a string.
            a = str(typeinfos).split('\n')
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            self.output, a,
            'Invalid semantic analyzer output ({}, line {})'.format(
                self.file, self.line))


class TypeInfoMap(Dict[str, TypeInfo]):
    def __str__(self) -> str:
        a = ['TypeInfoMap(']  # type: List[str]
        for x, y in sorted(self.items()):
            if isinstance(x, str) and (not x.startswith('builtins.') and
                                       not x.startswith('typing.') and
                                       not x.startswith('abc.')):
                ti = ('\n' + '  ').join(str(y).split('\n'))
                a.append('  {} : {}'.format(x, ti))
        a[-1] += ')'
        return '\n'.join(a)
