import os
import frontend.lexer as lexer
import frontend.astnodes as ast
import copy
from frontend.reparser import parse_regex

class ParserState:
    def __init__(self, filename, text):
        self.lexer = lexer.LexerState(filename, text)
        self.token = lexer.lex(self.lexer)
        self.queue = [lexer.lex(self.lexer)]
        self.errors = []

def parser_copy(parser):
    return copy.deepcopy(parser)

def parser_commit(dst, src):
    dst.lexer = src.lexer
    dst.token = src.token
    dst.queue = src.queue[:]
    dst.errors = src.errors

def enqueue_token(parser, token_type, token_value):
    parser.queue.insert(0, parser.token)
    parser.token = lexer.Token(token_type, token_value, parser.token.location)

def advance(parser):
    parser.token = parser.queue.pop(0)
    if len(parser.queue) == 0:
        parser.queue.append(lexer.lex(parser.lexer))

def error(parser, msg):
    parser.errors.append(ast.SyntaxError(parser.token.location, msg, parser.token.value))

def expect(parser, tokty, msg):
    ok = True
    if parser.token.type != tokty:
        loc = parser.token.location
        #print("%s:%s: Error: %s; got '%s'" % (loc.line, loc.column, msg, parser.token.value))
        parser.errors.append(ast.SyntaxError(loc, msg, parser.token.value))
        ok = False
        #assert False
    advance(parser)
    return ok

def see(parser, tok0, tok1=None, *, value=None):
    if tok1 == None and value == None:
        return parser.token.type == tok0
    elif tok1 == None and value != None:
        return parser.token.type == tok0 and parser.token.value == value
    else:
        return parser.token.type == tok0 and parser.queue[0].type == tok1



OPERATOR_PRECEDENCE_TABLE = {"..": 0,
                             "or": 1,
                             "and": 2,
                             "==": 3, "!=": 3, ">": 3, ">=": 3, "<": 3, "<=": 3,
                             "|": 4,
                             "^": 5,
                             "&": 6,
                             "<<": 7, ">>": 7,
                             "+": 8, "-": 8,
                             "*": 9, "/": 9, "//": 9, "%": 9,
                             "**": 10,
                             "else": 11}
MAX_PRECEDENECE = max(OPERATOR_PRECEDENCE_TABLE.values())

def parse_typeexpr_tupletype(parser):
    location = parser.token.location
    expect(parser, lexer.TokenType.LPAREN, "Expected '(' to begin tuple-type")
    positional = []
    names = []
    named = []
    parse_positional = True
    error_emitted = False
    while parser.token.type != lexer.TokenType.RPAREN:
        if see(parser, lexer.TokenType.IDENTIFIER, lexer.TokenType.COLON):
            names.append(parser.token.value)
            advance(parser)
            advance(parser)
            named.append(parse_typeexpr(parser))
            parse_positional = False
        else:
            if not parse_positional and not error_emitted:
                error_emitted = True
                error("Named tuple slots must follow positional slots")
            positional.append(parse_typeexpr(parser))
        if see(parser, lexer.TokenType.COMMA):
            advance(parser)
        else:
            break
    expect(parser, lexer.TokenType.RPAREN, "Expected ')' to finish tuple-type")
    return ast.TupleType(positional, named, names, location=location)

