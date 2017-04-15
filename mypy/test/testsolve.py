"""Test cases for the constraint solver used in type inference."""

from typing import List, Union, Tuple

from mypy.test.helpers import assert_equal
from mypy.constraints import SUPERTYPE_OF, SUBTYPE_OF, Constraint
from mypy.solve import solve_constraints
from mypy.typefixture import TypeFixture
from mypy.types import Type, TypeVarType, TypeVarId

fx = TypeFixture()


def test_empty_input() -> None:
    assert_solve([], [], [])


def test_simple_supertype_constraints() -> None:
    assert_solve([fx.t.id],
                 [supc(fx.t, fx.a)],
                 [(fx.a, fx.o)])
    assert_solve([fx.t.id],
                 [supc(fx.t, fx.a),
                 supc(fx.t, fx.b)],
                 [(fx.a, fx.o)])


def test_simple_subtype_constraints() -> None:
    assert_solve([fx.t.id],
                 [subc(fx.t, fx.a)],
                 [fx.a])
    assert_solve([fx.t.id],
                 [subc(fx.t, fx.a),
                 subc(fx.t, fx.b)],
                 [fx.b])


def test_both_kinds_of_constraints() -> None:
    assert_solve([fx.t.id],
                 [supc(fx.t, fx.b),
                 subc(fx.t, fx.a)],
                 [(fx.b, fx.a)])


def test_unsatisfiable_constraints() -> None:
    # The constraints are impossible to satisfy.
    assert_solve([fx.t.id],
                 [supc(fx.t, fx.a),
                 subc(fx.t, fx.b)],
                 [None])


def test_exactly_specified_result() -> None:
    assert_solve([fx.t.id],
                 [supc(fx.t, fx.b),
                 subc(fx.t, fx.b)],
                 [(fx.b, fx.b)])


def test_multiple_variables() -> None:
    assert_solve([fx.t.id, fx.s.id],
                 [supc(fx.t, fx.b),
                 supc(fx.s, fx.c),
                 subc(fx.t, fx.a)],
                 [(fx.b, fx.a), (fx.c, fx.o)])


def test_no_constraints_for_var() -> None:
    assert_solve([fx.t.id],
                 [],
                 [fx.uninhabited])
    assert_solve([fx.t.id, fx.s.id],
                 [],
                 [fx.uninhabited, fx.uninhabited])
    assert_solve([fx.t.id, fx.s.id],
                 [supc(fx.s, fx.a)],
                 [fx.uninhabited, (fx.a, fx.o)])


def test_simple_constraints_with_dynamic_type() -> None:
    assert_solve([fx.t.id],
                 [supc(fx.t, fx.anyt)],
                 [(fx.anyt, fx.anyt)])
    assert_solve([fx.t.id],
                 [supc(fx.t, fx.anyt),
                 supc(fx.t, fx.anyt)],
                 [(fx.anyt, fx.anyt)])
    assert_solve([fx.t.id],
                 [supc(fx.t, fx.anyt),
                 supc(fx.t, fx.a)],
                 [(fx.anyt, fx.anyt)])

    assert_solve([fx.t.id],
                 [subc(fx.t, fx.anyt)],
                 [(fx.anyt, fx.anyt)])
    assert_solve([fx.t.id],
                 [subc(fx.t, fx.anyt),
                 subc(fx.t, fx.anyt)],
                 [(fx.anyt, fx.anyt)])
    # assert_solve([fx.t.id],
    #                   [subc(fx.t, fx.anyt),
    #                    subc(fx.t, fx.a)],
    #                   [(fx.anyt, fx.anyt)])
    # TODO: figure out what this should be after changes to meet(any, X)


def test_both_normal_and_any_types_in_results() -> None:
    # If one of the bounds is any, we promote the other bound to
    # any as well, since otherwise the type range does not make sense.
    assert_solve([fx.t.id],
                 [supc(fx.t, fx.a),
                 subc(fx.t, fx.anyt)],
                 [(fx.anyt, fx.anyt)])

    assert_solve([fx.t.id],
                 [supc(fx.t, fx.anyt),
                 subc(fx.t, fx.a)],
                 [(fx.anyt, fx.anyt)])


def assert_solve(vars: List[TypeVarId],
                 constraints: List[Constraint],
                 results: List[Union[Type, Tuple[Type, Type]]],
                 ) -> None:
    res = []
    for r in results:
        if isinstance(r, tuple):
            res.append(r[0])
        else:
            res.append(r)
    actual = solve_constraints(vars, constraints)
    assert_equal(str(actual), str(res))


def supc(type_var: TypeVarType, bound: Type) -> Constraint:
    return Constraint(type_var.id, SUPERTYPE_OF, bound)


def subc(type_var: TypeVarType, bound: Type) -> Constraint:
    return Constraint(type_var.id, SUBTYPE_OF, bound)
