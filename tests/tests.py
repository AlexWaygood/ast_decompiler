"""

Helpers for tests.

"""

import ast
from ast_decompiler import decompile
import difflib


def check(code):
    """Checks that the code remains the same when decompiled and re-parsed."""
    tree = ast.parse(code)
    new_code = decompile(tree)
    try:
        new_tree = ast.parse(new_code)
    except SyntaxError as e:
        print '>>> syntax error:'
        lineno = e.lineno - 1
        min_lineno = max(0, lineno - 3)
        max_lineno = lineno + 3
        for line in new_code.splitlines()[min_lineno:max_lineno]:
            print line
        raise

    dumped = ast.dump(ast.parse(code))
    new_dumped = ast.dump(new_tree)

    if dumped != new_dumped:
        print code
        print new_code
        for line in difflib.unified_diff(dumped.split(), new_dumped.split()):
            print line
        assert False, '%s != %s' % (dumped, new_dumped)


def assert_decompiles(code, result, do_check=True, **kwargs):
    """Asserts that code, when parsed, decompiles into result."""
    decompile_result = decompile(ast.parse(code), **kwargs)
    if do_check:
        check(decompile_result)
    if result != decompile_result:
        print '>>> expected'
        print result
        print '>>> actual'
        print decompile_result
        print '>>> diff'
        for line in difflib.unified_diff(result.splitlines(), decompile_result.splitlines()):
            print line
        assert False, 'failed to decompile %s' % code