def parse_typeexpr_wo_union(parser):
    location = parser.token.location
    if see(parser, lexer.TokenType.IDENTIFIER):
        namespace = 'implicit'
        name = parser.token.value
        advance(parser)
        if see(parser, lexer.TokenType.DOT):
            advance(parser)
            namespace = name
            name = parser.token.value
            expect(parser, lexer.TokenType.IDENTIFIER, "Expected identifier")
        ty = ast.NamedType(namespace, name, location=parser.token.location)
    elif see(parser, lexer.TokenType.LPAREN):
        ty = parse_typeexpr_tupletype(parser)
    else:
        assert False, parser.token

    # Function type
    if see(parser, lexer.TokenType.LPAREN):
        advance(parser)
        argtys = []
        argnames = []
        while parser.token.type != lexer.TokenType.RPAREN:
            argtys.append(parse_typeexpr(parser))
            argnames.append(parser.token.value)
            expect(parser, lexer.TokenType.IDENTIFIER, "Expected argument name")
            if see(parser, lexer.TokenType.COMMA):
                advance(parser)
            else:
                break
        expect(parser, lexer.TokenType.RPAREN, "Expected ')' to finish field list")
        ty = ast.FunctionType(ty, argtys, argnames, location=location)

    while True:
        location = parser.token.location
        if see(parser, lexer.TokenType.OPERATOR, value='*'):
            ty = ast.PointerType(ty, location=location)
            advance(parser)
        elif see(parser, lexer.TokenType.LBRACKET, lexer.TokenType.RBRACKET):
            ty = ast.ArrayType(ty, location=location)
            advance(parser)
            advance(parser)
        elif see(parser, lexer.TokenType.QUESTION):
            ty = ast.OptionType(ty, location=location)
            advance(parser)
        elif see(parser, lexer.TokenType.EXCLAMATION):
            ty = ast.ErrorType(ty, location=location)
            advance(parser)
        else:
            break
    return ty

def parse_typeexpr(parser):
    """
    Parse a single type expression
    """
    location = parser.token.location
    ty = parse_typeexpr_wo_union(parser)
    if see(parser, lexer.TokenType.OPERATOR, value='|'):
        tys = [ty]
        while see(parser, lexer.TokenType.OPERATOR, value='|'):
            advance(parser)
            tys.append(parse_typeexpr_wo_union(parser))
        ty = ast.UnionType(tys, location=location)
    return ty

def parse_expr_array(parser):
    location = parser.token.location
    expect(parser, lexer.TokenType.LBRACKET, "Expected '(' to begin tuple-type")
    elems = []
    while parser.token.type != lexer.TokenType.RBRACKET:
        elems.append(parse_expr(parser, trailing_block_permitted=False))
        if see(parser, lexer.TokenType.COMMA):
            advance(parser)
        else:
            break
    expect(parser, lexer.TokenType.RBRACKET, "Expected ')' to finish tuple")

    return ast.ArrayExpr(elems, location=location)

def parse_expr_tuple(parser, only_named=False):
    location = parser.token.location
    expect(parser, lexer.TokenType.LPAREN, "Expected '(' to begin tuple-type")
    positional = []
    names = []
    named = []
    parse_positional = not only_named
    error_emitted = False
    while parser.token.type != lexer.TokenType.RPAREN:
        if see(parser, lexer.TokenType.IDENTIFIER, lexer.TokenType.COLON):
            names.append(parser.token.value)
            advance(parser)
            advance(parser)
            named.append(parse_expr(parser, trailing_block_permitted=False))
            parse_positional = False
        else:
            if not parse_positional and not error_emitted:
                error_emitted = True
                error("Named tuple slots must follow positional slots")
            positional.append(parse_expr(parser, trailing_block_permitted=False))
        if see(parser, lexer.TokenType.COMMA):
            advance(parser)
        else:
            break
    expect(parser, lexer.TokenType.RPAREN, "Expected ')' to finish tuple")

    return ast.TupleExpr(positional, named, names, location=location)


