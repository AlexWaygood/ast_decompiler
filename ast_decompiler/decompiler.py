"""

Implementation of the decompiler class.

"""
import ast
from contextlib import contextmanager

_OP_TO_STR = {
    ast.Add: '+',
    ast.Sub: '-',
    ast.Mult: '*',
    ast.Div: '/',
    ast.Mod: '%',
    ast.Pow: '**',
    ast.LShift: '<<',
    ast.RShift: '>>',
    ast.BitOr: '|',
    ast.BitXor: '^',
    ast.BitAnd: '&',
    ast.FloorDiv: '//',
    ast.Invert: '~',
    ast.Not: 'not ',
    ast.UAdd: '+',
    ast.USub: '-',
    ast.Eq: '==',
    ast.NotEq: '!=',
    ast.Lt: '<',
    ast.LtE: '<=',
    ast.Gt: '>',
    ast.GtE: '>=',
    ast.Is: 'is',
    ast.IsNot: 'is not',
    ast.In: 'in',
    ast.NotIn: 'not in',
    ast.And: 'and',
    ast.Or: 'or',
}


class _CallArgs(object):
    """Used as an entry in the precedence table.

    Needed to convey the high precedence of the callee but low precedence of the arguments.

    """

_PRECEDENCE = {
    _CallArgs: -1,
    ast.Or: 0,
    ast.And: 1,
    ast.Not: 2,
    ast.Compare: 3,
    ast.BitOr: 4,
    ast.BitXor: 5,
    ast.BitAnd: 6,
    ast.LShift: 7,
    ast.RShift: 7,
    ast.Add: 8,
    ast.Sub: 8,
    ast.Mult: 9,
    ast.Div: 9,
    ast.FloorDiv: 9,
    ast.Mod: 9,
    ast.UAdd: 10,
    ast.USub: 10,
    ast.Invert: 10,
    ast.Pow: 11,
    ast.Subscript: 12,
    ast.Call: 12,
    ast.Attribute: 12,
}


def decompile(ast, indentation=4, line_length=100):
    """Decompiles an AST into Python code.

    Arguments:
    - ast: code to decompile, using AST objects as generated by the standard library ast module
    - indentation: indentation level of lines
    - line_length: if lines become longer than this length, ast_decompiler will try to break them up
      (but it will not necessarily succeed in all cases)

    """
    decompiler = Decompiler(indentation=indentation, line_length=line_length)
    decompiler.visit(ast)
    return ''.join(decompiler.lines)


