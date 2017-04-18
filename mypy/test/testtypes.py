"""Test cases for mypy types and type operations."""

from typing import List, Tuple

import pytest  # type: ignore

from mypy.erasetype import erase_type
from mypy.expandtype import expand_type
from mypy.join import join_types, join_simple
from mypy.meet import meet_types
from mypy.nodes import ARG_POS, ARG_OPT, ARG_STAR
from mypy.subtypes import is_subtype, is_more_precise, is_proper_subtype
from mypy.types import (
    UnboundType, AnyType, CallableType, TupleType, TypeVarDef, Type,
    Instance, NoneTyp, Overloaded, TypeType, UnionType, UninhabitedType,
    true_only, false_only, TypeVarId,
)
from mypy.unit.helpers import (
    assert_equal, assert_true, assert_false, assert_type,
)
from mypy.unit.typefixture import InterfaceTypeFixture


class TypesSuite:
    def test_any(self) -> None:
        assert_equal(str(AnyType()), 'Any')

    def test_simple_unbound_type(self) -> None:
        u = UnboundType('Foo')
        assert_equal(str(u), 'Foo?')

    def test_generic_unbound_type(self) -> None:
        u = UnboundType('Foo', [UnboundType('T'), AnyType()])
        assert_equal(str(u), 'Foo?[T?, Any]')

    def test_callable_type(self, fx, x, y) -> None:
        c = CallableType([x, y],
                         [ARG_POS, ARG_POS],
                         [None, None],
                         AnyType(), fx.function)
        assert_equal(str(c), 'def (X?, Y?) -> Any')

        c2 = CallableType([], [], [], NoneTyp(), None)
        assert_equal(str(c2), 'def ()')

    def test_callable_type_with_default_args(self, fx, x, y) -> None:
        c = CallableType([x, y], [ARG_POS, ARG_OPT], [None, None],
                         AnyType(), fx.function)
        assert_equal(str(c), 'def (X?, Y? =) -> Any')

        c2 = CallableType([x, y], [ARG_OPT, ARG_OPT], [None, None],
                          AnyType(), fx.function)
        assert_equal(str(c2), 'def (X? =, Y? =) -> Any')

    def test_callable_type_with_var_args(self, fx, x, y) -> None:
        c = CallableType([x], [ARG_STAR], [None], AnyType(), fx.function)
        assert_equal(str(c), 'def (*X?) -> Any')

        c2 = CallableType([x, y], [ARG_POS, ARG_STAR],
                          [None, None], AnyType(), fx.function)
        assert_equal(str(c2), 'def (X?, *Y?) -> Any')

        c3 = CallableType([x, y], [ARG_OPT, ARG_STAR], [None, None],
                          AnyType(), fx.function)
        assert_equal(str(c3), 'def (X? =, *Y?) -> Any')

    def test_tuple_type(self, x) -> None:
        assert_equal(str(TupleType([], None)), 'Tuple[]')
        assert_equal(str(TupleType([x], None)), 'Tuple[X?]')
        assert_equal(str(TupleType([x, AnyType()], None)), 'Tuple[X?, Any]')

    def test_type_variable_binding(self, fx, x, y) -> None:
        assert_equal(str(TypeVarDef('X', 1, None, fx.o)), 'X')
        assert_equal(str(TypeVarDef('X', 1, [x, y], fx.o)),
                     'X in (X?, Y?)')

    def test_generic_function_type(self, fx, x, y) -> None:
        c = CallableType([x, y], [ARG_POS, ARG_POS], [None, None],
                         y, fx.function, name=None,
                         variables=[TypeVarDef('X', -1, None, fx.o)])
        assert_equal(str(c), 'def [X] (X?, Y?) -> Y?')

        v = [TypeVarDef('Y', -1, None, fx.o),
             TypeVarDef('X', -2, None, fx.o)]
        c2 = CallableType([], [], [], NoneTyp(), fx.function, name=None, variables=v)
        assert_equal(str(c2), 'def [Y, X] ()')


