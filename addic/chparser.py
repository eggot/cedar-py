import lexer
import typing
import utils
from dataclasses import dataclass, field

def expected(exp, act):
    if exp != act.type:
        line, col = act.location
        print("%s:%s: Error: expected %s; got %s" % (line, col, exp.name, act.type.name))

class AstNode(utils.Locatable):
    @classmethod
    def at(cls, location, *args, **kwargs):
        n = cls(*args, **kwargs)
        n.location = location
        n.ty = None
        return n


class TypeExpr(AstNode):
    pass

class Decl(AstNode):
    pass

class Stmt(AstNode):
    pass

class Expr(AstNode):
    type = field(compare=False, repr=False, init=False)

@dataclass
class ImportDecl(Decl):
    filename: str

@dataclass
class FailureDecl(Decl):
    name: str
    fieldtypes: list
    fieldnames: list
    exported: bool

@dataclass
class TypeDecl(Decl):
    name: str
    ctors: list # list of TypeCtor
    exported: bool

@dataclass
class TypeCtor(AstNode):
    name: str
    fieldtypes: list
    fieldnames: list
    tag: Expr

@dataclass # int, MyType
class TypeRef(TypeExpr):
    name: str

@dataclass # foo.mytype
class QualifiedTypeRef(TypeExpr):
    module: str
    name: str

@dataclass # int*
class PointerType(TypeExpr):
    ty: TypeExpr

@dataclass # const int, int const
class ConstType(TypeExpr):
    ty: TypeExpr

@dataclass # int[]
class ArraySliceType(TypeExpr):
    ty: TypeExpr

@dataclass # int[7]
class ArrayType(TypeExpr):
    ty: TypeExpr
    size: int

@dataclass
class OptionalType(TypeExpr):
    ty: TypeExpr

@dataclass
class FailableType(TypeExpr):
    ty: TypeExpr

@dataclass
class FunctionDecl(Decl):
    rettype: TypeExpr
    name: str
    argtypes: typing.List[TypeExpr]
    argnames: typing.List[str]
    body: Stmt # or None if it's a declaration without body
    exported: bool
    varargs: bool

@dataclass
class BlockStmt(Expr):
    stmts: typing.List[Stmt]

@dataclass
class ReturnStmt(Stmt):
    expr: Expr

@dataclass
class ExprStmt(Stmt):
    expr: Expr

@dataclass
class AssertStmt(Stmt):
    expr: Expr

@dataclass
class BoolExpr(Expr):
    value: bool

@dataclass
class IntegerExpr(Expr):
    num: int

@dataclass
class StringExpr(Expr):
    string: str

@dataclass
class NullExpr(Expr):
    pass

@dataclass
class IdentExpr(Expr):
    name: str

@dataclass
class LabelledExpr(Expr):
    name: str
    expr: Expr

@dataclass
class CallExpr(Expr):
    func: Expr
    args: list # of expr
    names: list # of str or None if argument was not named

@dataclass
class CtorExpr(Expr):
    typename: str
    args: typing.List[Expr]
    named_args: typing.Dict[str, Expr]

@dataclass
class InitExpr(Expr):
    elems: list

@dataclass
class WhereExpr(Expr):
    expr: Expr
    body: Stmt

@dataclass
class SwitchExpr(Expr):
    cond: Expr
    cases: typing.List[Expr]
    bodies: typing.List[Expr]

@dataclass
class IfExpr(Expr):
    cond: Expr
    ontrue: Expr
    onfalse: Expr

@dataclass
class IfStmt(Stmt):
    cond: Expr
    ontrue: Stmt
    onfalse: Stmt

@dataclass
class TrailingElse(Expr):
    expr: Expr
    stmt: Stmt

@dataclass
class UnaryExpr(Expr):
    op: str
    expr: Expr

@dataclass
class BinaryExpr(Expr):
    op: str
    lhs: Expr
    rhs: Expr

@dataclass
class IndexExpr(Expr):
    array: Expr
    index: Expr

@dataclass
class MemberExpr(Expr):
    struct: Expr
    field: str
    auto_deref: bool = field(compare=False, repr=False, init=False)

@dataclass
class TypeMemberExpr(Expr):
    typename: str
    member: str

@dataclass
class VarDecl(Stmt):
    decltype: TypeExpr
    name: str
    expr: Expr