def parse_expr_atom(parser, trailing_block_permitted):
    location = parser.token.location
    match parser.token.type:
        case lexer.TokenType.INT:
            value = parser.token.value
            advance(parser)
            return ast.IntegerExpr(eval(value.replace("_", "")), location=location)
        case lexer.TokenType.FLOAT:
            value = parser.token.value
            advance(parser)
            return ast.FloatExpr(value, location=location)
        case lexer.TokenType.REGEX:
            value = parser.token.value
            advance(parser)
            reast = parse_regex(value[1:-1])
            return ast.RegexExpr(reast, location=location)
        case lexer.TokenType.STRING:
            value = parser.token.value
            advance(parser)
            return ast.StringExpr(value, location=location)
        case lexer.TokenType.SYMBOL:
            value = parser.token.value[1:]
            advance(parser)
            if value[0] in ('"', "'"):
                value = value[1:-1]
            return ast.SymbolExpr(value, location=location)
        case lexer.TokenType.BOOL:
            value = parser.token.value == 'true'
            advance(parser)
            return ast.BoolExpr(value, location=location)
        case lexer.TokenType.NULL:
            advance(parser)
            return ast.NullExpr(location=location)
        case lexer.TokenType.IDENTIFIER:
            name = parser.token.value
            advance(parser)
            return ast.IdentifierExpr(name, location=location)
        case lexer.TokenType.CAST:
            advance(parser)
            expect(parser, lexer.TokenType.LPAREN, "Expected '(' after 'cast'")
            ty = parse_typeexpr(parser)
            expect(parser, lexer.TokenType.RPAREN, "Expected ')' after cast")
            return ast.CastExpr(ty, parse_expr(parser, trailing_block_permitted=True))
        case lexer.TokenType.LET:
            advance(parser)
            implicit = False
            if see(parser, lexer.TokenType.IMPLICIT):
                implicit = True
                advance(parser)
            name = parser.token.value
            expect(parser, lexer.TokenType.IDENTIFIER, "Expected variable name after 'let'")
            return ast.NewIdentifierExpr(name, implicit=implicit, location=location)
        case lexer.TokenType.TYPE:
            advance(parser)
            expect(parser, lexer.TokenType.LPAREN, "Expected '(' after 'type'")
            expr = parse_expr(parser, trailing_block_permitted=True)
            expect(parser, lexer.TokenType.RPAREN, "Expected ')'")
            return ast.TypeOfExpr(expr, location=location)
        case lexer.TokenType.LBRACKET:
            return parse_expr_array(parser)
        case lexer.TokenType.LPAREN:
            return parse_expr_tuple(parser)
        case lexer.TokenType.FOR if trailing_block_permitted:
            advance(parser)
            if see(parser, lexer.TokenType.LPAREN):
                iterator = parse_expr_tuple(parser)
            elif see(parser, lexer.TokenType.IDENTIFIER):
                iterator = ast.IdentifierExpr(parser.token.value)
                advance(parser)
            else:
                error(parser, "Expected tuple or identifier")
            expect(parser, lexer.TokenType.IN, "Expect 'in'")
            iterable = parse_expr(parser, trailing_block_permitted=False)
            body = parse_stmt_block(parser)
            return ast.ForExpr(iterator, iterable, body)
        case lexer.TokenType.WHILE if trailing_block_permitted:
            advance(parser)
            cond = parse_expr(parser, trailing_block_permitted=False)
            body = parse_stmt_block(parser)
            return ast.WhileExpr(cond, body)
        case lexer.TokenType.IF if trailing_block_permitted:
            advance(parser)
            cond = parse_expr(parser, trailing_block_permitted=False)
            if see(parser, lexer.TokenType.CASE):
                advance(parser)
                pattern = parse_expr(parser, trailing_block_permitted=False)
            else:
                pattern = None
            true_body = parse_stmt_block(parser)
            # TODO: This should only be done if the semicolon is implicit
            if see(parser, lexer.TokenType.SEMICOLON, lexer.TokenType.ELSE):
                advance(parser)
            if see(parser, lexer.TokenType.ELSE, lexer.TokenType.IF):
                advance(parser)
                if_expr = parse_expr_atom(parser, trailing_block_permitted)
                false_body = ast.BlockStmt([ast.ExprStmt(if_expr)])
            elif see(parser, lexer.TokenType.ELSE):
                advance(parser)
                false_body = parse_stmt_block(parser)
            else:
                false_body = ast.BlockStmt([])
            if pattern is not None:
                return ast.IfCaseExpr(cond, pattern, true_body, false_body)
            return ast.IfExpr(cond, true_body, false_body)
        case _:
            error(parser, "Expected expression")
            advance(parser)

