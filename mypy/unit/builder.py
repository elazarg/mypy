
from mypy import build
from mypy.build import BuildResult, BuildSource
from mypy.unit.config import test_temp_dir
from mypy.errors import CompileError
from mypy.options import Options


def perform_build(source: str) -> BuildResult:
    options = Options()
    options.use_builtins_fixtures = True
    options.show_traceback = True
    try:
        result = build.build(sources=[BuildSource('main', None, source)],
                             options=options,
                             alt_lib_path=test_temp_dir)
    except CompileError as e:
        # TODO: We need a manager and a graph in this case as well
        assert False, str('\n'.join(e.messages))
    return result
