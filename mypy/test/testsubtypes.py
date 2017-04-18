import pytest

from mypy.subtypes import is_subtype
from mypy.types import Type
from mypy.unit.helpers import assert_true
from mypy.unit.typefixture import InterfaceTypeFixture


def test_trivial_cases(fx) -> None:
    for simple in fx.a, fx.o, fx.b:
        assert_subtype(simple, simple)


def test_instance_subtyping(fx_inv) -> None:
    assert_strict_subtype(fx_inv.a, fx_inv.o)
    assert_strict_subtype(fx_inv.b, fx_inv.o)
    assert_strict_subtype(fx_inv.b, fx_inv.a)

    assert_not_subtype(fx_inv.a, fx_inv.d)
    assert_not_subtype(fx_inv.b, fx_inv.c)


def test_simple_generic_instance_subtyping_invariant(fx_inv) -> None:
    assert_subtype(fx_inv.ga, fx_inv.ga)
    assert_subtype(fx_inv.hab, fx_inv.hab)

    assert_not_subtype(fx_inv.ga, fx_inv.g2a)
    assert_not_subtype(fx_inv.ga, fx_inv.gb)
    assert_not_subtype(fx_inv.gb, fx_inv.ga)


def test_simple_generic_instance_subtyping_covariant(fx) -> None:
    assert_subtype(fx.ga, fx.ga)
    assert_subtype(fx.hab, fx.hab)

    assert_not_subtype(fx.ga, fx.g2a)
    assert_not_subtype(fx.ga, fx.gb)
    assert_subtype(fx.gb, fx.ga)


def test_simple_generic_instance_subtyping_contravariant(fx_contra) -> None:
    assert_subtype(fx_contra.ga, fx_contra.ga)
    assert_subtype(fx_contra.hab, fx_contra.hab)

    assert_not_subtype(fx_contra.ga, fx_contra.g2a)
    assert_subtype(fx_contra.ga, fx_contra.gb)
    assert_not_subtype(fx_contra.gb, fx_contra.ga)


def test_generic_subtyping_with_inheritance_invariant(fx_inv) -> None:
    assert_subtype(fx_inv.gsab, fx_inv.gb)
    assert_not_subtype(fx_inv.gsab, fx_inv.ga)
    assert_not_subtype(fx_inv.gsaa, fx_inv.gb)


def test_generic_subtyping_with_inheritance_covariant(fx) -> None:
    assert_subtype(fx.gsab, fx.gb)
    assert_subtype(fx.gsab, fx.ga)
    assert_not_subtype(fx.gsaa, fx.gb)


def test_generic_subtyping_with_inheritance_contravariant(fx_contra) -> None:
    assert_subtype(fx_contra.gsab, fx_contra.gb)
    assert_not_subtype(fx_contra.gsab, fx_contra.ga)
    assert_subtype(fx_contra.gsaa, fx_contra.gb)


def test_interface_subtyping(fx_inv) -> None:
    assert_subtype(fx_inv.e, fx_inv.f)
    assert_equivalent(fx_inv.f, fx_inv.f)
    assert_not_subtype(fx_inv.a, fx_inv.f)


@pytest.mark.skip(reason="TODO")
def test_generic_interface_subtyping() -> None:
    # TODO make this work
    fx2 = InterfaceTypeFixture()

    assert_subtype(fx2.m1, fx2.gfa)
    assert_not_subtype(fx2.m1, fx2.gfb)

    assert_equivalent(fx2.gfa, fx2.gfa)


def test_basic_callable_subtyping(fx_inv) -> None:
    assert_strict_subtype(fx_inv.callable(fx_inv.o, fx_inv.d),
                               fx_inv.callable(fx_inv.a, fx_inv.d))
    assert_strict_subtype(fx_inv.callable(fx_inv.d, fx_inv.b),
                               fx_inv.callable(fx_inv.d, fx_inv.a))

    assert_strict_subtype(fx_inv.callable(fx_inv.a, fx_inv.nonet),
                               fx_inv.callable(fx_inv.a, fx_inv.a))

    assert_unrelated(
        fx_inv.callable(fx_inv.a, fx_inv.a, fx_inv.a),
        fx_inv.callable(fx_inv.a, fx_inv.a))


def test_default_arg_callable_subtyping(fx_inv) -> None:
    assert_strict_subtype(
        fx_inv.callable_default(1, fx_inv.a, fx_inv.d, fx_inv.a),
        fx_inv.callable(fx_inv.a, fx_inv.d, fx_inv.a))

    assert_strict_subtype(
        fx_inv.callable_default(1, fx_inv.a, fx_inv.d, fx_inv.a),
        fx_inv.callable(fx_inv.a, fx_inv.a))

    assert_strict_subtype(
        fx_inv.callable_default(0, fx_inv.a, fx_inv.d, fx_inv.a),
        fx_inv.callable_default(1, fx_inv.a, fx_inv.d, fx_inv.a))

    assert_unrelated(
        fx_inv.callable_default(1, fx_inv.a, fx_inv.d, fx_inv.a),
        fx_inv.callable(fx_inv.d, fx_inv.d, fx_inv.a))

    assert_unrelated(
        fx_inv.callable_default(0, fx_inv.a, fx_inv.d, fx_inv.a),
        fx_inv.callable_default(1, fx_inv.a, fx_inv.a, fx_inv.a))

    assert_unrelated(
        fx_inv.callable_default(1, fx_inv.a, fx_inv.a),
        fx_inv.callable(fx_inv.a, fx_inv.a, fx_inv.a))