class TypeOpsSuite:
    # expand_type

    def test_trivial_expand(self, fx_inv, make_tuple, make_callable) -> None:
        for t in (fx_inv.a, fx_inv.o, fx_inv.t, fx_inv.nonet,
                  make_tuple(fx_inv.a),
                  make_callable(fx_inv.a, fx_inv.a), fx_inv.anyt):
            assert_expand(t, [], t)
            assert_expand(t, [], t)
            assert_expand(t, [], t)

    def test_expand_naked_type_var(self, fx_inv) -> None:
        assert_expand(fx_inv.t, [(fx_inv.t.id, fx_inv.a)], fx_inv.a)
        assert_expand(fx_inv.t, [(fx_inv.s.id, fx_inv.a)], fx_inv.t)

    def test_expand_basic_generic_types(self, fx_inv) -> None:
        assert_expand(fx_inv.gt, [(fx_inv.t.id, fx_inv.a)], fx_inv.ga)

    # IDEA: Add test cases for
    #   tuple types
    #   callable types
    #   multiple arguments

    # erase_type

    def test_trivial_erase(self, fx_inv) -> None:
        for t in (fx_inv.a, fx_inv.o, fx_inv.nonet, fx_inv.anyt):
            assert_erase(t, t)

    def test_erase_with_type_variable(self, fx_inv) -> None:
        assert_erase(fx_inv.t, fx_inv.anyt)

    def test_erase_with_generic_type(self, fx_inv) -> None:
        assert_erase(fx_inv.ga, fx_inv.gdyn)
        assert_erase(fx_inv.hab,
                          Instance(fx_inv.hi, [fx_inv.anyt, fx_inv.anyt]))

    def test_erase_with_tuple_type(self, fx_inv, make_tuple) -> None:
        assert_erase(make_tuple(fx_inv.a), fx_inv.std_tuple)

    def test_erase_with_function_type(self, fx_inv) -> None:
        assert_erase(fx_inv.callable(fx_inv.a, fx_inv.b),
                          fx_inv.callable_type(fx_inv.nonet))

    def test_erase_with_type_object(self, fx_inv) -> None:
        assert_erase(fx_inv.callable_type(fx_inv.a, fx_inv.b),
                          fx_inv.callable_type(fx_inv.nonet))

    def test_erase_with_type_type(self, fx_inv) -> None:
        assert_erase(fx_inv.type_a, fx_inv.type_a)
        assert_erase(fx_inv.type_t, fx_inv.type_any)

    # is_more_precise

    def test_is_more_precise(self, fx_inv, make_tuple) -> None:
        assert_true(is_more_precise(fx_inv.b, fx_inv.a))
        assert_true(is_more_precise(fx_inv.b, fx_inv.b))
        assert_true(is_more_precise(fx_inv.b, fx_inv.b))
        assert_true(is_more_precise(fx_inv.b, fx_inv.anyt))
        assert_true(is_more_precise(make_tuple(fx_inv.b, fx_inv.a),
                                    make_tuple(fx_inv.b, fx_inv.a)))

        assert_false(is_more_precise(fx_inv.a, fx_inv.b))
        assert_false(is_more_precise(fx_inv.anyt, fx_inv.b))
        assert_false(is_more_precise(make_tuple(fx_inv.b, fx_inv.b),
                                     make_tuple(fx_inv.b, fx_inv.a)))

    # is_proper_subtype

    def test_is_proper_subtype(self, fx_inv) -> None:

        assert_true(is_proper_subtype(fx_inv.a, fx_inv.a))
        assert_true(is_proper_subtype(fx_inv.b, fx_inv.a))
        assert_true(is_proper_subtype(fx_inv.b, fx_inv.o))
        assert_true(is_proper_subtype(fx_inv.b, fx_inv.o))

        assert_false(is_proper_subtype(fx_inv.a, fx_inv.b))
        assert_false(is_proper_subtype(fx_inv.o, fx_inv.b))

        assert_true(is_proper_subtype(fx_inv.anyt, fx_inv.anyt))
        assert_false(is_proper_subtype(fx_inv.a, fx_inv.anyt))
        assert_false(is_proper_subtype(fx_inv.anyt, fx_inv.a))

        assert_true(is_proper_subtype(fx_inv.ga, fx_inv.ga))
        assert_true(is_proper_subtype(fx_inv.gdyn, fx_inv.gdyn))
        assert_false(is_proper_subtype(fx_inv.ga, fx_inv.gdyn))
        assert_false(is_proper_subtype(fx_inv.gdyn, fx_inv.ga))

        assert_true(is_proper_subtype(fx_inv.t, fx_inv.t))
        assert_false(is_proper_subtype(fx_inv.t, fx_inv.s))

        assert_true(is_proper_subtype(fx_inv.a, UnionType([fx_inv.a, fx_inv.b])))
        assert_true(is_proper_subtype(UnionType([fx_inv.a, fx_inv.b]),
                                      UnionType([fx_inv.a, fx_inv.b, fx_inv.c])))
        assert_false(is_proper_subtype(UnionType([fx_inv.a, fx_inv.b]),
                                       UnionType([fx_inv.b, fx_inv.c])))

    def test_is_proper_subtype_covariance(self, fx) -> None:
        assert_true(is_proper_subtype(fx.gsab, fx.gb))
        assert_true(is_proper_subtype(fx.gsab, fx.ga))
        assert_false(is_proper_subtype(fx.gsaa, fx.gb))
        assert_true(is_proper_subtype(fx.gb, fx.ga))
        assert_false(is_proper_subtype(fx.ga, fx.gb))

    def test_is_proper_subtype_contravariance(self, fx_contra) -> None:
        assert_true(is_proper_subtype(fx_contra.gsab, fx_contra.gb))
        assert_false(is_proper_subtype(fx_contra.gsab, fx_contra.ga))
        assert_true(is_proper_subtype(fx_contra.gsaa, fx_contra.gb))
        assert_false(is_proper_subtype(fx_contra.gb, fx_contra.ga))
        assert_true(is_proper_subtype(fx_contra.ga, fx_contra.gb))

    def test_is_proper_subtype_invariance(self, fx_inv) -> None:
        assert_true(is_proper_subtype(fx_inv.gsab, fx_inv.gb))
        assert_false(is_proper_subtype(fx_inv.gsab, fx_inv.ga))
        assert_false(is_proper_subtype(fx_inv.gsaa, fx_inv.gb))
        assert_false(is_proper_subtype(fx_inv.gb, fx_inv.ga))
        assert_false(is_proper_subtype(fx_inv.ga, fx_inv.gb))

    # can_be_true / can_be_false

    def test_empty_tuple_always_false(self, make_tuple) -> None:
        tuple_type = make_tuple()
        assert_true(tuple_type.can_be_false)
        assert_false(tuple_type.can_be_true)

    def test_nonempty_tuple_always_true(self, make_tuple) -> None:
        tuple_type = make_tuple(AnyType(), AnyType())
        assert_true(tuple_type.can_be_true)
        assert_false(tuple_type.can_be_false)

    def test_union_can_be_true_if_any_true(self, fx_inv, make_tuple) -> None:
        union_type = UnionType([fx_inv.a, make_tuple()])
        assert_true(union_type.can_be_true)

    def test_union_can_not_be_true_if_none_true(self, make_tuple) -> None:
        union_type = UnionType([make_tuple(), make_tuple()])
        assert_false(union_type.can_be_true)

    def test_union_can_be_false_if_any_false(self, fx_inv, make_tuple) -> None:
        union_type = UnionType([fx_inv.a, make_tuple()])
        assert_true(union_type.can_be_false)

    def test_union_can_not_be_false_if_none_false(self, fx_inv, make_tuple) -> None:
        union_type = UnionType([make_tuple(fx_inv.a), make_tuple(fx_inv.d)])
        assert_false(union_type.can_be_false)

    # true_only / false_only

    def test_true_only_of_false_type_is_uninhabited(self) -> None:
        to = true_only(NoneTyp())
        assert_type(UninhabitedType, to)

    def test_true_only_of_true_type_is_idempotent(self, make_tuple) -> None:
        always_true = make_tuple(AnyType())
        to = true_only(always_true)
        assert_true(always_true is to)

    def test_true_only_of_instance(self, fx_inv) -> None:
        to = true_only(fx_inv.a)
        assert_equal(str(to), "A")
        assert_true(to.can_be_true)
        assert_false(to.can_be_false)
        assert_type(Instance, to)
        # The original class still can be false
        assert_true(fx_inv.a.can_be_false)

    def test_true_only_of_union(self, fx_inv, make_tuple) -> None:
        tup_type = make_tuple(AnyType())
        # Union of something that is unknown, something that is always true, something
        # that is always false
        union_type = UnionType([fx_inv.a, tup_type, make_tuple()])
        to = true_only(union_type)
        assert isinstance(to, UnionType)
        assert_equal(len(to.items), 2)
        assert_true(to.items[0].can_be_true)
        assert_false(to.items[0].can_be_false)
        assert_true(to.items[1] is tup_type)

    def test_false_only_of_true_type_is_uninhabited(self, make_tuple) -> None:
        fo = false_only(make_tuple(AnyType()))
        assert_type(UninhabitedType, fo)

    def test_false_only_of_false_type_is_idempotent(self) -> None:
        always_false = NoneTyp()
        fo = false_only(always_false)
        assert_true(always_false is fo)

    def test_false_only_of_instance(self, fx_inv) -> None:
        fo = false_only(fx_inv.a)
        assert_equal(str(fo), "A")
        assert_false(fo.can_be_true)
        assert_true(fo.can_be_false)
        assert_type(Instance, fo)
        # The original class still can be true
        assert_true(fx_inv.a.can_be_true)

    def test_false_only_of_union(self, fx_inv, make_tuple) -> None:
        tup_type = make_tuple()
        # Union of something that is unknown, something that is always true, something
        # that is always false
        union_type = UnionType([fx_inv.a, make_tuple(AnyType()), tup_type])
        assert_equal(len(union_type.items), 3)
        fo = false_only(union_type)
        assert isinstance(fo, UnionType)
        assert_equal(len(fo.items), 2)
        assert_false(fo.items[0].can_be_true)
        assert_true(fo.items[0].can_be_false)
        assert_true(fo.items[1] is tup_type)


