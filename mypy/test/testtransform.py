"""Identity AST transform test cases"""

import os.path

from mypy import build
from mypy.build import BuildSource
from mypy.errors import CompileError
from mypy.options import Options
from mypy.treetransform import TransformVisitor
from mypy.types import Type
from mypy.unit.config import test_temp_dir
from mypy.unit.helpers import assert_string_arrays_equal, casefile_pyversion
from mypy.unit.data import MypyDataItem


class TransformSuite(MypyDataItem):

    # Reuse semantic analysis test cases.
    files = ['semanal-basic.test',
             'semanal-expressions.test',
             'semanal-classes.test',
             'semanal-types.test',
             'semanal-modules.test',
             'semanal-statements.test',
             'semanal-abstractclasses.test',
             'semanal-python2.test']

    def run_case(self) -> None:
        try:
            src = '\n'.join(self.input)
            options = Options()
            options.use_builtins_fixtures = True
            options.semantic_analysis_only = True
            options.show_traceback = True
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
                                         'abc.pyi'))
                    and not os.path.basename(f.path).startswith('_')
                    and not os.path.splitext(
                        os.path.basename(f.path))[0].endswith('_')):
                    t = TestTransformVisitor()
                    f = t.mypyfile(f)
                    a += str(f).split('\n')
        except CompileError as e:
            a = e.messages
        assert_string_arrays_equal(
            self.output, a,
            'Invalid semantic analyzer output ({}, line {})'.format(self.file,
                                                                    self.line))


class TestTransformVisitor(TransformVisitor):
    def type(self, type: Type) -> Type:
        assert type is not None
        return type