class Decompiler(ast.NodeVisitor):
    def __init__(self, indentation, line_length):
        self.lines = []
        self.current_line = []
        self.current_indentation = 0
        self.node_stack = []
        self.indentation = indentation
        self.max_line_length = line_length
        self.has_unicode_literals = False

    def visit(self, node):
        self.node_stack.append(node)
        try:
            return super(Decompiler, self).visit(node)
        finally:
            self.node_stack.pop()

    def precedence_of_node(self, node):
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.BoolOp)):
            return _PRECEDENCE[type(node.op)]
        return _PRECEDENCE.get(type(node), -1)

    def get_parent_node(self):
        try:
            return self.node_stack[-2]
        except IndexError:
            return None

    def write(self, code):
        assert isinstance(code, basestring), 'invalid code %r' % code
        self.current_line.append(code)

    def write_indentation(self):
        self.write(' ' * self.current_indentation)

    def write_newline(self):
        line = ''.join(self.current_line) + '\n'
        self.lines.append(line)
        self.current_line = []

    def current_line_length(self):
        return sum(map(len, self.current_line))

    def write_expression_list(self, nodes, separator=', ', allow_newlines=True, need_parens=True,
                              final_separator_if_multiline=True):
        """Writes a list of nodes, separated by separator.

        If allow_newlines, will write the expression over multiple lines if necessary to say within
        max_line_length. If need_parens, will surround the expression with parentheses in this case.
        If final_separator_if_multiline, will write a separator at the end of the list if it is
        divided over multiple lines.

        """
        first = True
        last_line = len(self.lines)
        current_line = list(self.current_line)
        for node in nodes:
            if first:
                first = False
            else:
                self.write(separator)
            self.visit(node)
            if allow_newlines and self.current_line_length() > self.max_line_length:
                break
        else:
            return  # stayed within the limit

        # reset state
        del self.lines[last_line:]
        self.current_line = current_line

        separator = separator.rstrip()
        if need_parens:
            self.write('(')
        self.write_newline()
        with self.add_indentation():
            num_nodes = len(nodes)
            for i, node in enumerate(nodes):
                self.write_indentation()
                self.visit(node)
                if final_separator_if_multiline or i < num_nodes - 1:
                    self.write(separator)
                self.write_newline()

        self.write_indentation()
        if need_parens:
            self.write(')')

    def write_suite(self, nodes):
        with self.add_indentation():
            for line in nodes:
                self.visit(line)

    @contextmanager
    def add_indentation(self):
        self.current_indentation += self.indentation
        try:
            yield
        finally:
            self.current_indentation -= self.indentation

    @contextmanager
    def parenthesize_if(self, condition):
        if condition:
            self.write('(')
            yield
            self.write(')')
        else:
            yield

    def generic_visit(self, node):
        raise NotImplementedError('missing visit method for %r' % node)

    def visit_Module(self, node):
        for line in node.body:
            self.visit(line)

    visit_Interactive = visit_Module

    def visit_Expression(self, node):
        self.visit(node.body)

    # Multi-line statements

    def visit_FunctionDef(self, node):
        self.write_newline()
        for decorator in node.decorator_list:
            self.write_indentation()
            self.write('@')
            self.visit(decorator)
            self.write_newline()

        self.write_indentation()
        self.write('def %s(' % node.name)
        self.visit(node.args)
        self.write('):')
        self.write_newline()

        self.write_suite(node.body)

    def visit_ClassDef(self, node):
        self.write_newline()
        self.write_newline()
        for decorator in node.decorator_list:
            self.write_indentation()
            self.write('@')
            self.visit(decorator)
            self.write_newline()

        self.write_indentation()
        self.write('class %s(' % node.name)
        self.write_expression_list(node.bases, need_parens=False)
        self.write('):')
        self.write_newline()
        self.write_suite(node.body)

    def visit_For(self, node):
        self.write_indentation()
        self.write('for ')
        self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        self.write(':')
        self.write_newline()
        self.write_suite(node.body)
        self.write_else(node.orelse)

    def visit_While(self, node):
        self.write_indentation()
        self.write('while ')
        self.visit(node.test)
        self.write(':')
        self.write_newline()
        self.write_suite(node.body)
        self.write_else(node.orelse)

    def visit_If(self, node):
        self.write_indentation()
        self.write('if ')
        self.visit(node.test)
        self.write(':')
        self.write_newline()
        self.write_suite(node.body)
        while node.orelse and len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            node = node.orelse[0]
            self.write_indentation()
            self.write('elif ')
            self.visit(node.test)
            self.write(':')
            self.write_newline()
            self.write_suite(node.body)
        self.write_else(node.orelse)

    def write_else(self, orelse):
        if orelse:
            self.write_indentation()
            self.write('else:')
            self.write_newline()
            self.write_suite(orelse)

    def visit_With(self, node):
        self.write_indentation()
        self.write('with ')
        nodes = [node]
        body = node.body
        is_first = True

        while len(body) == 1 and isinstance(body[0], ast.With):
            nodes.append(body[0])
            body = body[0].body

        for context_node in nodes:
            if is_first:
                is_first = False
            else:
                self.write(', ')
            self.visit(context_node.context_expr)
            if context_node.optional_vars:
                self.write(' as ')
                self.visit(context_node.optional_vars)
        self.write(':')
        self.write_newline()
        self.write_suite(body)

    def visit_TryExcept(self, node):
        self.write_indentation()
        self.write('try:')
        self.write_newline()
        self.write_suite(node.body)
        for handler in node.handlers:
            self.visit(handler)
        self.write_else(node.orelse)

    def visit_TryFinally(self, node):
        if len(node.body) == 1 and isinstance(node.body[0], ast.TryExcept):
            self.visit(node.body[0])
        else:
            self.write_indentation()
            self.write('try:')
            self.write_newline()
            self.write_suite(node.body)
        self.write_indentation()
        self.write('finally:')
        self.write_newline()
        self.write_suite(node.finalbody)

    # One-line statements

    def visit_Return(self, node):
        self.write_indentation()
        self.write('return')
        if node.value:
            self.write(' ')
            self.visit(node.value)
        self.write_newline()

    def visit_Delete(self, node):
        self.write_indentation()
        self.write('del ')
        self.write_expression_list(node.targets)
        self.write_newline()

    def visit_Assign(self, node):
        self.write_indentation()
        self.write_expression_list(node.targets, separator=' = ')
        self.write(' = ')
        self.visit(node.value)
        self.write_newline()

    def visit_AugAssign(self, node):
        self.write_indentation()
        self.visit(node.target)
        self.write(' ')
        self.visit(node.op)
        self.write('= ')
        self.visit(node.value)
        self.write_newline()

    def visit_Print(self, node):
        self.write_indentation()
        self.write('print')
        if node.dest:
            self.write(' >>')
            self.visit(node.dest)
            if node.values:
                self.write(',')
        if node.values:
            self.write(' ')
        self.write_expression_list(node.values, allow_newlines=False)
        if not node.nl:
            self.write(',')
        self.write_newline()

    def visit_Raise(self, node):
        self.write_indentation()
        self.write('raise')
        expressions = [child for child in (node.type, node.inst, node.tback) if child]
        if expressions:
            self.write(' ')
            self.write_expression_list(expressions, allow_newlines=False)
        self.write_newline()

    def visit_Assert(self, node):
        self.write_indentation()
        self.write('assert ')
        self.visit(node.test)
        if node.msg:
            self.write(', ')
            self.visit(node.msg)
        self.write_newline()

    def visit_Import(self, node):
        self.write_indentation()
        self.write('import ')
        self.write_expression_list(node.names)
        self.write_newline()

    def visit_ImportFrom(self, node):
        if (
            node.module == '__future__' and
            any(alias.name == 'unicode_literals' for alias in node.names)
        ):
            self.has_unicode_literals = True

        self.write_indentation()
        self.write('from %s' % ('.' * (node.level or 0)))
        if node.module:
            self.write(node.module)
        self.write(' import ')
        self.write_expression_list(node.names)
        self.write_newline()

    def visit_Exec(self, node):
        self.write_indentation()
        self.write('exec ')
        self.visit(node.body)
        if node.globals:
            self.write(' in ')
            self.visit(node.globals)
        if node.locals:
            self.write(', ')
            self.visit(node.locals)
        self.write_newline()

    def visit_Global(self, node):
        self.write_indentation()
        self.write('global ')
        self.write_expression_list([ast.Name(id=name) for name in node.names])
        self.write_newline()

    def visit_Expr(self, node):
        self.write_indentation()
        self.visit(node.value)
        self.write_newline()

    def visit_Pass(self, node):
        self.write_indentation()
        self.write('pass')
        self.write_newline()

    def visit_Break(self, node):
        self.write_indentation()
        self.write('break')
        self.write_newline()

    def visit_Continue(self, node):
        self.write_indentation()
        self.write('continue')
        self.write_newline()

    # Expressions

    def visit_BoolOp(self, node):
        my_prec = self.precedence_of_node(node)
        parent_prec = self.precedence_of_node(self.get_parent_node())
        with self.parenthesize_if(my_prec <= parent_prec):
            op = 'and' if isinstance(node.op, ast.And) else 'or'
            self.write_expression_list(
                node.values,
                separator=' %s ' % op,
                final_separator_if_multiline=False,
            )

    def visit_BinOp(self, node):
        parent_node = self.get_parent_node()
        my_prec = self.precedence_of_node(node)
        parent_prec = self.precedence_of_node(parent_node)
        if my_prec < parent_prec:
            should_parenthesize = True
        elif my_prec == parent_prec:
            if isinstance(node.op, ast.Pow):
                should_parenthesize = node == parent_node.left
            else:
                should_parenthesize = node == parent_node.right
        else:
            should_parenthesize = False

        with self.parenthesize_if(should_parenthesize):
            self.visit(node.left)
            self.write(' ')
            self.visit(node.op)
            self.write(' ')
            self.visit(node.right)

    def visit_UnaryOp(self, node):
        my_prec = self.precedence_of_node(node)
        parent_prec = self.precedence_of_node(self.get_parent_node())
        with self.parenthesize_if(my_prec < parent_prec):
            self.visit(node.op)
            self.visit(node.operand)

    def visit_Lambda(self, node):
        should_parenthesize = isinstance(
            self.get_parent_node(),
            (ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.Attribute, ast.Subscript, ast.Call)
        )
        with self.parenthesize_if(should_parenthesize):
            self.write('lambda')
            if node.args.args or node.args.vararg or node.args.kwarg:
                self.write(' ')
            self.visit(node.args)
            self.write(': ')
            self.visit(node.body)

    def visit_IfExp(self, node):
        parent_node = self.get_parent_node()
        if isinstance(parent_node,
                      (ast.BinOp, ast.UnaryOp, ast.Compare, ast.Attribute, ast.Subscript,
                       ast.Call)):
            should_parenthesize = True
        elif isinstance(parent_node, ast.IfExp) and \
                (node is parent_node.test or node is parent_node.body):
            should_parenthesize = True
        else:
            should_parenthesize = False

        with self.parenthesize_if(should_parenthesize):
            self.visit(node.body)
            self.write(' if ')
            self.visit(node.test)
            self.write(' else ')
            self.visit(node.orelse)

    def visit_Dict(self, node):
        self.write('{')
        items = [KeyValuePair(key, value) for key, value in zip(node.keys, node.values)]
        self.write_expression_list(items, need_parens=False)
        self.write('}')

    def visit_KeyValuePair(self, node):
        self.visit(node.key)
        self.write(': ')
        self.visit(node.value)

    def visit_Set(self, node):
        self.write('{')
        self.write_expression_list(node.elts, need_parens=False)
        self.write('}')

    def visit_ListComp(self, node):
        self.visit_comp(node, '[', ']')

    def visit_SetComp(self, node):
        self.visit_comp(node, '{', '}')

    def visit_DictComp(self, node):
        self.write('{')
        elts = [KeyValuePair(node.key, node.value)] + node.generators
        self.write_expression_list(elts, separator=' ', need_parens=False)
        self.write('}')

    def visit_GeneratorExp(self, node):
        self.visit_comp(node, '(', ')')

    def visit_comp(self, node, start, end):
        self.write(start)
        self.write_expression_list([node.elt] + node.generators, separator=' ', need_parens=False)
        self.write(end)

    def visit_Yield(self, node):
        with self.parenthesize_if(
                not isinstance(self.get_parent_node(), (ast.Expr, ast.Assign, ast.AugAssign))):
            self.write('yield')
            if node.value:
                self.write(' ')
                self.visit(node.value)

    def visit_Compare(self, node):
        my_prec = self.precedence_of_node(node)
        parent_prec = self.precedence_of_node(self.get_parent_node())
        with self.parenthesize_if(my_prec <= parent_prec):
            self.visit(node.left)
            for op, expr in zip(node.ops, node.comparators):
                self.write(' ')
                self.visit(op)
                self.write(' ')
                self.visit(expr)

    def visit_Call(self, node):
        self.visit(node.func)
        self.write('(')

        self.node_stack.append(_CallArgs())
        try:
            args = node.args + node.keywords
            if node.starargs:
                args.append(StarArg(node.starargs))
            if node.kwargs:
                args.append(DoubleStarArg(node.kwargs))

            if args:
                self.write_expression_list(
                    args,
                    need_parens=False,
                    final_separator_if_multiline=False  # it's illegal after *args and **kwargs
                )

            self.write(')')
        finally:
            self.node_stack.pop()

    def visit_StarArg(self, node):
        self.write('*')
        self.visit(node.arg)

    def visit_DoubleStarArg(self, node):
        self.write('**')
        self.visit(node.arg)

    def visit_KeywordArg(self, node):
        self.visit(node.arg)
        self.write('=')
        self.visit(node.value)

    def visit_Repr(self, node):
        self.write('`')
        self.visit(node.value)
        self.write('`')

    def visit_Num(self, node):
        self.write(repr(node.n))

    def visit_Str(self, node):
        if self.has_unicode_literals and isinstance(node.s, str):
            self.write('b')
        self.write(repr(node.s))

    def visit_Attribute(self, node):
        self.visit(node.value)
        self.write('.%s' % node.attr)

    def visit_Subscript(self, node):
        self.visit(node.value)
        self.write('[')
        self.visit(node.slice)
        self.write(']')

    def visit_Name(self, node):
        self.write(node.id)

    def visit_List(self, node):
        self.write('[')
        self.write_expression_list(node.elts, need_parens=False)
        self.write(']')

    def visit_Tuple(self, node):
        if not node.elts:
            self.write('()')
        else:
            should_parenthesize = not isinstance(
                self.get_parent_node(),
                (ast.Expr, ast.Assign, ast.AugAssign, ast.Return, ast.Yield)
            )
            with self.parenthesize_if(should_parenthesize):
                if len(node.elts) == 1:
                    self.visit(node.elts[0])
                    self.write(',')
                else:
                    self.write_expression_list(node.elts, need_parens=not should_parenthesize)

    # slice

    def visit_Ellipsis(self, node):
        self.write('Ellipsis')

    def visit_Slice(self, node):
        if node.lower:
            self.visit(node.lower)
        self.write(':')
        if node.upper:
            self.visit(node.upper)
        if node.step:
            self.write(':')
            self.visit(node.step)

    def visit_ExtSlice(self, node):
        self.write_expression_list(node.dims, need_parens=False)

    def visit_Index(self, node):
        self.visit(node.value)

    # operators
    for op, string in _OP_TO_STR.items():
        exec('def visit_%s(self, node): self.write(%r)' % (op.__name__, string))

    # Other types

    visit_Load = visit_Store = visit_Del = visit_AugLoad = visit_AugStore = visit_Param = \
        lambda self, node: None

    def visit_comprehension(self, node):
        self.write('for ')
        self.visit(node.target)
        self.write(' in ')
        self.visit(node.iter)
        for expr in node.ifs:
            self.write(' if ')
            self.visit(expr)

    def visit_ExceptHandler(self, node):
        self.write_indentation()
        self.write('except')
        if node.type:
            self.write(' ')
            self.visit(node.type)
            if node.name:
                self.write(' as ')
                self.visit(node.name)
        self.write(':')
        self.write_newline()
        self.write_suite(node.body)

    def visit_arguments(self, node):
        num_defaults = len(node.defaults)
        if num_defaults:
            args = node.args[:-num_defaults]
            default_args = zip(node.args[-num_defaults:], node.defaults)
        else:
            args = list(node.args)
            default_args = []

        for name, value in default_args:
            args.append(KeywordArg(name, value))
        if node.vararg:
            args.append(StarArg(ast.Name(id=node.vararg)))
        if node.kwarg:
            args.append(DoubleStarArg(ast.Name(id=node.kwarg)))

        if args:
            # lambdas can't have a multiline arglist
            allow_newlines = not isinstance(self.get_parent_node(), ast.Lambda)
            self.write_expression_list(
                args,
                allow_newlines=allow_newlines,
                need_parens=False,
                final_separator_if_multiline=False  # illegal after **kwargs
            )

    def visit_keyword(self, node):
        self.write(node.arg + '=')
        self.visit(node.value)

    def visit_alias(self, node):
        self.write(node.name)
        if node.asname is not None:
            self.write(' as %s' % node.asname)


# helper ast nodes to make decompilation easier
class KeyValuePair(object):
    """A key-value pair as used in a dictionary display."""
    _fields = ['key', 'value']

    def __init__(self, key, value):
        self.key = key
        self.value = value


class StarArg(object):
    """A * argument."""
    _fields = ['arg']

    def __init__(self, arg):
        self.arg = arg


class DoubleStarArg(object):
    """A ** argument."""
    _fields = ['arg']

    def __init__(self, arg):
        self.arg = arg


class KeywordArg(object):
    """A x=3 keyword argument in a function definition."""
    _fields = ['arg', 'value']

    def __init__(self, arg, value):
        self.arg = arg
        self.value = value