@dataclass
class AssignStmt(Expr):
    lhs: Expr
    rhs: Expr

DECLS = None
def parse_file(text):
    decls = []
    global DECLS
    DECLS = decls
    tokbuf = _TokenBuffer(lexer.Lexer(text))
    while not tokbuf.peek(lexer.T_FILEEND):
        decls.append(_parse_decl(tokbuf))
    return decls

PRECEDENCE_TABLE = {
    lexer.T_ELSE: 10,

    lexer.T_STAR: 9,
    lexer.T_SLASH: 9,
    lexer.T_PERCENT: 9,

    lexer.T_PLUS: 8,
    lexer.T_MINUS: 8,

    lexer.T_LSHIFT: 7,
    lexer.T_RSHIFT: 7,

    lexer.T_AMPERSAND: 6,

    lexer.T_CIRCUMFLEX: 5,

    lexer.T_PIPE: 4,

    lexer.T_LT: 3,
    lexer.T_LE: 3,
    lexer.T_GE: 3,
    lexer.T_GT: 3,

    lexer.T_EQ: 2,
    lexer.T_NE: 2,

    lexer.T_AND: 1,

    lexer.T_OR: 0,
}
precedence_of = PRECEDENCE_TABLE.__getitem__

def is_binary_operator(toktype, else_binop):
    if toktype == lexer.T_ELSE and not else_binop:
        return False
    return toktype in PRECEDENCE_TABLE



class _TokenBuffer:
    def __init__(self, token_generator):
        self._tokens = token_generator
        self._peekd = [self._tokens.next()]
        self._last = None
        self._stack = []

    def push(self):
        self._stack.append((self._peekd.copy(), self._last, self._tokens.copy()))

    def pop(self):
        self._peekd, self._last, self._tokens = self._stack.pop()
    
    def drop(self):
        self._stack.pop()

    def peek(self, toktype):
        return self._peekd[-1].type == toktype
    
    def peek_token(self):
        return self._peekd[-1]

    def type(self):
        return self._peekd[-1].type

    def take(self, toktype=None):
        if toktype is not None:
            expected(toktype, self._peekd[-1])
            assert self._peekd[-1].type == toktype, self._peekd[-1]
        self._last = self._peekd[-1]
        self._peekd.pop()
        if len(self._peekd) == 0:
            self._peekd.append(self._tokens.next())
        return self._last

    def peek2(self, toktype0, toktype1):
        while len(self._peekd) < 2:
            self._peekd.insert(0, self._tokens.next())
        t1, t0 = self._peekd # yes, this is the right order
        return t0.type == toktype0 and t1.type == toktype1

    def location(self):
        return self._peekd[-1].location

    def takeif(self, toktype):
        if self.peek(toktype):
            self.take(toktype)
            return True
        return False

    def lastwas(self, toktype):
        return self._last is not None and self._last.type == toktype

def _parse_decl(tokbuf):
    exported = tokbuf.takeif(lexer.T_EXPORT)
    if tokbuf.peek(lexer.T_TYPE):
        return _parse_type_decl(tokbuf, exported)
    if tokbuf.peek(lexer.T_FAILURE):
        return _parse_failure_decl(tokbuf, exported)
    elif tokbuf.peek(lexer.T_IMPORT):
        loc = tokbuf.location()
        return ImportDecl.at(loc, tokbuf.take().text)
    else: # Function definition or variable declaration
        rettype = _parse_typeexpr(tokbuf)
        loc = tokbuf.location()
        name = tokbuf.take(lexer.T_IDENT).text
        
        # Function definition or declaration
        if tokbuf.takeif(lexer.T_LPAREN):
            argtypes = []
            argnames = []
            varargs = False
            while not tokbuf.peek(lexer.T_RPAREN):
                if tokbuf.takeif(lexer.T_ELLIPSIS):
                    varargs = True
                    break
                argtypes.append(_parse_typeexpr(tokbuf))
                argnames.append(tokbuf.take(lexer.T_IDENT).text)
                if not tokbuf.takeif(lexer.T_COMMA):
                    break
            tokbuf.take(lexer.T_RPAREN)
            if tokbuf.takeif(lexer.T_SEMICOLON):
                body = None
            else:
                body = _parse_stmt(tokbuf)
            return FunctionDecl.at(loc, rettype, name, argtypes, argnames, body, exported, varargs)
        
        # Variable declaration
        else:
            tokbuf.take(lexer.T_ASSIGN)
            init = _parse_expr(tokbuf)
            tokbuf.take(lexer.T_SEMICOLON)
            return VarDecl.at(loc, rettype, name, init)


