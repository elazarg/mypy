import re
from typing import List, Tuple, Set, Optional, Iterator, NamedTuple
from collections import OrderedDict

"""Parsed test caseitem.

An item is of the form
  [id arg]
  .. data ..
"""
TestItem = NamedTuple('TestItem', [
    ('id', str),
    ('arg', Optional[str]),
    ('data', List[str]),
    ('line', int),
    ('lastline', int),
])


def find_test_cases(text: str):
    text = re.sub(r'^\[out1?\]', '[out pre]', text, flags=re.MULTILINE)
    text = re.sub(r'^\[out2\]', '[out post]', text, flags=re.MULTILINE)
    text = re.sub(r'^--.*?$', '', text, flags=re.MULTILINE)
    items = re.split(r'^\[([a-zA-Z0-9_]*)\s+(\S*?)\]\s*$', text, flags=re.MULTILINE)[1:]
    from itertools import groupby
    c = 0

    def next_case(x: Tuple[str, str, str]):
        nonlocal c
        if x[0] == 'case':
            c += 1
        return c
    return groupby([(items[j], items[j+1], items[j+2]) for j in range(0, len(items), 3)],
                   key=next_case)


def parse_test_items(text):
    flagsline = ''
    if text.strip().startswith('#'):
        flagsline, text = text.split('\n', maxsplit=1)
        '^# flags: {args}'
        '^# flags2: {args}'
        '^# cmd: {args}'

    pat = '|'.join([
        '^[headerid {modid_list}]'
        '^[rechecked {modid_list}]'
        '^[builtins {path}]'
        '^[builtins_py2 {path}]'
        '^[outfile path]'
        '^[file {path}]'
        '^[out]'
        '^[out1]'
        '^[out2]'
    ])
    pat_as_regex = re.escape(pat).replace(' ', r'\s+').format(
        args=r'.*?',
        modid_list='.*?',
        path='.*?'
    )
    res = re.split(r'\[case\s*([a-zA-Z0-9_]*)(-skip)?\s*\]', text)[1:]
    return [(res[i], res[i+1], res[i+2]) for i in range(0, len(res), 3)]


def strip_list(l: List[str]) -> List[str]:
    """Return a stripped copy of l.

    Strip whitespace at the end of all lines, and strip all empty
    lines from the end of the array.
    """

    r = []  # type: List[str]
    for s in l:
        # Strip spaces at end of line
        r.append(re.sub(r'\s+$', '', s))

    while len(r) > 0 and r[-1] == '':
        r.pop()

    return r


def collapse_line_continuation(l: List[str]) -> List[str]:
    r = []  # type: List[str]
    cont = False
    for s in l:
        ss = re.sub(r'\\$', '', s)
        if cont:
            r[-1] += re.sub('^ +', '', ss)
        else:
            r.append(ss)
        cont = s.endswith('\\')
    return r


def parse_test_data(l: List[str]) -> Iterator[TestItem]:
    """Parse a list of lines that represent a sequence of test items."""

    data = []  # type: List[str]

    id = None  # type: Optional[str]
    arg = None  # type: Optional[str]

    i = 0
    i0 = 0
    while i < len(l):
        s = l[i].strip()

        if l[i].startswith('[') and s.endswith(']') and not s.startswith('[['):
            if id:
                data = collapse_line_continuation(data)
                data = strip_list(data)
                yield TestItem(id, arg, strip_list(data), i0 + 1, i)
            i0 = i
            id = s[1:-1]
            arg = None
            if ' ' in id:
                arg = id[id.index(' ') + 1:]
                id = id[:id.index(' ')]
            data = []
        elif l[i].startswith('[['):
            data.append(l[i][1:])
        elif not l[i].startswith('--'):
            data.append(l[i])
        elif l[i].startswith('----'):
            data.append(l[i][2:])
        i += 1

    # Process the last item.
    if id:
        data = collapse_line_continuation(data)
        data = strip_list(data)
        yield TestItem(id, arg, data, i0 + 1, i)


