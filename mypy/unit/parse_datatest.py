import re
from typing import List, Tuple, Set, Optional, Iterator, NamedTuple


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