def _parse_failure_decl(tokbuf, exported):
    loc = tokbuf.location()
    tokbuf.take(lexer.T_FAILURE)
    
    name = tokbuf.take(lexer.T_IDENT).text
    if tokbuf.takeif(lexer.T_LPAREN):
        fieldtypes = []
        fieldnames = []
        while not tokbuf.peek(lexer.T_RPAREN):
            fieldtypes.append(_parse_typeexpr(tokbuf))
            fieldnames.append(tokbuf.take(lexer.T_IDENT).text)
            if not tokbuf.takeif(lexer.T_COMMA):
                break
        tokbuf.take(lexer.T_RPAREN)
    else:
        fieldnames = []
        fieldtypes = []
    tokbuf.take(lexer.T_SEMICOLON)


    return FailureDecl.at(loc, name, fieldtypes, fieldnames, exported)


def _parse_type_decl(tokbuf, exported):
    loc = tokbuf.location()
    tokbuf.take(lexer.T_TYPE)
    
    # Short form, e.g., type foo(int i);
    if tokbuf.peek2(lexer.T_IDENT, lexer.T_LPAREN):
        name = tokbuf.peek_token().text
        ctor = _parse_type_ctor(tokbuf)
        return TypeDecl.at(loc, name, [ctor], exported)
    # Generic form
    elif tokbuf.peek2(lexer.T_IDENT, lexer.T_LBRACE):
        name = tokbuf.take().text
        tokbuf.take(lexer.T_LBRACE)
        ctors = []
        while not tokbuf.peek(lexer.T_RBRACE):
            ctors.append(_parse_type_ctor(tokbuf))
        tokbuf.take(lexer.T_RBRACE)
        return TypeDecl.at(loc, name, ctors, exported)

def _parse_type_ctor(tokbuf):
    loc = tokbuf.location()
    name = tokbuf.take(lexer.T_IDENT).text
    if tokbuf.takeif(lexer.T_LPAREN):
        fieldtypes = []
        fieldnames = []
        while not tokbuf.peek(lexer.T_RPAREN):
            fieldtypes.append(_parse_typeexpr(tokbuf))
            fieldnames.append(tokbuf.take(lexer.T_IDENT).text)
            if not tokbuf.takeif(lexer.T_COMMA):
                break
        tokbuf.take(lexer.T_RPAREN)
    else:
        fieldtypes = None
        fieldnames = None
    if tokbuf.takeif(lexer.T_ASSIGN):
        tag = _parse_expr(tokbuf);
    else:
        tag = None
    tokbuf.take(lexer.T_SEMICOLON)
    return TypeCtor.at(loc, name, fieldtypes, fieldnames, tag)


def _parse_typeexpr(tokbuf):
    is_const = tokbuf.takeif(lexer.T_CONST)
    ident = tokbuf.take(lexer.T_IDENT).text
    if tokbuf.takeif(lexer.T_DOT):
        ty = QualifiedTypeRef.at(tokbuf.location(), ident, tokbuf.take(lexer.T_IDENT).text)
    else:
        ty = TypeRef.at(tokbuf.location(), ident)
    if is_const:
        ty = ConstType(ty)
    while True:
        if tokbuf.takeif(lexer.T_QUESTION):
            ty = OptionalType(ty)
        elif tokbuf.takeif(lexer.T_EXCLAMATION):
            ty = FailableType(ty)
        elif tokbuf.takeif(lexer.T_STAR):
            ty = PointerType(ty)
        elif tokbuf.takeif(lexer.T_LBRACKET):
            if tokbuf.takeif(lexer.T_RBRACKET):
                ty = ArraySliceType(ty)
            else:
                sz = _parse_expr(tokbuf).num
                ty = ArrayType(ty, sz)
                tokbuf.take(lexer.T_RBRACKET)
        elif tokbuf.takeif(lexer.T_CONST):
            ty = ConstType(ty)
        else:
            break
    return ty

def _parse_stmt_term(tokbuf, eat_semicolor):
    if not tokbuf.lastwas(lexer.T_RBRACE) and eat_semicolor:
        tokbuf.take(lexer.T_SEMICOLON)