def parse_expr_primary(parser, trailing_block_permitted):
    expr = parse_expr_atom(parser, trailing_block_permitted)
    while True:
        location = parser.token.location
        match parser.token.type:
            case lexer.TokenType.LPAREN:
                args = parse_expr_tuple(parser)
                if trailing_block_permitted and see(parser, lexer.TokenType.LBRACE):
                    block = parse_stmt_block(parser)
                else:
                    block = None
                expr = ast.CallExpr(expr, args, block, location=location)
            case lexer.TokenType.ON:
                advance(parser)
                data = parse_expr(parser, trailing_block_permitted=False)
                expr = ast.AllocateExpr(expr, data, location=location)
            case lexer.TokenType.DOT:
                advance(parser)
                name = parser.token.value
                expect(parser, lexer.TokenType.IDENTIFIER, "Expected identifier for member access")
                expr = ast.MemberExpr(expr, name, location=location)
            case lexer.TokenType.LBRACKET:
                advance(parser)
                index = parse_expr(parser, trailing_block_permitted=False)
                expect(parser, lexer.TokenType.RBRACKET, "Expected ']'")
                expr = ast.IndexExpr(expr, [index], location=location)
            case _:
                break
    return expr

def parse_expr_unary(parser, precedence, trailing_block_permitted):
    location = parser.token.location
    max_prec = 12
    table = {2: ['not'], 12: ["+", "-", "~", '&', '*']}#, ':+', ':~', ':-', '.+', '.-', '.*', '.and', '.or', ':not']}

    if parser.token.value in table.get(precedence, []):
        op = parser.token.value
        advance(parser)
        operand = parse_expr_unary(parser, precedence, trailing_block_permitted)
        return ast.UnaryOpExpr(op, operand, location=location)
    elif precedence < max_prec:
        return parse_expr_unary(parser, precedence + 1, trailing_block_permitted)
    return parse_expr_primary(parser, trailing_block_permitted)

def parse_expr_binary(parser, precedence, trailing_block_permitted):
    left = parse_expr_unary(parser, precedence, trailing_block_permitted)
    while (see(parser, lexer.TokenType.OPERATOR) or see(parser, lexer.TokenType.ELSE)) and OPERATOR_PRECEDENCE_TABLE[parser.token.value] >= precedence:
        location = parser.token.location
        op = parser.token.value
        advance(parser)
        if op == 'else':
            if see(parser, lexer.TokenType.LBRACE) and trailing_block_permitted:
                stmt = parse_stmt_block(parser)
                return ast.BinaryElseExpr(left, stmt)
            else:
                right = parse_expr_binary(parser, OPERATOR_PRECEDENCE_TABLE[op] + 1, trailing_block_permitted)
                return ast.BinaryElseExpr(left, ast.BlockStmt([ast.ExprStmt(right)]))
        else:
            right = parse_expr_binary(parser, OPERATOR_PRECEDENCE_TABLE[op] + 1, trailing_block_permitted)
            left = ast.BinaryOpExpr(left, op, right, location=location)
    return left


def parse_expr(parser, trailing_block_permitted):
    return parse_expr_binary(parser, precedence=0, trailing_block_permitted=trailing_block_permitted)

def parse_expr_top(parser):
    match parser.token.type:
        case _:
            expr = parse_expr(parser, trailing_block_permitted=True)
            if see(parser, lexer.TokenType.WHERE):
                location = parser.token.location
                advance(parser)
                block = parse_stmt_block(parser)
                return ast.WhereExpr(expr, block.stmts, location=location)
            return expr

def parse_stmt_expr_or_assign(parser):
    location = parser.token.location
    lhs = parse_expr_top(parser)
    if see(parser, lexer.TokenType.SEMICOLON):
        advance(parser)
        return ast.ExprStmt(lhs, location=location)
    expect(parser, lexer.TokenType.ASSIGN, "Expected '='")
    rhs = parse_expr_top(parser)
    expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' after expression")
    return ast.AssignStmt(lhs, rhs, location=location)

