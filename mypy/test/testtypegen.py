"""Test cases for the type checker: exporting inferred types"""

import os.path
import re

from typing import Set, List

from mypy.nodes import (
    NameExpr, TypeVarExpr, CallExpr, Expression, MypyFile, AssignmentStmt, IntExpr,
)
from mypy.traverser import TraverserVisitor
from mypy.util import short_type

from mypy.unit.data import DataSuite, parse_test_cases, DataDrivenTestCase
from mypy.unit import config
from mypy.unit.builder import perform_build


# List of files that contain test case descriptions.
files = ['typexport-basic.test']


class TypeExportSuite(DataSuite):
    @classmethod
    def cases(cls) -> List[DataDrivenTestCase]:
        c = []  # type: List[DataDrivenTestCase]
        for f in files:
            c += parse_test_cases(os.path.join(config.test_data_prefix, f),
                                  None, config.test_temp_dir)
        return c

    def run_case(self, testcase: DataDrivenTestCase) -> None:
        line = testcase.input[0]
        mask = ''
        if line.startswith('##'):
            mask = '(' + line[2:].strip() + ')$'
        result = perform_build('\n'.join(testcase.input))
        a, map = result.errors, result.types
        nodes = map.keys()

        # Ignore NameExpr nodes of variables with explicit (trivial) types
        # to simplify output.
        searcher = SkippedNodeSearcher()
        for file in result.files.values():
            file.accept(searcher)
        ignored = searcher.nodes

        # Filter nodes that should be included in the output.
        keys = []
        for node in nodes:
            if node.line is not None and node.line != -1 and map[node]:
                if ignore_node(node) or node in ignored:
                    continue
                if (re.match(mask, short_type(node))
                        or (isinstance(node, NameExpr)
                            and re.match(mask, node.name))):
                    # Include node in output.
                    keys.append(node)

        for key in sorted(keys,
                          key=lambda n: (n.line, short_type(n),
                                         str(n) + str(map[n]))):
            ts = str(map[key]).replace('*', '')  # Remove erased tags
            ts = ts.replace('__main__.', '')
            a.append('{}({}) : {}'.format(short_type(key), key.line, ts))


class SkippedNodeSearcher(TraverserVisitor):
    def __init__(self) -> None:
        self.nodes = set()  # type: Set[Expression]
        self.is_typing = False

    def visit_mypy_file(self, f: MypyFile) -> None:
        self.is_typing = f.fullname() == 'typing' or f.fullname() == 'builtins'
        super().visit_mypy_file(f)

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        if s.type or ignore_node(s.rvalue):
            for lvalue in s.lvalues:
                if isinstance(lvalue, NameExpr):
                    self.nodes.add(lvalue)
        super().visit_assignment_stmt(s)

    def visit_name_expr(self, n: NameExpr) -> None:
        self.skip_if_typing(n)

    def visit_int_expr(self, n: IntExpr) -> None:
        self.skip_if_typing(n)

    def skip_if_typing(self, n: Expression) -> None:
        if self.is_typing:
            self.nodes.add(n)


def ignore_node(node: Expression) -> bool:
    """Return True if node is to be omitted from test case output."""

    # We want to get rid of object() expressions in the typing module stub
    # and also TypeVar(...) expressions. Since detecting whether a node comes
    # from the typing module is not easy, we just to strip them all away.
    if isinstance(node, TypeVarExpr):
        return True
    if isinstance(node, NameExpr) and node.fullname == 'builtins.object':
        return True
    if isinstance(node, NameExpr) and node.fullname == 'builtins.None':
        return True
    if isinstance(node, CallExpr) and (ignore_node(node.callee) or
                                       node.analyzed):
        return True

    return False