def _parse_stmt(tokbuf, eat_semicolor=True):
    loc = tokbuf.location()
    # Return statement
    if tokbuf.takeif(lexer.T_RETURN):
        expr = _parse_expr(tokbuf) if not tokbuf.peek(lexer.T_SEMICOLON) else None
        stmt = ReturnStmt.at(loc, expr)
        _parse_stmt_term(tokbuf, eat_semicolor)

    # Assert
    elif tokbuf.takeif(lexer.T_ASSERT):
        stmt = AssertStmt.at(loc, _parse_expr(tokbuf))
        _parse_stmt_term(tokbuf, eat_semicolor)

    # Block statement
    elif tokbuf.takeif(lexer.T_LBRACE):
        stmts = []
        while not tokbuf.peek(lexer.T_RBRACE):
            stmts.append(_parse_stmt(tokbuf))
        tokbuf.take(lexer.T_RBRACE)
        stmt = BlockStmt.at(loc, stmts)

    # If statement
    elif tokbuf.takeif(lexer.T_IF):
        cond = _parse_expr(tokbuf)
        ontrue = _parse_stmt(tokbuf)
        if tokbuf.peek(lexer.T_ELSE):
            tokbuf.take(lexer.T_ELSE)
            onfalse = _parse_stmt(tokbuf)
        else:
            onfalse = BlockStmt([])
        stmt = IfStmt.at(loc, cond, block_wrap(ontrue), block_wrap(onfalse))

    # Variable declaration
    # This is messy, because we have to undo the parse (the calls to tokbuf.pop())
    # if it turns out that we're not parsing a variable declaration. For example,
    # the statement "int* i();" looks like a variable declaration up until we see
    # the first parenthesis, and at that point we need to abort the parse and try
    # to parse it as an expression instead.
    elif tokbuf.type() in (lexer.T_IDENT, lexer.T_CONST):
        tokbuf.push()
        ty = _parse_typeexpr(tokbuf)
        if not tokbuf.peek(lexer.T_IDENT):
            tokbuf.pop()
            stmt = _parse_stmt_expr(loc, tokbuf)
        else:
            name = tokbuf.take(lexer.T_IDENT)
            if tokbuf.takeif(lexer.T_ASSIGN):
                init = _parse_expr(tokbuf)
                stmt = VarDecl.at(name.location, ty, name.text, init)
                tokbuf.drop()
            elif tokbuf.peek(lexer.T_SEMICOLON):
                init = None
                stmt = VarDecl.at(name.location, ty, name.text, init)
                tokbuf.drop()
            else:
                tokbuf.pop()
                stmt = _parse_stmt_expr(loc, tokbuf)
        _parse_stmt_term(tokbuf, eat_semicolor)

    # Expression statement
    else:
        stmt = _parse_stmt_expr(loc, tokbuf)
        _parse_stmt_term(tokbuf, eat_semicolor)

    return stmt

def _parse_stmt_expr(loc, tokbuf):
    expr = _parse_expr(tokbuf)
    if tokbuf.takeif(lexer.T_ASSIGN):
        rhs = _parse_expr(tokbuf)
        return AssignStmt.at(loc, expr, rhs)
    else:
        return ExprStmt.at(loc, expr)


def _parse_expr(tokbuf, else_binop=True):
    expr = _parse_expr_primary(tokbuf)
    if is_binary_operator(tokbuf.type(), else_binop):
        expr = _parse_expr_binop(tokbuf, expr, 0, else_binop)

    while True:
        loc = tokbuf.location()
        if tokbuf.takeif(lexer.T_WHERE):
            expr = WhereExpr.at(loc, expr, block_wrap(_parse_stmt(tokbuf)))

        elif tokbuf.takeif(lexer.T_ELSE):
            stmt = _parse_stmt(tokbuf, eat_semicolor=False)
            expr = TrailingElse.at(loc, expr,  block_wrap(stmt))
            break

        # If expr
        elif tokbuf.takeif(lexer.T_IF):
            ontrue = expr
            cond = _parse_expr(tokbuf, else_binop=False)
            tokbuf.take(lexer.T_ELSE)
            onfalse = _parse_expr(tokbuf)
            expr = IfExpr.at(loc, cond, ontrue, onfalse)
        else:
            break
    return expr

