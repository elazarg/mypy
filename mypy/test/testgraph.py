"""Test cases for graph processing code in build.py."""

from typing import AbstractSet, Dict, Set, List

from mypy.build import (
    BuildManager, State, BuildSourceSet,
    topsort, strongly_connected_components, sorted_components, order_ascc,
)
from mypy.options import Options
from mypy.report import Reports
from mypy.unit.helpers import assert_equal
from mypy.version import __version__


def test_topsort() -> None:
    a = frozenset({'A'})
    b = frozenset({'B'})
    c = frozenset({'C'})
    d = frozenset({'D'})
    data = {a: {b, c}, b: {d}, c: {d}}  # type: Dict[AbstractSet[str], Set[AbstractSet[str]]]
    res = list(topsort(data))
    assert_equal(res, [{d}, {b, c}, {a}])


def test_scc() -> None:
    vertices = {'A', 'B', 'C', 'D'}
    edges = {'A': ['B', 'C'],
             'B': ['C'],
             'C': ['B', 'D'],
             'D': []}  # type: Dict[str, List[str]]
    sccs = set(frozenset(x) for x in strongly_connected_components(vertices, edges))
    assert_equal(sccs,
                 {frozenset({'A'}),
                  frozenset({'B', 'C'}),
                  frozenset({'D'})})


def _make_manager() -> BuildManager:
    manager = BuildManager(
        data_dir='',
        lib_path=[],
        ignore_prefix='',
        source_set=BuildSourceSet([]),
        reports=Reports('', {}),
        options=Options(),
        version_id=__version__,
    )
    return manager


def test_sorted_components() -> None:
    manager = _make_manager()
    graph = {'a': State('a', None, 'import b, c', manager),
             'd': State('d', None, 'pass', manager),
             'b': State('b', None, 'import c', manager),
             'c': State('c', None, 'import b, d', manager),
             }
    res = sorted_components(graph)
    assert_equal(res, [frozenset({'d'}), frozenset({'c', 'b'}), frozenset({'a'})])


def test_order_ascc() -> None:
    manager = _make_manager()
    graph = {'a': State('a', None, 'import b, c', manager),
             'd': State('d', None, 'def f(): import a', manager),
             'b': State('b', None, 'import c', manager),
             'c': State('c', None, 'import b, d', manager),
             }
    res = sorted_components(graph)
    assert_equal(res, [frozenset({'a', 'd', 'c', 'b'})])
    ascc = res[0]
    scc = order_ascc(graph, ascc)
    assert_equal(scc, ['d', 'c', 'b', 'a'])