class JoinSuite:
    def test_trivial_cases(self, fx) -> None:
        for simple in fx.a, fx.o, fx.b:
            assert_join(simple, simple, simple)

    def test_class_subtyping(self, fx) -> None:
        assert_join(fx.a, fx.o, fx.o)
        assert_join(fx.b, fx.o, fx.o)
        assert_join(fx.a, fx.d, fx.o)
        assert_join(fx.b, fx.c, fx.a)
        assert_join(fx.b, fx.d, fx.o)

    def test_tuples(self, fx, make_tuple) -> None:
        assert_join(make_tuple(), make_tuple(), make_tuple())
        assert_join(make_tuple(fx.a),
                         make_tuple(fx.a),
                         make_tuple(fx.a))
        assert_join(make_tuple(fx.b, fx.c),
                         make_tuple(fx.a, fx.d),
                         make_tuple(fx.a, fx.o))

        assert_join(make_tuple(fx.a, fx.a),
                         fx.std_tuple,
                         fx.o)
        assert_join(make_tuple(fx.a),
                         make_tuple(fx.a, fx.a),
                         fx.o)

    def test_function_types(self, fx, make_callable) -> None:
        assert_join(make_callable(fx.a, fx.b),
                         make_callable(fx.a, fx.b),
                         make_callable(fx.a, fx.b))

        assert_join(make_callable(fx.a, fx.b),
                         make_callable(fx.b, fx.b),
                         make_callable(fx.b, fx.b))
        assert_join(make_callable(fx.a, fx.b),
                         make_callable(fx.a, fx.a),
                         make_callable(fx.a, fx.a))
        assert_join(make_callable(fx.a, fx.b),
                         fx.function,
                         fx.function)
        assert_join(make_callable(fx.a, fx.b),
                         make_callable(fx.d, fx.b),
                         fx.function)

    def test_type_vars(self, fx) -> None:
        assert_join(fx.t, fx.t, fx.t)
        assert_join(fx.s, fx.s, fx.s)
        assert_join(fx.t, fx.s, fx.o)

    def test_none(self, fx, make_tuple, make_callable) -> None:
        # Any type t joined with None results in t.
        for t in [NoneTyp(), fx.a, fx.o, UnboundType('x'),
                  fx.t, make_tuple(),
                  make_callable(fx.a, fx.b), fx.anyt]:
            assert_join(t, NoneTyp(), t)

    def test_unbound_type(self, fx, make_tuple, make_callable) -> None:
        assert_join(UnboundType('x'), UnboundType('x'), fx.anyt)
        assert_join(UnboundType('x'), UnboundType('y'), fx.anyt)

        # Any type t joined with an unbound type results in dynamic. Unbound
        # type means that there is an error somewhere in the program, so this
        # does not affect type safety (whatever the result).
        for t in [fx.a, fx.o, fx.ga, fx.t, make_tuple(),
                  make_callable(fx.a, fx.b)]:
            assert_join(t, UnboundType('X'), fx.anyt)

    def test_any_type(self, fx, make_tuple, make_callable) -> None:
        # Join against 'Any' type always results in 'Any'.
        for t in [fx.anyt, fx.a, fx.o, NoneTyp(),
                  UnboundType('x'), fx.t, make_tuple(),
                  make_callable(fx.a, fx.b)]:
            assert_join(t, fx.anyt, fx.anyt)

    def test_mixed_truth_restricted_type_simple(self, fx) -> None:
        # join_simple against differently restricted truthiness types drops restrictions.
        true_a = true_only(fx.a)
        false_o = false_only(fx.o)
        j = join_simple(fx.o, true_a, false_o)
        assert_true(j.can_be_true)
        assert_true(j.can_be_false)

    def test_mixed_truth_restricted_type(self, fx) -> None:
        # join_types against differently restricted truthiness types drops restrictions.
        true_any = true_only(AnyType())
        false_o = false_only(fx.o)
        j = join_types(true_any, false_o)
        assert_true(j.can_be_true)
        assert_true(j.can_be_false)

    def test_other_mixed_types(self, fx, make_tuple, make_callable) -> None:
        # In general, joining unrelated types produces object.
        for t1 in [fx.a, fx.t, make_tuple(),
                   make_callable(fx.a, fx.b)]:
            for t2 in [fx.a, fx.t, make_tuple(),
                       make_callable(fx.a, fx.b)]:
                if str(t1) != str(t2):
                    assert_join(t1, t2, fx.o)

    def test_simple_generics(self, fx, make_tuple, make_callable) -> None:
        assert_join(fx.ga, fx.ga, fx.ga)
        assert_join(fx.ga, fx.gb, fx.ga)
        assert_join(fx.ga, fx.gd, fx.o)
        assert_join(fx.ga, fx.g2a, fx.o)

        assert_join(fx.ga, fx.nonet, fx.ga)
        assert_join(fx.ga, fx.anyt, fx.anyt)

        for t in [fx.a, fx.o, fx.t, make_tuple(),
                  make_callable(fx.a, fx.b)]:
            assert_join(t, fx.ga, fx.o)

    def test_generics_with_multiple_args(self, fx) -> None:
        assert_join(fx.hab, fx.hab, fx.hab)
        assert_join(fx.hab, fx.hbb, fx.hab)
        assert_join(fx.had, fx.haa, fx.o)

    def test_generics_with_inheritance(self, fx) -> None:
        assert_join(fx.gsab, fx.gb, fx.gb)
        assert_join(fx.gsba, fx.gb, fx.ga)
        assert_join(fx.gsab, fx.gd, fx.o)

    def test_generics_with_inheritance_and_shared_supertype(self, fx) -> None:
        assert_join(fx.gsba, fx.gs2a, fx.ga)
        assert_join(fx.gsab, fx.gs2a, fx.ga)
        assert_join(fx.gsab, fx.gs2d, fx.o)

    def test_generic_types_and_any(self, fx) -> None:
        assert_join(fx.gdyn, fx.ga, fx.gdyn)

    def test_callables_with_any(self, fx, make_callable) -> None:
        assert_join(make_callable(fx.a, fx.a, fx.anyt, fx.a),
                         make_callable(fx.a, fx.anyt, fx.a, fx.anyt),
                         make_callable(fx.a, fx.anyt, fx.anyt, fx.anyt))

    def test_overloaded(self, fx, make_callable) -> None:
        c = make_callable

        def ov(*items: CallableType) -> Overloaded:
            return Overloaded(list(items))

        func = fx.function
        c1 = c(fx.a, fx.a)
        c2 = c(fx.b, fx.b)
        c3 = c(fx.c, fx.c)
        assert_join(ov(c1, c2), c1, c1)
        assert_join(ov(c1, c2), c2, c2)
        assert_join(ov(c1, c2), ov(c1, c2), ov(c1, c2))
        assert_join(ov(c1, c2), ov(c1, c3), c1)
        assert_join(ov(c2, c1), ov(c3, c1), c1)
        assert_join(ov(c1, c2), c3, func)

    def test_overloaded_with_any(self, fx, make_callable) -> None:
        c = make_callable

        def ov(*items: CallableType) -> Overloaded:
            return Overloaded(list(items))

        any = fx.anyt
        assert_join(ov(c(fx.a, fx.a), c(fx.b, fx.b)), c(any, fx.b), c(any, fx.b))
        assert_join(ov(c(fx.a, fx.a), c(any, fx.b)), c(fx.b, fx.b), c(any, fx.b))

    @pytest.mark.skip(reason="TODO")
    def test_join_interface_types(self, fx) -> None:
        assert_join(fx.f, fx.f, fx.f)
        assert_join(fx.f, fx.f2, fx.o)
        assert_join(fx.f, fx.f3, fx.f)

    @pytest.mark.skip(reason="TODO")
    def test_join_interface_and_class_types(self, fx) -> None:
        assert_join(fx.o, fx.f, fx.o)
        assert_join(fx.a, fx.f, fx.o)

        assert_join(fx.e, fx.f, fx.f)

    @pytest.mark.skip(reason="TODO")
    def test_join_class_types_with_interface_result(self, fx) -> None:
        # Unique result
        assert_join(fx.e, fx.e2, fx.f)

        # Ambiguous result
        assert_join(fx.e2, fx.e3, fx.anyt)

    @pytest.mark.skip(reason="TODO")
    def test_generic_interfaces(self) -> None:
        fx = InterfaceTypeFixture()

        assert_join(fx.gfa, fx.gfa, fx.gfa)
        assert_join(fx.gfa, fx.gfb, fx.o)

        assert_join(fx.m1, fx.gfa, fx.gfa)

        assert_join(fx.m1, fx.gfb, fx.o)

    def test_simple_type_objects(self, fx, make_type_callable) -> None:
        t1 = make_type_callable(fx.a, fx.a)
        t2 = make_type_callable(fx.b, fx.b)
        tr = make_type_callable(fx.b, fx.a)

        assert_join(t1, t1, t1)
        j = join_types(t1, t1)
        assert isinstance(j, CallableType)
        assert_true(j.is_type_obj())

        assert_join(t1, t2, tr)
        assert_join(t1, fx.type_type, fx.type_type)
        assert_join(fx.type_type, fx.type_type,
                         fx.type_type)

    def test_type_type(self, fx) -> None:
        assert_join(fx.type_a, fx.type_b, fx.type_a)
        assert_join(fx.type_b, fx.type_any, fx.type_any)
        assert_join(fx.type_b, fx.type_type, fx.type_type)
        assert_join(fx.type_b, fx.type_c, fx.type_a)
        assert_join(fx.type_c, fx.type_d, TypeType(fx.o))
        assert_join(fx.type_type, fx.type_any, fx.type_type)
        assert_join(fx.type_b, fx.anyt, fx.anyt)

    # There are additional test cases in check-inference.test.

    # TODO: Function types + varargs and default args.