def _parse_expr_binop(tokbuf, lhs, current_precedence, else_binop):
    if precedence_of(tokbuf.type()) > current_precedence:
        lhs = _parse_expr_binop(tokbuf, lhs, current_precedence + 1, else_binop)

    while is_binary_operator(tokbuf.type(), else_binop) and precedence_of(tokbuf.type()) >= current_precedence:
        if else_binop and (tokbuf.peek2(lexer.T_ELSE, lexer.T_LBRACE) or tokbuf.peek2(lexer.T_ELSE, lexer.T_RETURN) or tokbuf.peek2(lexer.T_ELSE, lexer.T_ASSERT)):
            break

        optok = tokbuf.take();
        rhs = _parse_expr_primary(tokbuf)

        if is_binary_operator(tokbuf.type(), else_binop) and precedence_of(tokbuf.type()) > current_precedence:
            rhs = _parse_expr_binop(tokbuf, rhs, current_precedence + 1, else_binop)
        lhs = BinaryExpr.at(optok.location, optok.text, lhs, rhs)
    return lhs

def block_wrap(ast):
    if type(ast) is not BlockStmt:
        return BlockStmt([ast])
    return ast

def _parse_expr_primary(tokbuf):
    loc = tokbuf.location()
    # Unary minus
    if tokbuf.takeif(lexer.T_MINUS):
        expr = _parse_expr_primary(tokbuf)
        expr = UnaryExpr.at(loc, '-', expr)

    # Pointer dereference
    elif tokbuf.takeif(lexer.T_STAR):
        expr = _parse_expr_primary(tokbuf)
        expr = UnaryExpr.at(loc, '*', expr)

    # Address-of
    elif tokbuf.takeif(lexer.T_AMPERSAND):
        expr = _parse_expr_primary(tokbuf)
        expr = UnaryExpr.at(loc, '&', expr)

    else:
        expr = _parse_expr_atom(tokbuf)

    while True:
        loc = tokbuf.location()

        # Function call
        if tokbuf.takeif(lexer.T_LPAREN):
            args = []
            names = []
            #named_args = {}
            while not tokbuf.peek(lexer.T_RPAREN):
                if tokbuf.peek2(lexer.T_IDENT, lexer.T_COLON):
                    arg_name = tokbuf.take(lexer.T_IDENT).text
                    tokbuf.take(lexer.T_COLON)
                else:
                    arg_name = None
                args.append(_parse_expr(tokbuf))
                names.append(arg_name)
                if not tokbuf.takeif(lexer.T_COMMA):
                    break
            tokbuf.take(lexer.T_RPAREN)
            expr = CallExpr.at(loc, expr, args, names)

        # Array indexing
        elif tokbuf.takeif(lexer.T_LBRACKET):
            idx = _parse_expr(tokbuf)
            tokbuf.take(lexer.T_RBRACKET)
            expr = IndexExpr.at(loc, expr, idx)

        # Member/field access
        elif tokbuf.takeif(lexer.T_DOT):
            name = tokbuf.take(lexer.T_IDENT)
            expr = MemberExpr.at(loc, expr, name.text)

        else:
            break
    return expr