def parse_stmt(parser):
    location = parser.token.location
    match parser.token.type:
        case lexer.TokenType.PASS:
            advance(parser)
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' after 'pass'")
            return ast.PassStmt(location=location)
        case lexer.TokenType.CONTINUE:
            advance(parser)
            value = parse_expr_top(parser) if not see(parser, lexer.TokenType.SEMICOLON) else ast.NoExpr
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' after 'continue'")
            return ast.ContinueStmt(value, location=location)
        case lexer.TokenType.BREAK:
            advance(parser)
            value = parse_expr_top(parser) if not see(parser, lexer.TokenType.SEMICOLON) else ast.NoExpr
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' after 'break'")
            return ast.BreakStmt(value, location=location)
        case lexer.TokenType.RETURN:
            advance(parser)
            value = parse_expr_top(parser) if not see(parser, lexer.TokenType.SEMICOLON) else ast.NoExpr
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' after 'return'")
            return ast.ReturnStmt(value, location=location)
        case lexer.TokenType.ASSERT:
            advance(parser)
            value = parse_expr_top(parser)
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' after 'assert'")
            return ast.AssertStmt(value, location=location)
        case _:
            return parse_stmt_expr_or_assign(parser)

def parse_stmt_block(parser):
    location = parser.token.location
    expect(parser, lexer.TokenType.LBRACE, "Expected block statement")
    stmts = []
    while parser.token.type != lexer.TokenType.RBRACE:
        stmt = parse_stmt(parser)
        if type(stmt) != ast.PassStmt:
            stmts.append(stmt)
    expect(parser, lexer.TokenType.RBRACE, "Expected end of block statement")
    return ast.BlockStmt(stmts, location=location)

def parse_top_type_constructor(parser):
    location = parser.token.location
    name = parser.token.value
    expect(parser, lexer.TokenType.IDENTIFIER, "Expected type constructor name")

    # This is a constructor without argument list
    if see(parser, lexer.TokenType.SEMICOLON) or see(parser, lexer.TokenType.ASSIGN):
        field_names = None
        field_types = None

    # Parse argument list.
    else:
        expect(parser, lexer.TokenType.LPAREN, "Expected '('")
        field_types = []
        field_names = []
        while parser.token.type != lexer.TokenType.RPAREN:
            field_types.append(parse_typeexpr(parser))
            field_names.append(parser.token.value)
            expect(parser, lexer.TokenType.IDENTIFIER, "Expected field name")
            if see(parser, lexer.TokenType.COMMA):
                advance(parser)
            else:
                break
        expect(parser, lexer.TokenType.RPAREN, "Expected ')' to finish field list")

    if see(parser, lexer.TokenType.ASSIGN):
        advance(parser)
        tag_value = parse_expr(parser, trailing_block_permitted=False)
    else:
        tag_value = None

    expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' to finish constructor definition")

    return ast.TypeConstructor(name, field_types, field_names, tag_value, location=location)