class MeetSuite:
    def test_trivial_cases(self, fx) -> None:
        for simple in fx.a, fx.o, fx.b:
            assert_meet(simple, simple, simple)

    def test_class_subtyping(self, fx) -> None:
        assert_meet(fx.a, fx.o, fx.a)
        assert_meet(fx.a, fx.b, fx.b)
        assert_meet(fx.b, fx.o, fx.b)
        assert_meet(fx.a, fx.d, NoneTyp())
        assert_meet(fx.b, fx.c, NoneTyp())

    def test_tuples(self, fx, make_tuple) -> None:
        assert_meet(make_tuple(), make_tuple(), make_tuple())
        assert_meet(make_tuple(fx.a),
                         make_tuple(fx.a),
                         make_tuple(fx.a))
        assert_meet(make_tuple(fx.b, fx.c),
                         make_tuple(fx.a, fx.d),
                         make_tuple(fx.b, NoneTyp()))

        assert_meet(make_tuple(fx.a, fx.a),
                         fx.std_tuple,
                         make_tuple(fx.a, fx.a))
        assert_meet(make_tuple(fx.a),
                         make_tuple(fx.a, fx.a),
                         NoneTyp())

    def test_function_types(self, fx, make_callable) -> None:
        assert_meet(make_callable(fx.a, fx.b),
                         make_callable(fx.a, fx.b),
                         make_callable(fx.a, fx.b))

        assert_meet(make_callable(fx.a, fx.b),
                         make_callable(fx.b, fx.b),
                         make_callable(fx.a, fx.b))
        assert_meet(make_callable(fx.a, fx.b),
                         make_callable(fx.a, fx.a),
                         make_callable(fx.a, fx.b))

    def test_type_vars(self, fx) -> None:
        assert_meet(fx.t, fx.t, fx.t)
        assert_meet(fx.s, fx.s, fx.s)
        assert_meet(fx.t, fx.s, NoneTyp())

    def test_none(self, fx, make_tuple, make_callable) -> None:
        assert_meet(NoneTyp(), NoneTyp(), NoneTyp())

        assert_meet(NoneTyp(), fx.anyt, NoneTyp())

        # Any type t joined with None results in None, unless t is Any.
        for t in [fx.a, fx.o, UnboundType('x'), fx.t,
                  make_tuple(), make_callable(fx.a, fx.b)]:
            assert_meet(t, NoneTyp(), NoneTyp())

    def test_unbound_type(self, fx, make_tuple, make_callable) -> None:
        assert_meet(UnboundType('x'), UnboundType('x'), fx.anyt)
        assert_meet(UnboundType('x'), UnboundType('y'), fx.anyt)

        assert_meet(UnboundType('x'), fx.anyt, UnboundType('x'))

        # The meet of any type t with an unbound type results in dynamic.
        # Unbound type means that there is an error somewhere in the program,
        # so this does not affect type safety.
        for t in [fx.a, fx.o, fx.t, make_tuple(),
                  make_callable(fx.a, fx.b)]:
            assert_meet(t, UnboundType('X'), fx.anyt)

    def test_dynamic_type(self, fx, make_tuple, make_callable) -> None:
        # Meet against dynamic type always results in dynamic.
        for t in [fx.anyt, fx.a, fx.o, NoneTyp(),
                  UnboundType('x'), fx.t, make_tuple(),
                  make_callable(fx.a, fx.b)]:
            assert_meet(t, fx.anyt, t)

    def test_simple_generics(self, fx, make_tuple, make_callable) -> None:
        assert_meet(fx.ga, fx.ga, fx.ga)
        assert_meet(fx.ga, fx.o, fx.ga)
        assert_meet(fx.ga, fx.gb, fx.gb)
        assert_meet(fx.ga, fx.gd, fx.nonet)
        assert_meet(fx.ga, fx.g2a, fx.nonet)

        assert_meet(fx.ga, fx.nonet, fx.nonet)
        assert_meet(fx.ga, fx.anyt, fx.ga)

        for t in [fx.a, fx.t, make_tuple(),
                  make_callable(fx.a, fx.b)]:
            assert_meet(t, fx.ga, fx.nonet)

    def test_generics_with_multiple_args(self, fx) -> None:
        assert_meet(fx.hab, fx.hab, fx.hab)
        assert_meet(fx.hab, fx.haa, fx.hab)
        assert_meet(fx.hab, fx.had, fx.nonet)
        assert_meet(fx.hab, fx.hbb, fx.hbb)

    def test_generics_with_inheritance(self, fx) -> None:
        assert_meet(fx.gsab, fx.gb, fx.gsab)
        assert_meet(fx.gsba, fx.gb, fx.nonet)

    def test_generics_with_inheritance_and_shared_supertype(self, fx) -> None:
        assert_meet(fx.gsba, fx.gs2a, fx.nonet)
        assert_meet(fx.gsab, fx.gs2a, fx.nonet)

    def test_generic_types_and_dynamic(self, fx) -> None:
        assert_meet(fx.gdyn, fx.ga, fx.ga)

    def test_callables_with_dynamic(self, fx, make_callable) -> None:
        assert_meet(make_callable(fx.a, fx.a, fx.anyt,
                                       fx.a),
                         make_callable(fx.a, fx.anyt, fx.a,
                                       fx.anyt),
                         make_callable(fx.a, fx.anyt, fx.anyt,
                                       fx.anyt))

    def test_meet_interface_types(self, fx) -> None:
        assert_meet(fx.f, fx.f, fx.f)
        assert_meet(fx.f, fx.f2, fx.nonet)
        assert_meet(fx.f, fx.f3, fx.f3)

    def test_meet_interface_and_class_types(self, fx) -> None:
        assert_meet(fx.o, fx.f, fx.f)
        assert_meet(fx.a, fx.f, fx.nonet)

        assert_meet(fx.e, fx.f, fx.e)

    def test_meet_class_types_with_shared_interfaces(self, fx) -> None:
        # These have nothing special with respect to meets, unlike joins. These
        # are for completeness only.
        assert_meet(fx.e, fx.e2, fx.nonet)
        assert_meet(fx.e2, fx.e3, fx.nonet)

    @pytest.mark.skip(reason="TODO")
    def test_meet_with_generic_interfaces(self) -> None:
        fx = InterfaceTypeFixture()
        assert_meet(fx.gfa, fx.m1, fx.m1)
        assert_meet(fx.gfa, fx.gfa, fx.gfa)
        assert_meet(fx.gfb, fx.m1, fx.nonet)

    def test_type_type(self, fx) -> None:
        assert_meet(fx.type_a, fx.type_b, fx.type_b)
        assert_meet(fx.type_b, fx.type_any, fx.type_b)
        assert_meet(fx.type_b, fx.type_type, fx.type_b)
        assert_meet(fx.type_b, fx.type_c, fx.nonet)
        assert_meet(fx.type_c, fx.type_d, fx.nonet)
        assert_meet(fx.type_type, fx.type_any, fx.type_any)
        assert_meet(fx.type_b, fx.anyt, fx.type_b)

    # FIX generic interfaces + ranges