def _parse_expr_atom(tokbuf):
    loc = tokbuf.location()
    # For expression
    if tokbuf.takeif(lexer.T_FOR):
        took_paren = tokbuf.takeif(lexer.T_LPAREN)

        # For-in expression, for x in iterable
        if tokbuf.peek(lexer.T_IDENT) or tokbuf.peek(lexer.T_IDENT):
            ty = _parse_typeexpr(tokbuf) if tokbuf.peek(lexer.T_IDENT) else TypeRef.at(tokbuf.location(), 'auto')
            ident = tokbuf.take(lexer.T_IDENT)
            tokbuf.take(lexer.T_IN)
            iterable = _parse_expr(tokbuf)        
            if took_paren:
                tokbuf.take(lexer.T_RPAREN)
            body = _parse_expr(tokbuf)
            return ForInExpr.at(loc, ty, ident.text, iterable, body)

    # Switch expression
    elif tokbuf.takeif(lexer.T_SWITCH):
        expr = _parse_expr(tokbuf)
        tokbuf.take(lexer.T_LBRACE)

        patterns = []
        bodies = []
        while tokbuf.takeif(lexer.T_CASE):
            patterns.append(_parse_pattern_expr(tokbuf))
            tokbuf.take(lexer.T_COLON)
            bodies.append(_parse_stmt(tokbuf))
        tokbuf.take(lexer.T_RBRACE)
        return SwitchExpr.at(loc, expr, patterns, bodies)

    # While expression
    elif tokbuf.takeif(lexer.T_WHILE):
        cond = _parse_expr(tokbuf)
        body = _parse_expr(tokbuf)
        return WhileExpr.at(loc, cond, body)

    # Null
    elif tokbuf.takeif(lexer.T_NULL):
        return NullExpr.at(loc)

    # Initialization expression
    elif tokbuf.takeif(lexer.T_LBRACE):
        args = []
        while not tokbuf.peek(lexer.T_RBRACE):
            if tokbuf.peek2(lexer.T_IDENT, lexer.T_COLON):
                label = tokbuf.take(lexer.T_IDENT)
                tokbuf.take(lexer.T_COLON)
                args.append(LabelledExpr.at(label.location, label.text, _parse_expr(tokbuf)))
            else:
                args.append(_parse_expr(tokbuf))
            if not tokbuf.takeif(lexer.T_COMMA):
                break
        tokbuf.take(lexer.T_RBRACE)
        return InitExpr.at(loc, args)

    # Parenthesized expression
    elif tokbuf.takeif(lexer.T_LPAREN):
        expr = _parse_expr(tokbuf)
        tokbuf.take(lexer.T_RPAREN)
        return expr

    # Integer expression
    elif tokbuf.peek(lexer.T_INTEGER):
        return IntegerExpr.at(loc, int(tokbuf.take(lexer.T_INTEGER).text))

    # Integer expression
    elif tokbuf.peek(lexer.T_STRING):
        return StringExpr.at(loc, tokbuf.take(lexer.T_STRING).text) 

    # boolean literals
    elif tokbuf.peek(lexer.T_TRUE) or tokbuf.peek(lexer.T_FALSE):
        return BoolExpr.at(loc, tokbuf.take().type == lexer.T_TRUE)

    # Identifier expression
    elif tokbuf.peek(lexer.T_IDENT):
        return IdentExpr.at(loc, tokbuf.take(lexer.T_IDENT).text)


    assert False, tokbuf._peekd


def _parse_pattern_expr(tokbuf):
    loc = tokbuf.location()

    # Type pattern
    if tokbuf.peek2(lexer.T_IDENT, lexer.T_LPAREN):
        typename = tokbuf.take(lexer.T_IDENT).text
        tokbuf.take(lexer.T_LPAREN)
        args = []
        while not tokbuf.peek(lexer.T_RPAREN):
            args.append(_parse_pattern_expr(tokbuf))
            if not tokbuf.takeif(lexer.T_COMMA):
                break
        tokbuf.take(lexer.T_RPAREN)
        return CtorExpr.at(loc, typename, args)

    # Null pattern
    elif tokbuf.takeif(lexer.T_NULL):
        return NullExpr.at(loc)

    # Integer pattern
    elif tokbuf.peek(lexer.T_INTEGER):
        return IntegerExpr.at(loc, int(tokbuf.take(lexer.T_INTEGER).text))

    # boolean pattern
    elif tokbuf.peek(lexer.T_TRUE) or tokbuf.peek(lexer.T_FALSE):
        return BoolExpr.at(loc, tokbuf.take().type == lexer.T_TRUE)

    # Identifier pattern (capture, or reference)
    elif tokbuf.peek(lexer.T_IDENT):
        return IdentExpr.at(loc, tokbuf.take(lexer.T_IDENT).text)

    # Array pattern
    elif tokbuf.takeif(lexer.T_LBRACKET):
        assert False, ("TODO", tokbuf)

    assert False, tokbuf


def _testparse(code, fn):
    return fn(_TokenBuffer(lexer.Lexer(code)))

def test_import():
    assert ImportDecl('hello/world.ch') == _testparse("import hello/world.ch", _parse_decl)