def parse_top(parser):
    """
    Parse a single top-level definition
    """
    location = parser.token.location
    export = False
    if see(parser, lexer.TokenType.EXPORT):
        advance(parser)
        export = True

    if see(parser, lexer.TokenType.IMPORT):
        filename = parser.token.value
        advance(parser)
        expect_semicolon = True
        if see(parser, lexer.TokenType.IN):
            advance(parser)
            namespace = parser.token.value
            # Either 'implicit' or an identifier is expected
            if parser.token.type == lexer.TokenType.IMPLICIT:
                advance(parser)
            else:
                expect(parser, lexer.TokenType.IDENTIFIER, "Expected namespace")
            # semicolon isn't inserted implicitly after 'implicit' so we need to handle that here
            if not see(parser, lexer.TokenType.SEMICOLON) and not see(parser, lexer.TokenType.LPAREN):
                expect_semicolon = False
        else:
            basename = os.path.basename(filename)
            namespace = os.path.splitext(basename)[0]
        if see(parser, lexer.TokenType.LPAREN):
            import_params = parse_expr_tuple(parser, only_named=True)
        else:
            import_params = None
        if expect_semicolon:
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' to end import declaration")
        return ast.ImportDef(filename, namespace, import_params, location=location)

    # Type definition
    elif see(parser, lexer.TokenType.TYPE):
        advance(parser)

        # General/long form
        if parser.queue[0].type == lexer.TokenType.LBRACE:
            tyname = parser.token.value
            ctors = []
            expect(parser, lexer.TokenType.IDENTIFIER, "Expected type name")
            expect(parser, lexer.TokenType.LBRACE, "Expected '{' to begin type definition")
            while parser.token.type != lexer.TokenType.RBRACE:
                ctors.append(parse_top_type_constructor(parser))
            expect(parser, lexer.TokenType.RBRACE, "Expected '}' to end type definition")
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' to end type definition")
            return ast.TypeDef(export, tyname, ctors, location=location)

        # Short form
        else:
            ctor = parse_top_type_constructor(parser)
            return ast.TypeDef(export, ctor.name, [ctor], location=location)

    # Function or variable definition
    elif see(parser, lexer.TokenType.IDENTIFIER) or see(parser, lexer.TokenType.LPAREN):
        ty = parse_typeexpr(parser)
        name = parser.token.value
        expect(parser, lexer.TokenType.IDENTIFIER, "Expected variable name")
        # Parse global variable definition
        if see(parser, lexer.TokenType.ASSIGN):
            advance(parser)
            value = parse_expr_top(parser)
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' to end variable assignment")
            return ast.VariableDef(export, ty, name, value, location=location)
        
        # Parse function definition
        else:
            expect(parser, lexer.TokenType.LPAREN, "Expected '(' or '='")
            argtys_implicit = []
            argnames_implicit = []
            argtys = []
            argnames = []
            implicit_arg_permitted = True
            while parser.token.type != lexer.TokenType.RPAREN:
                implicit = False
                if implicit_arg_permitted:
                    if see(parser, lexer.TokenType.IMPLICIT):
                        advance(parser)
                        implicit = True
                    else:
                        implicit_arg_permitted = False                    
                    
                if implicit:
                    argtys_implicit.append(parse_typeexpr(parser))
                    argnames_implicit.append(parser.token.value)
                else:
                    argtys.append(parse_typeexpr(parser))
                    argnames.append(parser.token.value)
                expect(parser, lexer.TokenType.IDENTIFIER, "Expected argument name")
                if see(parser, lexer.TokenType.COMMA):
                    advance(parser)
                else:
                    break
            expect(parser, lexer.TokenType.RPAREN, "Expected ')' to finish argument list")
            body = parse_stmt_block(parser).stmts
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';' to end function definition")
            return ast.FunctionDef(export, ty, name, argtys_implicit, argnames_implicit, argtys, argnames, body, location=location)

def parse_module(parser, filename, main_module):
    defs = []

    if '__builtins__' not in filename:
        implicit_imports = ["string", "symbol", "context", "range"]
        for name in implicit_imports:
            defs.append(ast.ImportDef("__builtins__/%s.ce" % name, 'implicit', None, location=None))
    
    while not see(parser, lexer.TokenType.EOF):
        defs.append(parse_top(parser))
    return ast.ModuleDef(parser.lexer.filename, defs, main_module=main_module)


def parse_text(full_filename, filename, text, main_module):
    parser = ParserState(filename, text)
    module_ast = parse_module(parser, filename, main_module)
    assert parser.errors == [], parser.errors
    return module_ast

def parse_file(full_filename, filename, main_module):
    with open(full_filename) as f:
        text = f.read()
        return parse_text(full_filename, filename, text, main_module)

if __name__ == '__main__':
    def test(code, ast, fn):
        parser = ParserState("test.ch", code)
        actual_ast = fn(parser)
        assert parser.errors == [], parser.errors
        if actual_ast != ast:
            print("Expected:\n  %s\nGot:\n  %s" % (ast, actual_ast))
            assert False
   
    code = """
    let for_else = for eee in 0..7 {
        if eee > 10 {
            break 100
        }
    } else -100

    """
    test(code, None, parse_stmt)