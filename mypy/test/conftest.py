from typing import List

from mypy.nodes import INVARIANT, CONTRAVARIANT, ARG_POS
from mypy.typefixture import TypeFixture
from mypy.types import UnboundType, TupleType, TypeVarDef, CallableType, Type

import pytest  # type: ignore

pytest_plugins = [
    'mypy.unit.data',
]


@pytest.fixture
def x() -> UnboundType:
    return UnboundType('X')


@pytest.fixture
def y() -> UnboundType:
    return UnboundType('Y')


@pytest.fixture
def fx() -> TypeFixture:
    return TypeFixture()


@pytest.fixture
def fx_inv() -> TypeFixture:
    return TypeFixture(INVARIANT)


@pytest.fixture
def fx_contra() -> TypeFixture:
    return TypeFixture(CONTRAVARIANT)


@pytest.fixture
def make_tuple(fx: TypeFixture):
    def make(*a: Type) -> TupleType:
        return TupleType(list(a), fx.std_tuple)
    return make


@pytest.fixture
def make_callable(fx: TypeFixture):
    """callable(args, a1, ..., an, r) constructs a callable with
    argument types a1, ... an and return type r and type arguments
    vars.
    """
    def make(*a: Type, vars: List[str] = (), fallback=fx.function):
        tv = [TypeVarDef(v, -n, None, fx.o)
              for n, v in enumerate(vars)]
        return CallableType(list(a[:-1]),
                            [ARG_POS] * (len(a) - 1),
                            [None] * (len(a) - 1),
                            a[-1],
                            fallback,
                            name=None,
                            variables=tv)
    return make


@pytest.fixture
def make_type_callable(make_callable, fx):
    def make(*a: Type) -> CallableType:
        """type_callable(a1, ..., an, r) constructs a callable with
        argument types a1, ... an and return type r, and which
        represents a type.
        """
        return make_callable(*a, fallback=fx.type_type)
    return make