def test_typexpr():
    assert TypeRef("void") == _testparse("void", _parse_typeexpr)
    assert TypeRef("foobar") == _testparse("foobar", _parse_typeexpr)
    assert QualifiedTypeRef("io", "file") == _testparse("io.file", _parse_typeexpr)
    assert PointerType(TypeRef("int")) == _testparse("int*", _parse_typeexpr)
    assert ArraySliceType(TypeRef("int")) == _testparse("int[]", _parse_typeexpr)
    #assert OptionalType(TypeRef("int")) == _testparse("int?", _parse_typeexpr)
    assert TypeRef("char") == _testparse("char", _parse_typeexpr)
    assert ConstType(TypeRef("char")) == _testparse("const char", _parse_typeexpr)
    assert _testparse("const int*", _parse_typeexpr) == _testparse("int const*", _parse_typeexpr)
    assert ArraySliceType(ConstType(PointerType(ConstType(TypeRef("char"))))) == _testparse("const char* const[]", _parse_typeexpr)

def test_expr():
    assert BoolExpr(True) == _testparse("true", _parse_expr)
    assert BoolExpr(False) == _testparse("false", _parse_expr)
    assert BoolExpr(False) == _testparse("(false)", _parse_expr)
    assert IntegerExpr(10) == _testparse("10", _parse_expr)
    assert IntegerExpr(10) == _testparse("(10)", _parse_expr)
    assert IdentExpr('x') == _testparse("x", _parse_expr)
    assert CallExpr(IdentExpr('f'), [], {}) == _testparse("f()", _parse_expr)
    assert IndexExpr(IdentExpr('i'), IntegerExpr(1)) == _testparse("i[1]", _parse_expr)
    assert StringExpr('hello') == _testparse("'hello'", _parse_expr)

def test_binexpr():
    assert BinaryExpr('or', BoolExpr(value=False), BoolExpr(True)) == _testparse("false or true", _parse_expr)
    assert BinaryExpr('+', IntegerExpr(1), BinaryExpr('*', IntegerExpr(2), IntegerExpr(3))) == _testparse("1 + 2 * 3", _parse_expr)
    assert BinaryExpr('+', BinaryExpr('*', IntegerExpr(1), IntegerExpr(2)), IntegerExpr(3)) == _testparse("1 * 2 + 3", _parse_expr)
    assert BinaryExpr('*', IntegerExpr(1), BinaryExpr('else', IntegerExpr(2), IntegerExpr(3))) == _testparse("1 * 2 else 3", _parse_expr)  

def test_memberexpr():
    assert MemberExpr(IdentExpr('foo'), 'bar') == _testparse("foo.bar", _parse_expr)

def test_if_expr():
    assert IfExpr(IdentExpr('a'), IdentExpr('x'), IdentExpr('b')) == _testparse("x if a else b", _parse_expr)

def test_if_stmt():
    assert IfStmt(IdentExpr('a'), BlockStmt([ExprStmt(IntegerExpr(1))]), BlockStmt([ExprStmt(IntegerExpr(2))])) == _testparse("if (a) 1; else 2;", _parse_stmt)
    assert IfStmt(IdentExpr('a'), BlockStmt([ExprStmt(IntegerExpr(1))]), BlockStmt([ExprStmt(IntegerExpr(2))])) == _testparse("if (a) {1;} else {2;}", _parse_stmt)

def test_where_expr():
    assert WhereExpr(IdentExpr('x'), BlockStmt([ExprStmt(IntegerExpr(0))])) == _testparse("x where { 0; }", _parse_expr)
    assert _testparse("x where { 0; }", _parse_expr) == _testparse("x where 0;", _parse_expr)
    assert IfExpr(IdentExpr('b'), WhereExpr(IdentExpr('a'), BlockStmt([])), IdentExpr('c')) == _testparse("a where { } if b else c;", _parse_expr)

def test_stmt():
    assert ReturnStmt(IntegerExpr(2)) == _testparse("return 2;", _parse_stmt)
    assert ExprStmt(IntegerExpr(1)) == _testparse("1;", _parse_stmt)
    assert VarDecl(TypeRef('int'), 'i', None) == _testparse("int i;", _parse_stmt)
    assert VarDecl(PointerType(ConstType(TypeRef('int'))), 'p', NullExpr()) == _testparse("int const* p = null;", _parse_stmt)
    assert BlockStmt([]) == _testparse("{}", _parse_stmt)
    assert BlockStmt([ReturnStmt(IntegerExpr(1)), ReturnStmt(IntegerExpr(2))]) == _testparse("{return 1;return 2;}", _parse_stmt)
    assert VarDecl(TypeRef('int'), 'i', None) == _testparse("int i;", _parse_stmt)
    assert VarDecl(PointerType(TypeRef('int')), 'i', None) == _testparse("int* i;", _parse_stmt)
    assert _testparse("(int* i());", _parse_stmt) == _testparse("int* i();", _parse_stmt)
    assert _testparse("(int* i*j);", _parse_stmt) == _testparse("int* i*j;", _parse_stmt)