TestCaseData = NamedTuple('TestCaseData', [
    ('skip', bool),
    ('line', int),
    ('lastline', int),
    ('input', List[str]),
    ('output', List[str]),
    ('output2', List[str]),
    ('files', List[str]),
    ('output_files', List[Tuple[str, str]]),
    ('expected_stale_modules', Optional[Set[str]]),
    ('expected_rechecked_modules', Optional[Set[str]])
])


def parse_test_cases(p: List[TestItem]) -> Tuple[str, Iterator[TestCaseData]]:
    """Parse a file with test case descriptions.

    Return an array of test cases.
    """
    # Process the parsed items. Each item has a header of form [id args],
    # optionally followed by lines of text.
    i = 0
    while i < len(p):
        ok = False
        if p[i].id == 'case':
            input = p[i].data
            name, is_skip, startline = p[i].arg, p[i].arg.endswith('-skip'), p[i].line
            i += 1

            inline_files = []  # type: List[Tuple[str, str]] # path and contents
            files = []  # type: List[str] # path
            output_files = []  # type: List[Tuple[str, str]] # path and contents for output files
            tcout = []  # type: List[str]  # Regular output errors
            tcout2 = []  # type: List[str]  # Output errors for incremental, second run
            stale_modules = None  # type: Optional[Set[str]]  # module names
            rechecked_modules = None  # type: Optional[Set[str]]  # module names
            while i < len(p) and p[i].id != 'case':
                if p[i].id == 'file' or p[i].id == 'outfile':
                    # Record an extra file needed for the test case.
                    arg = p[i].arg
                    assert arg is not None
                    file_entry = (arg, '\n'.join(p[i].data))
                    if p[i].id == 'file':
                        inline_files.append(file_entry)
                    elif p[i].id == 'outfile':
                        output_files.append(file_entry)
                elif p[i].id in ('builtins', 'builtins_py2'):
                    # Use a custom source file for the std module.
                    arg = p[i].arg
                    assert arg is not None
                    files.append(arg)
                elif p[i].id == 'stale':
                    arg = p[i].arg
                    if arg is None:
                        stale_modules = set()
                    else:
                        stale_modules = {item.strip() for item in arg.split(',')}
                elif p[i].id == 'rechecked':
                    arg = p[i].arg
                    if arg is None:
                        rechecked_modules = set()
                    else:
                        rechecked_modules.update(item.strip() for item in arg.split(','))
                elif p[i].id == 'out' or p[i].id == 'out1':
                    tcout = p[i].data
                    ok = True
                elif p[i].id == 'out2':
                    tcout2 = p[i].data
                    ok = True
                else:
                    return 'Invalid section header {} at line {}'.format(p[i].id, p[i].line)
                i += 1

            if rechecked_modules is None:
                # If the set of rechecked modules isn't specified, make it the same as the set of
                # modules with a stale public interface.
                rechecked_modules = stale_modules
            if (stale_modules is not None
                    and rechecked_modules is not None
                    and not stale_modules.issubset(rechecked_modules)):
                return 'Stale modules must be a subset of rechecked modules'

            if ok:
                lastline = p[i].line if i < len(p) else p[i - 1].line + 9999
                yield (name, TestCaseData(is_skip, startline, lastline, input,
                                               tcout, tcout2,
                                               files, output_files, stale_modules,
                                               rechecked_modules))
        if not ok:
            return 'line {}: Error in test case description'.format(startline)


def main():
    import sys
    with open(sys.argv[1], encoding='utf-8') as f:
        l = f.readlines()
    ls = list(parse_test_data(l))
    for t in ls:
        print(t)
    for n, v in OrderedDict(parse_test_cases(ls)).items():
        print(n, ':', v)


if __name__ == '__main__':
    import sys

    with open(sys.argv[1], encoding='utf-8') as f:
        for i, t in find_test_cases(f.read()):
            print(i, list(t))