def test_var_arg_callable_subtyping_1(fx_inv) -> None:
    assert_strict_subtype(
        fx_inv.callable_var_arg(0, fx_inv.a, fx_inv.a),
        fx_inv.callable_var_arg(0, fx_inv.b, fx_inv.a))


def test_var_arg_callable_subtyping_2(fx_inv) -> None:
    assert_strict_subtype(
        fx_inv.callable_var_arg(0, fx_inv.a, fx_inv.a),
        fx_inv.callable(fx_inv.b, fx_inv.a))


def test_var_arg_callable_subtyping_3(fx_inv) -> None:
    assert_strict_subtype(
        fx_inv.callable_var_arg(0, fx_inv.a, fx_inv.a),
        fx_inv.callable(fx_inv.a))


def test_var_arg_callable_subtyping_4(fx_inv) -> None:
    assert_strict_subtype(
        fx_inv.callable_var_arg(1, fx_inv.a, fx_inv.d, fx_inv.a),
        fx_inv.callable(fx_inv.b, fx_inv.a))


def test_var_arg_callable_subtyping_5(fx_inv) -> None:
    assert_strict_subtype(
        fx_inv.callable_var_arg(0, fx_inv.a, fx_inv.d, fx_inv.a),
        fx_inv.callable(fx_inv.b, fx_inv.a))


def test_var_arg_callable_subtyping_6(fx_inv) -> None:
    assert_strict_subtype(
        fx_inv.callable_var_arg(0, fx_inv.a, fx_inv.f, fx_inv.d),
        fx_inv.callable_var_arg(0, fx_inv.b, fx_inv.e, fx_inv.d))


def test_var_arg_callable_subtyping_7(fx_inv) -> None:
    assert_not_subtype(
        fx_inv.callable_var_arg(0, fx_inv.b, fx_inv.d),
        fx_inv.callable(fx_inv.a, fx_inv.d))


def test_var_arg_callable_subtyping_8(fx_inv) -> None:
    assert_not_subtype(
        fx_inv.callable_var_arg(0, fx_inv.b, fx_inv.d),
        fx_inv.callable_var_arg(0, fx_inv.a, fx_inv.a, fx_inv.d))
    assert_subtype(
        fx_inv.callable_var_arg(0, fx_inv.a, fx_inv.d),
        fx_inv.callable_var_arg(0, fx_inv.b, fx_inv.b, fx_inv.d))


def test_var_arg_callable_subtyping_9(fx_inv) -> None:
    assert_not_subtype(
        fx_inv.callable_var_arg(0, fx_inv.b, fx_inv.b, fx_inv.d),
        fx_inv.callable_var_arg(0, fx_inv.a, fx_inv.d))
    assert_subtype(
        fx_inv.callable_var_arg(0, fx_inv.a, fx_inv.a, fx_inv.d),
        fx_inv.callable_var_arg(0, fx_inv.b, fx_inv.d))


def test_type_callable_subtyping(fx_inv) -> None:
    assert_subtype(
        fx_inv.callable_type(fx_inv.d, fx_inv.a), fx_inv.type_type)

    assert_strict_subtype(
        fx_inv.callable_type(fx_inv.d, fx_inv.b),
        fx_inv.callable(fx_inv.d, fx_inv.a))

    assert_strict_subtype(fx_inv.callable_type(fx_inv.a, fx_inv.b),
                               fx_inv.callable(fx_inv.a, fx_inv.b))

# IDEA: Maybe add these test cases (they are tested pretty well in type
#       checker tests already):
#  * more interface subtyping test cases
#  * more generic interface subtyping test cases
#  * type variables
#  * tuple types
#  * None type
#  * any type
#  * generic function types


def assert_subtype(s: Type, t: Type) -> None:
    assert_true(is_subtype(s, t), '{} not subtype of {}'.format(s, t))


def assert_not_subtype(s: Type, t: Type) -> None:
    assert_true(not is_subtype(s, t), '{} subtype of {}'.format(s, t))


def assert_strict_subtype(s: Type, t: Type) -> None:
    assert_subtype(s, t)
    assert_not_subtype(t, s)


def assert_equivalent(s: Type, t: Type) -> None:
    assert_subtype(s, t)
    assert_subtype(t, s)


def assert_unrelated(s: Type, t: Type) -> None:
    assert_not_subtype(s, t)
    assert_not_subtype(t, s)
