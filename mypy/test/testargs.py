"""Ensure the argparse parser and Options class are in sync.

In particular, verify that the argparse defaults are the same as the Options
defaults, and that argparse doesn't assign any new members to the Options
object it creates.
"""

from mypy.test.helpers import assert_equal
from mypy.options import Options
from mypy.main import process_options


def test_coherence() -> None:
    options = Options()
    _, parsed_options = process_options([], require_targets=False)
    assert_equal(options, parsed_options)