def assert_erase(orig: Type, result: Type) -> None:
    assert_equal(str(erase_type(orig)), str(result))


def assert_expand(orig: Type,
                  map_items: List[Tuple[TypeVarId, Type]],
                  result: Type,
                  ) -> None:
    lower_bounds = {}

    for id, t in map_items:
        lower_bounds[id] = t

    exp = expand_type(orig, lower_bounds)
    # Remove erased tags (asterisks).
    assert_equal(str(exp).replace('*', ''), str(result))


def assert_meet(s: Type, t: Type, meet: Type) -> None:
    assert_simple_meet(s, t, meet)
    assert_simple_meet(t, s, meet)


def assert_simple_meet(s: Type, t: Type, meet: Type) -> None:
    result = meet_types(s, t)
    actual = str(result)
    expected = str(meet)
    assert_equal(actual, expected,
                 'meet({}, {}) == {{}} ({{}} expected)'.format(s, t))
    assert_true(is_subtype(result, s),
                '{} not subtype of {}'.format(result, s))
    assert_true(is_subtype(result, t),
                '{} not subtype of {}'.format(result, t))


def assert_join(s: Type, t: Type, join: Type) -> None:
    assert_simple_join(s, t, join)
    assert_simple_join(t, s, join)


def assert_simple_join(s: Type, t: Type, join: Type) -> None:
    result = join_types(s, t)
    actual = str(result)
    expected = str(join)
    assert_equal(actual, expected,
                 'join({}, {}) == {{}} ({{}} expected)'.format(s, t))
    assert_true(is_subtype(s, result),
                '{} not subtype of {}'.format(s, result))
    assert_true(is_subtype(t, result),
                '{} not subtype of {}'.format(t, result))
