"""Test cases for running mypy programs using a Python interpreter.

Each test case type checks a program then runs it using Python. The
output (stdout) of the program is compared to expected output. Type checking
uses full builtins and other stubs.

Note: Currently Python interpreter paths are hard coded.

Note: These test cases are *not* included in the main test suite, as including
      this suite would slow down the main suite too much.
"""

import os
import os.path
import re
import subprocess
import sys

from typing import Dict, List, Tuple

from mypy.util import try_find_python2_interpreter

from mypy.unit.config import test_temp_dir
from mypy.unit.helpers import SkipTestCaseException, assert_string_arrays_equal
from mypy.unit.data import MypyDataItem


# Path to Python 3 interpreter
python3_path = sys.executable
program_re = re.compile(r'\b_program.py\b')


class PythonEvaluationSuite(MypyDataItem):
    # Files which contain test case descriptions.
    files = ['pythoneval.test',
             'python2eval.test']
    optional_out = True

    def run_case(self) -> None:
        """Runs Mypy in a subprocess.

        If this passes without errors, executes the script again with a given Python
        version.
        """
        mypy_cmdline = [
            python3_path,
            os.path.join(self.old_cwd, 'scripts', 'mypy'),
            '--show-traceback',
        ]
        py2 = self.name.lower().endswith('python2')
        if py2:
            mypy_cmdline.append('--py2')
            interpreter = try_find_python2_interpreter()
            if not interpreter:
                # Skip, can't find a Python 2 interpreter.
                raise SkipTestCaseException()
        else:
            interpreter = python3_path

        # Write the program to a file.
        program = '_' + self.name + '.py'
        mypy_cmdline.append(program)
        program_path = os.path.join(test_temp_dir, program)
        with open(program_path, 'w') as file:
            for s in self.input:
                file.write('{}\n'.format(s))
        # Type check the program.
        # This uses the same PYTHONPATH as the current process.
        returncode, out = run(mypy_cmdline)
        if returncode == 0:
            # Set up module path for the execution.
            # This needs the typing module but *not* the mypy module.
            vers_dir = '2.7' if py2 else '3.2'
            typing_path = os.path.join(self.old_cwd, 'lib-typing', vers_dir)
            assert os.path.isdir(typing_path)
            env = os.environ.copy()
            env['PYTHONPATH'] = typing_path
            returncode, interp_out = run([interpreter, program], env=env)
            out += interp_out
        # Remove temp file.
        os.remove(program_path)
        assert_string_arrays_equal(self.adapt_output(), out,
                                   'Invalid output ({}, line {})'.format(
                                       self.file, self.line))

    def adapt_output(self) -> List[str]:
        """Translates the generic _program.py into the actual filename."""
        program = '_' + self.name + '.py'
        return [program_re.sub(program, line) for line in self.output]


def split_lines(*streams: bytes) -> List[str]:
    """Returns a single list of string lines from the byte streams in args."""
    return [
        s.rstrip('\n\r')
        for stream in streams
        for s in str(stream, 'utf8').splitlines()
    ]


def run(
    cmdline: List[str], *, env: Dict[str, str] = None, timeout: int = 30
) -> Tuple[int, List[str]]:
    """A poor man's subprocess.run() for 3.3 and 3.4 compatibility."""
    process = subprocess.Popen(
        cmdline,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=test_temp_dir,
    )
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        out = err = b''
        process.kill()
    return process.returncode, split_lines(out, err)
