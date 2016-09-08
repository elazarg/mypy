"""Test cases for type inference helper functions."""

import typing

from mypy.myunit import Suite, assert_equal, assert_true
from mypy.checkexpr import map_actuals_to_formals
from mypy.nodes import Arg
from mypy.types import TupleType, ANY_TYPE


class MapActualsToFormalsSuite(Suite):
    """Test cases for checkexpr.map_actuals_to_formals."""

    def test_basic(self):
        self.assert_map([], [], [])

    def test_positional_only(self):
        self.assert_map([Arg.POS],
                        [Arg.POS],
                        [[0]])
        self.assert_map([Arg.POS, Arg.POS],
                        [Arg.POS, Arg.POS],
                        [[0], [1]])

    def test_optional(self):
        self.assert_map([],
                        [Arg.OPT],
                        [[]])
        self.assert_map([Arg.POS],
                        [Arg.OPT],
                        [[0]])
        self.assert_map([Arg.POS],
                        [Arg.OPT, Arg.OPT],
                        [[0], []])

    def test_callee_star(self):
        self.assert_map([],
                        [Arg.STAR],
                        [[]])
        self.assert_map([Arg.POS],
                        [Arg.STAR],
                        [[0]])
        self.assert_map([Arg.POS, Arg.POS],
                        [Arg.STAR],
                        [[0, 1]])

    def test_caller_star(self):
        self.assert_map([Arg.STAR],
                        [Arg.STAR],
                        [[0]])
        self.assert_map([Arg.POS, Arg.STAR],
                        [Arg.STAR],
                        [[0, 1]])
        self.assert_map([Arg.STAR],
                        [Arg.POS, Arg.STAR],
                        [[0], [0]])
        self.assert_map([Arg.STAR],
                        [Arg.OPT, Arg.STAR],
                        [[0], [0]])

    def test_too_many_caller_args(self):
        self.assert_map([Arg.POS],
                        [],
                        [])
        self.assert_map([Arg.STAR],
                        [],
                        [])
        self.assert_map([Arg.STAR],
                        [Arg.POS],
                        [[0]])

    def test_tuple_star(self):
        self.assert_vararg_map(
            [Arg.STAR],
            [Arg.POS],
            [[0]],
            self.tuple(ANY_TYPE))
        self.assert_vararg_map(
            [Arg.STAR],
            [Arg.POS, Arg.POS],
            [[0], [0]],
            self.tuple(ANY_TYPE, ANY_TYPE))
        self.assert_vararg_map(
            [Arg.STAR],
            [Arg.POS, Arg.OPT, Arg.OPT],
            [[0], [0], []],
            self.tuple(ANY_TYPE, ANY_TYPE))

    def tuple(self, *args):
        return TupleType(args, None)

    def test_named_args(self):
        self.assert_map(
            ['x'],
            [(Arg.POS, 'x')],
            [[0]])
        self.assert_map(
            ['y', 'x'],
            [(Arg.POS, 'x'), (Arg.POS, 'y')],
            [[1], [0]])

    def test_some_named_args(self):
        self.assert_map(
            ['y'],
            [(Arg.OPT, 'x'), (Arg.OPT, 'y'), (Arg.OPT, 'z')],
            [[], [0], []])

    def test_missing_named_arg(self):
        self.assert_map(
            ['y'],
            [(Arg.OPT, 'x')],
            [[]])

    def test_duplicate_named_arg(self):
        self.assert_map(
            ['x', 'x'],
            [(Arg.OPT, 'x')],
            [[0, 1]])

    def test_varargs_and_bare_asterisk(self):
        self.assert_map(
            [Arg.STAR],
            [Arg.STAR, (Arg.NAMED, 'x')],
            [[0], []])
        self.assert_map(
            [Arg.STAR, 'x'],
            [Arg.STAR, (Arg.NAMED, 'x')],
            [[0], [1]])

    def test_keyword_varargs(self):
        self.assert_map(
            ['x'],
            [Arg.STAR2],
            [[0]])
        self.assert_map(
            ['x', Arg.STAR2],
            [Arg.STAR2],
            [[0, 1]])
        self.assert_map(
            ['x', Arg.STAR2],
            [(Arg.POS, 'x'), Arg.STAR2],
            [[0], [1]])
        self.assert_map(
            [Arg.POS, Arg.STAR2],
            [(Arg.POS, 'x'), Arg.STAR2],
            [[0], [1]])

    def test_both_kinds_of_varargs(self):
        self.assert_map(
            [Arg.STAR, Arg.STAR2],
            [(Arg.POS, 'x'), (Arg.POS, 'y')],
            [[0, 1], [0, 1]])

    def test_special_cases(self):
        self.assert_map([Arg.STAR],
                        [Arg.STAR, Arg.STAR2],
                        [[0], []])
        self.assert_map([Arg.STAR, Arg.STAR2],
                        [Arg.STAR, Arg.STAR2],
                        [[0], [1]])
        self.assert_map([Arg.STAR2],
                        [(Arg.POS, 'x'), Arg.STAR2],
                        [[0], [0]])
        self.assert_map([Arg.STAR2],
                        [Arg.STAR2],
                        [[0]])

    def assert_map(self, caller_kinds, callee_kinds, expected):
        caller_kinds, caller_names = expand_caller_kinds(caller_kinds)
        callee_kinds, callee_names = expand_callee_kinds(callee_kinds)
        result = map_actuals_to_formals(
            caller_kinds,
            caller_names,
            callee_kinds,
            callee_names,
            lambda i: ANY_TYPE)
        assert_equal(result, expected)

    def assert_vararg_map(self, caller_kinds, callee_kinds, expected,
                          vararg_type):
        result = map_actuals_to_formals(
            caller_kinds,
            [],
            callee_kinds,
            [],
            lambda i: vararg_type)
        assert_equal(result, expected)


def expand_caller_kinds(kinds_or_names):
    kinds = []
    names = []
    for k in kinds_or_names:
        if isinstance(k, str):
            kinds.append(Arg.NAMED)
            names.append(k)
        else:
            kinds.append(k)
            names.append(None)
    return kinds, names


def expand_callee_kinds(kinds_and_names):
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
