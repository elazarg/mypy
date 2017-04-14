"""Test cases for reports generated by mypy."""
import textwrap

from mypy.myunit import Suite
from mypy.test.helpers import assert_equal
from mypy.report import CoberturaPackage, get_line_rate

import lxml.etree as etree


class CoberturaReportSuite(Suite):
    def test_get_line_rate(self) -> None:
        assert_equal('1.0', get_line_rate(0, 0))
        assert_equal('0.3333', get_line_rate(1, 3))

    def test_as_xml(self) -> None:
        cobertura_package = CoberturaPackage('foobar')
        cobertura_package.covered_lines = 21
        cobertura_package.total_lines = 42

        child_package = CoberturaPackage('raz')
        child_package.covered_lines = 10
        child_package.total_lines = 10
        child_package.classes['class'] = etree.Element('class')

        cobertura_package.packages['raz'] = child_package

        expected_output = textwrap.dedent('''\
            <package complexity="1.0" name="foobar" branch-rate="0" line-rate="0.5000">
              <classes/>
              <packages>
                <package complexity="1.0" name="raz" branch-rate="0" line-rate="1.0000">
                  <classes>
                    <class/>
                  </classes>
                </package>
              </packages>
            </package>
        ''').encode('ascii')
        assert_equal(expected_output,
                     etree.tostring(cobertura_package.as_xml(), pretty_print=True))
