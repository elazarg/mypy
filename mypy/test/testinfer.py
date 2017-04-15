"""Test cases for type inference helper functions."""

from typing import List, Optional, Tuple, Union

from mypy.checkexpr import map_actuals_to_formals
from mypy.nodes import ARG_POS, ARG_OPT, ARG_STAR, ARG_STAR2, ARG_NAMED
from mypy.types import AnyType, TupleType, Type
from mypy.unit.helpers import assert_equal


"""Test cases for checkexpr.map_actuals_to_formals."""


def test_basic() -> None:
    assert_map([], [], [])


def test_positional_only() -> None:
    assert_map([ARG_POS],
               [ARG_POS],
               [[0]])
    assert_map([ARG_POS, ARG_POS],
               [ARG_POS, ARG_POS],
               [[0], [1]])


def test_optional() -> None:
    assert_map([],
               [ARG_OPT],
               [[]])
    assert_map([ARG_POS],
               [ARG_OPT],
               [[0]])
    assert_map([ARG_POS],
               [ARG_OPT, ARG_OPT],
               [[0], []])


def test_callee_star() -> None:
    assert_map([],
               [ARG_STAR],
               [[]])
    assert_map([ARG_POS],
               [ARG_STAR],
               [[0]])
    assert_map([ARG_POS, ARG_POS],
               [ARG_STAR],
               [[0, 1]])


def test_caller_star() -> None:
    assert_map([ARG_STAR],
               [ARG_STAR],
               [[0]])
    assert_map([ARG_POS, ARG_STAR],
               [ARG_STAR],
               [[0, 1]])
    assert_map([ARG_STAR],
               [ARG_POS, ARG_STAR],
               [[0], [0]])
    assert_map([ARG_STAR],
               [ARG_OPT, ARG_STAR],
               [[0], [0]])


def test_too_many_caller_args() -> None:
    assert_map([ARG_POS],
               [],
               [])
    assert_map([ARG_STAR],
               [],
               [])
    assert_map([ARG_STAR],
               [ARG_POS],
               [[0]])


def test_tuple_star() -> None:
    assert_vararg_map(
        [ARG_STAR],
        [ARG_POS],
        [[0]],
        make_tuple(AnyType()))
    assert_vararg_map(
        [ARG_STAR],
        [ARG_POS, ARG_POS],
        [[0], [0]],
        make_tuple(AnyType(), AnyType()))
    assert_vararg_map(
        [ARG_STAR],
        [ARG_POS, ARG_OPT, ARG_OPT],
        [[0], [0], []],
        make_tuple(AnyType(), AnyType()))


def make_tuple(*args: Type) -> TupleType:
    return TupleType(list(args), None)


def test_named_args() -> None:
    assert_map(
        ['x'],
        [(ARG_POS, 'x')],
        [[0]])
    assert_map(
        ['y', 'x'],
        [(ARG_POS, 'x'), (ARG_POS, 'y')],
        [[1], [0]])


def test_some_named_args() -> None:
    assert_map(
        ['y'],
        [(ARG_OPT, 'x'), (ARG_OPT, 'y'), (ARG_OPT, 'z')],
        [[], [0], []])


def test_missing_named_arg() -> None:
    assert_map(
        ['y'],
        [(ARG_OPT, 'x')],
        [[]])


def test_duplicate_named_arg() -> None:
    assert_map(
        ['x', 'x'],
        [(ARG_OPT, 'x')],
        [[0, 1]])


def test_varargs_and_bare_asterisk() -> None:
    assert_map(
        [ARG_STAR],
        [ARG_STAR, (ARG_NAMED, 'x')],
        [[0], []])
    assert_map(
        [ARG_STAR, 'x'],
        [ARG_STAR, (ARG_NAMED, 'x')],
        [[0], [1]])


def test_keyword_varargs() -> None:
    assert_map(
        ['x'],
        [ARG_STAR2],
        [[0]])
    assert_map(
        ['x', ARG_STAR2],
        [ARG_STAR2],
        [[0, 1]])
    assert_map(
        ['x', ARG_STAR2],
        [(ARG_POS, 'x'), ARG_STAR2],
        [[0], [1]])
    assert_map(
        [ARG_POS, ARG_STAR2],
        [(ARG_POS, 'x'), ARG_STAR2],
        [[0], [1]])


def test_both_kinds_of_varargs() -> None:
    assert_map(
        [ARG_STAR, ARG_STAR2],
        [(ARG_POS, 'x'), (ARG_POS, 'y')],
        [[0, 1], [0, 1]])


def test_special_cases() -> None:
    assert_map([ARG_STAR],
                    [ARG_STAR, ARG_STAR2],
                    [[0], []])
    assert_map([ARG_STAR, ARG_STAR2],
                    [ARG_STAR, ARG_STAR2],
                    [[0], [1]])
    assert_map([ARG_STAR2],
                    [(ARG_POS, 'x'), ARG_STAR2],
                    [[0], [0]])
    assert_map([ARG_STAR2],
                    [ARG_STAR2],
                    [[0]])


def assert_map(caller_kinds_: List[Union[int, str]],
               callee_kinds_: List[Union[int, Tuple[int, str]]],
               expected: List[List[int]],
               ) -> None:
    caller_kinds, caller_names = expand_caller_kinds(caller_kinds_)
    callee_kinds, callee_names = expand_callee_kinds(callee_kinds_)
    result = map_actuals_to_formals(
        caller_kinds,
        caller_names,
        callee_kinds,
        callee_names,
        lambda i: AnyType())
    assert_equal(result, expected)


def assert_vararg_map(caller_kinds: List[int],
                      callee_kinds: List[int],
                      expected: List[List[int]],
                      vararg_type: Type,
                      ) -> None:
    result = map_actuals_to_formals(
        caller_kinds,
        [],
        callee_kinds,
        [],
        lambda i: vararg_type)
    assert_equal(result, expected)


def expand_caller_kinds(kinds_or_names: List[Union[int, str]]
                        ) -> Tuple[List[int], List[Optional[str]]]:
    kinds = []
    names = []
    for k in kinds_or_names:
        if isinstance(k, str):
            kinds.append(ARG_NAMED)
            names.append(k)
        else:
            kinds.append(k)
            names.append(None)
    return kinds, names


def expand_callee_kinds(kinds_and_names: List[Union[int, Tuple[int, str]]]
                        ) -> Tuple[List[int], List[Optional[str]]]:
    kinds = []
    names = []
    for v in kinds_and_names:
        if isinstance(v, tuple):
            kinds.append(v[0])
            names.append(v[1])
        else:
            kinds.append(v)
            names.append(None)
    return kinds, names