def test_function():
    assert FunctionDecl(TypeRef("void"), "f", [], [], BlockStmt([]), False) == _testparse("void f() { }", _parse_decl)
    assert FunctionDecl(TypeRef("int"), "g", [TypeRef("bool")], ['b'], BlockStmt([]), False) == _testparse("int g(bool b) { }", _parse_decl)
    assert FunctionDecl(TypeRef("int"), "h", [], [], ReturnStmt(IntegerExpr(5)), False) == _testparse("int h() return 5;", _parse_decl)
    assert FunctionDecl(TypeRef("int"), "k", [], [], BlockStmt([ReturnStmt(IntegerExpr(7))]), False) == _testparse("int k() {return 7;}", _parse_decl)
    assert [TypeRef("int")] == _testparse("int k(int i) {}", _parse_decl).argtypes
    assert ['a', 'b'] == _testparse("int k(int a, bool b) {}", _parse_decl).argnames


def test_type_decl():
    assert TypeDecl('Foo', [TypeCtor('Foo', [], [], None)], False) == _testparse("type Foo();", _parse_decl)
    assert TypeDecl('Foo', [TypeCtor('Foo', [TypeRef(name='int')], ['i'], None)], False) == _testparse("type Foo(int i);", _parse_decl)
    assert TypeDecl('Foo', [TypeCtor('Foo', [TypeRef(name='int'), PointerType(TypeRef(name='void'))], ['i', 'p'], None)], False) == _testparse("type Foo(int i, void* p);", _parse_decl)
    assert _testparse("type Foo();", _parse_decl) == _testparse("type Foo { Foo(); }", _parse_decl)
    assert TypeDecl('Foo', [TypeCtor('Goo', [], [], None), TypeCtor('Bar', [TypeRef('int')], ['i'], None)], False) == _testparse("type Foo { Goo(); Bar(int i); }", _parse_decl)
    assert TypeDecl('Foo', [TypeCtor('Goo', [], [], IntegerExpr(0)), TypeCtor('Bar', [], [], IntegerExpr(1))], False) == _testparse("type Foo { Goo() = 0; Bar() = 1; }", _parse_decl)
    assert TypeDecl('Foo', [TypeCtor('A', None, None, None), TypeCtor('B', None, None, None)], False) == _testparse("type Foo { A; B; }", _parse_decl)
    assert TypeDecl('Foo', [TypeCtor('A', None, None, IntegerExpr(0)), TypeCtor('B', None, None, IntegerExpr(1))], False) == _testparse("type Foo { A = 0; B = 1; }", _parse_decl)


def _test_for():
    assert ForInExpr(TypeRef('auto'), 'x', IdentExpr('foo'), ExprStmt(BlockStmt([]))) == _testparse("for (int i = 0; i < 10; i++) { }", _parse_stmt)
    assert _testparse("for (x in foo) { }", _parse_expr) == _testparse("for x in foo { }", _parse_expr)
    assert _testparse("for (auto x in foo) { }", _parse_expr) == _testparse("for x in foo { }", _parse_expr)

def _test_while():
    assert _testparse("while (x) { }", _parse_expr) == WhileExpr(IdentExpr('x'), ExprStmt(BlockStmt([])))

def _test_switch():
    assert _testparse("switch (x) { }", _parse_expr) == SwitchExpr(IdentExpr('x'), [], [])
    assert _testparse("switch (x) { case 0: 1; }", _parse_expr) == SwitchExpr(IdentExpr('x'), [IntegerExpr(0)], [IntegerExpr(1)])
    assert _testparse("switch (x) { case 0: 1; case 1: 2; }", _parse_expr) == SwitchExpr(IdentExpr('x'), [IntegerExpr(0), IntegerExpr(1)], [IntegerExpr(1), IntegerExpr(2)])
    assert _testparse("switch (x) { case Foo(0): 1; }", _parse_expr) == SwitchExpr(IdentExpr('x'), [CtorExpr('Foo', [IntegerExpr(0)])], [IntegerExpr(1)])