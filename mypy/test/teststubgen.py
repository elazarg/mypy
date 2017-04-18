import glob
import importlib
import os.path
import shutil
import sys
import tempfile

from types import ModuleType
from typing import List, Tuple

from mypy.errors import CompileError
from mypy.stubgen import generate_stub, generate_stub_for_module
from mypy.stubgenc import generate_c_type_stub, infer_method_sig
from mypy.stubutil import (
    parse_signature, parse_all_signatures, build_signature, find_unique_signatures,
    infer_sig_from_docstring,
)
from mypy.unit.helpers import assert_string_arrays_equal, assert_equal
from mypy.unit.data import MypyDataItem


def test_parse_signature() -> None:
    assert_parse_signature('func()', ('func', [], []))


def test_parse_signature_with_args() -> None:
    assert_parse_signature('func(arg)', ('func', ['arg'], []))
    assert_parse_signature('do(arg, arg2)', ('do', ['arg', 'arg2'], []))


def test_parse_signature_with_optional_args() -> None:
    assert_parse_signature('func([arg])', ('func', [], ['arg']))
    assert_parse_signature('func(arg[, arg2])', ('func', ['arg'], ['arg2']))
    assert_parse_signature('func([arg[, arg2]])', ('func', [], ['arg', 'arg2']))


def test_parse_signature_with_default_arg() -> None:
    assert_parse_signature('func(arg=None)', ('func', [], ['arg']))
    assert_parse_signature('func(arg, arg2=None)', ('func', ['arg'], ['arg2']))
    assert_parse_signature('func(arg=1, arg2="")', ('func', [], ['arg', 'arg2']))


def test_parse_signature_with_qualified_function() -> None:
    assert_parse_signature('ClassName.func(arg)', ('func', ['arg'], []))


def test_parse_signature_with_kw_only_arg() -> None:
    assert_parse_signature('ClassName.func(arg, *, arg2=1)',
                           ('func', ['arg', '*'], ['arg2']))


def test_parse_signature_with_star_arg() -> None:
    assert_parse_signature('ClassName.func(arg, *args)',
                           ('func', ['arg', '*args'], []))


def test_parse_signature_with_star_star_arg() -> None:
    assert_parse_signature('ClassName.func(arg, **args)',
                           ('func', ['arg', '**args'], []))


def assert_parse_signature(sig: str, result: Tuple[str, List[str], List[str]]) -> None:
    assert_equal(parse_signature(sig), result)


def test_build_signature() -> None:
    assert_equal(build_signature([], []), '()')
    assert_equal(build_signature(['arg'], []), '(arg)')
    assert_equal(build_signature(['arg', 'arg2'], []), '(arg, arg2)')
    assert_equal(build_signature(['arg'], ['arg2']), '(arg, arg2=...)')
    assert_equal(build_signature(['arg'], ['arg2', '**x']), '(arg, arg2=..., **x)')


def test_parse_all_signatures() -> None:
    assert_equal(parse_all_signatures(['random text',
                                       '.. function:: fn(arg',
                                       '.. function:: fn()',
                                       '  .. method:: fn2(arg)']),
                 ([('fn', '()'),
                   ('fn2', '(arg)')], []))


def test_find_unique_signatures() -> None:
    assert_equal(find_unique_signatures(
        [('func', '()'),
         ('func', '()'),
         ('func2', '()'),
         ('func2', '(arg)'),
         ('func3', '(arg, arg2)')]),
        [('func', '()'),
         ('func3', '(arg, arg2)')])


def test_infer_sig_from_docstring() -> None:
    assert_equal(infer_sig_from_docstring('\nfunc(x) - y', 'func'), '(x)')
    assert_equal(infer_sig_from_docstring('\nfunc(x, Y_a=None)', 'func'), '(x, Y_a=None)')
    assert_equal(infer_sig_from_docstring('\nafunc(x) - y', 'func'), None)
    assert_equal(infer_sig_from_docstring('\nfunc(x, y', 'func'), None)
    assert_equal(infer_sig_from_docstring('\nfunc(x=z(y))', 'func'), None)
    assert_equal(infer_sig_from_docstring('\nfunc x', 'func'), None)


class StubgenPythonSuite(MypyDataItem):
    files = ['stubgen.test']

    def run_case(self) -> None:
        if 'stubgen-test-path' not in sys.path:
            sys.path.insert(0, 'stubgen-test-path')
        os.mkdir('stubgen-test-path')
        source = '\n'.join(self.input)
        handle = tempfile.NamedTemporaryFile(prefix='prog_', suffix='.py', dir='stubgen-test-path',
                                             delete=False)
        assert os.path.isabs(handle.name)
        path = os.path.basename(handle.name)
        name = path[:-3]
        path = os.path.join('stubgen-test-path', path)
        out_dir = '_out'
        os.mkdir(out_dir)
        try:
            handle.write(bytes(source, 'ascii'))
            handle.close()
            # Without this we may sometimes be unable to import the module below, as importlib
            # caches os.listdir() results in Python 3.3+ (Guido explained this to me).
            reset_importlib_caches()
            try:
                if self.name.endswith('_import'):
                    generate_stub_for_module(name, out_dir, quiet=True)
                else:
                    generate_stub(path, out_dir)
                a = load_output(out_dir)
            except CompileError as e:
                a = e.messages
            assert_string_arrays_equal(self.output, a,
                                       'Invalid output ({}, line {})'.format(
                                           self.file, self.line))
        finally:
            handle.close()
            os.unlink(handle.name)
            shutil.rmtree(out_dir)


def reset_importlib_caches() -> None:
    try:
        importlib.invalidate_caches()
    except (ImportError, AttributeError):
        pass


def load_output(dirname: str) -> List[str]:
    result = []  # type: List[str]
    entries = glob.glob('%s/*' % dirname)
    assert entries, 'No files generated'
    if len(entries) == 1:
        add_file(entries[0], result)
    else:
        for entry in entries:
            result.append('## %s ##' % entry)
            add_file(entry, result)
    return result


def add_file(path: str, result: List[str]) -> None:
    with open(path) as file:
        result.extend(file.read().splitlines())


def test_infer_hash_sig() -> None:
    assert_equal(infer_method_sig('__hash__'), '()')


def test_infer_getitem_sig() -> None:
    assert_equal(infer_method_sig('__getitem__'), '(index)')


def test_infer_setitem_sig() -> None:
    assert_equal(infer_method_sig('__setitem__'), '(index, object)')


def test_infer_binary_op_sig() -> None:
    for op in ('eq', 'ne', 'lt', 'le', 'gt', 'ge',
               'add', 'radd', 'sub', 'rsub', 'mul', 'rmul'):
        assert_equal(infer_method_sig('__%s__' % op), '(other)')


def test_infer_unary_op_sig() -> None:
    for op in ('neg', 'pos'):
        assert_equal(infer_method_sig('__%s__' % op), '()')


def test_generate_c_type_stub_no_crash_for_object() -> None:
    output = []  # type: List[str]
    mod = ModuleType('module', '')  # any module is fine
    generate_c_type_stub(mod, 'alias', object, output)
    assert_equal(output[0], 'class alias:')
