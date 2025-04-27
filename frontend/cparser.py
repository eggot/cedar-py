import os
import frontend.clexer as lexer
import frontend.astnodes as ast
import copy

class ParserState:
    def __init__(self, filename, text, ignore_tokens, default_macros):
        self.lexer = lexer.LexerState(filename, text, ignore_tokens)
        self.default_macros = default_macros
        self.token = lexer.lex(self.lexer)
        self.next_token = lexer.lex(self.lexer)
        self.errors = []
        # Preprocessor definitions; populated as the file is parsed.
        self.ppdefs = {}
        self.includes = []
        self.defs = [] # The parse tree

def advance(parser):
    parser.token = parser.next_token
    parser.next_token = lexer.lex(parser.lexer)

def error(parser, msg):
    parser.errors.append(ast.SyntaxError(parser.token.location, msg, parser.token.value))

def expect(parser, tokty, msg):
    ok = True
    if parser.token.type != tokty:
        loc = parser.token.location
        print("%s:%s: Error: %s; got '%s'" % (loc.line, loc.column, msg, parser.token.value))
        parser.errors.append(ast.SyntaxError(loc, msg, parser.token.value))
        ok = False
        assert False
    advance(parser)
    return ok

def see(parser, tok0, tok1=None, *, value=None):
    if tok1 == None and value == None:
        return parser.token.type == tok0
    elif tok1 == None and value != None:
        return parser.token.type == tok0 and parser.token.value == value
    else:
        return parser.token.type == tok0 and parser.next_token.type == tok1


def skip_until(parser, toktypes, block_ending=None, keep_last=False):
    toks = []
    if type(toktypes) != tuple:
        toktypes = (toktypes, lexer.TokenType.EOF) 
    else:
        toktypes += (lexer.TokenType.EOF, )
    if parser.token.type == block_ending:
        return toks
    while parser.token.type not in toktypes:
        toks.append(parser.token)
        advance(parser)
        if parser.token.type == block_ending:
            return toks
    if not keep_last:
        advance(parser)
    return toks

PARENS = {lexer.TokenType.LBRACE: (lexer.TokenType.RBRACE, ), 
            lexer.TokenType.LPAREN: (lexer.TokenType.RPAREN, ),
            lexer.TokenType.LBRACKET: (lexer.TokenType.RBRACKET, )}
def skip_expression(parser, end_tokens):
    while parser.token.type not in end_tokens:
        tokty = parser.token.type
        advance(parser)
        if tokty in PARENS:
            skip_expression(parser, PARENS[tokty])

def skip_until_pp_endif(parser):
    while not see(parser, lexer.TokenType.PPDIRECTIVE, value='endif') and parser.token.type != lexer.TokenType.EOF:
        recurse = see(parser, lexer.TokenType.PPDIRECTIVE) and parser.token.value.startswith('if')
        advance(parser)
        if recurse:
            skip_until_pp_endif(parser)
    skip_until(parser, lexer.TokenType.PPDIRECTIVE_END)

def determine_pp_define_type(parser, toks, location):
    if any(t.type == lexer.TokenType.INT_LITERAL for t in toks):
        return ast.CNamedType('int', location=location)
    elif any(t.type == lexer.TokenType.FLOAT_LITERAL for t in toks):
        return ast.CNamedType('float', location=location)
    for t in toks:
        if t.value in parser.ppdefs:
            return parser.ppdefs[t.value].ty
    return None
            
    
def parse_pp_directive(parser):
    directive = parser.token.value
    advance(parser)

    if directive.startswith('if'):
        skip_until_pp_endif(parser)
        return

    location = parser.token.location
    match directive:
        case 'define':
            ident = parser.token.value
            expect(parser, lexer.TokenType.IDENTIFIER, "Expected identifier after #define")
            toks = skip_until(parser, lexer.TokenType.PPDIRECTIVE_END)
            ty = determine_pp_define_type(parser, toks, location)
            res = ast.CConstDefine(ty, ident, undefined=False, location=location)
            parser.ppdefs[ident] = res
            return res
        case 'undef':
            ident = parser.token.value
            expect(parser, lexer.TokenType.IDENTIFIER, "Expected identifier after #define")
            skip_until(parser, lexer.TokenType.PPDIRECTIVE_END)
            if ident in parser.ppdefs:
                parser.ppdefs[ident].undefined = True
            return
        case 'include':
            if see(parser, lexer.TokenType.STRING_LITERAL):
                filename = parser.token.value
                skip_until(parser, lexer.TokenType.PPDIRECTIVE_END)
            else:
                toks = skip_until(parser, lexer.TokenType.PPDIRECTIVE_END)[1:-1]
                filename = "".join(t.value for t in toks)
            return ast.CInclude(filename)
        case 'include_next':
            # This is some gcc thing, don't know what it's for.
            skip_until(parser, lexer.TokenType.PPDIRECTIVE_END)
        case 'error':
            # Since we're not doing a proper pre-processing, we can't know for sure that
            # the error would be triggered so we simply skip it.
            skip_until(parser, lexer.TokenType.PPDIRECTIVE_END)
        case _:
            assert False, directive


TYPE_SPECIFIERS = {lexer.TokenType.UNSIGNED, lexer.TokenType.SIGNED, lexer.TokenType.LONG, lexer.TokenType.SHORT,
                   lexer.TokenType.INT, lexer.TokenType.CHAR}
KW_TYPES = {lexer.TokenType.FLOAT, lexer.TokenType.VOID, lexer.TokenType.DOUBLE}
def parse_typeexpr(parser):
    location = parser.token.location
    is_const = False
    if see(parser, lexer.TokenType.CONST):
        is_const = True
        advance(parser)

    tok = parser.token
    match tok.type:
        case lexer.TokenType.IDENTIFIER:
            advance(parser)
            ty = ast.CNamedType(tok.value, location=location)
        case lexer.TokenType.ENUM:
            name, enumerators = parse_enum(parser)
            ty = ast.CAnonymousType(ast.CEnumDef(name, enumerators, location=location))
        case ty if ty in (lexer.TokenType.STRUCT, lexer.TokenType.UNION):
            kind = parser.token.value
            advance(parser)
            name, fieldtys, fieldnames = parse_struct_or_union(parser)
            if fieldtys is None:
                ty = ast.CNamedType(name, typekind=kind, location=location)
            else:
                if name is None:
                    name = "_anonymous_%s" % len(parser.defs)
                tydef = (ast.CStructDef if kind == 'struct' else ast.CUnionDef)(name, fieldtys, fieldnames, location=location)
                parser.defs.append(tydef)
                ty = ast.CNamedType(name, typekind=kind, location=location)
        case ty if ty in TYPE_SPECIFIERS:
            advance(parser)
            name = [tok.value]
            while parser.token.type in TYPE_SPECIFIERS:
                name.append(parser.token.value)
                advance(parser)
            ty = ast.CNamedType(" ".join(name), location=location)
        case ty if ty in KW_TYPES:
            advance(parser)
            ty = ast.CNamedType(tok.value, location=location)
        case _:
            assert False, tok
    
    if is_const:
        ty = ast.CConstType(ty, location=location)

    while True:
        location = parser.token.location
        if see(parser, lexer.TokenType.OPERATOR, value='*'):
            ty = ast.PointerType(ty, location=location)
            advance(parser)
        elif see(parser, lexer.TokenType.CONST):
            ty = ast.CConstType(ty, location=location)
        else:
            break
    return ty

def parse_function_argument_list(parser):
    argtys = []
    argnames = []
    is_varargs = False
    expect(parser, lexer.TokenType.LPAREN, "Expected '('")
    if see(parser, lexer.TokenType.VOID, lexer.TokenType.RPAREN):
        advance(parser)
        advance(parser)
        return argtys, argnames, is_varargs

    while not see(parser, lexer.TokenType.RPAREN):
        if see(parser, lexer.TokenType.ELLIPSIS):
            advance(parser)
            is_varargs = True
            # Varargs has to be the last argument, so we know we can break the loop here
            break
        else:
            argty = parse_typeexpr(parser)
            if see(parser, lexer.TokenType.LPAREN, lexer.TokenType.OPERATOR) and parser.next_token.value == '*':
                argty, argname = parse_function_pointer(parser, argty)
            else:
                if see(parser, lexer.TokenType.IDENTIFIER):
                    # We might have stuff like '__restrict' directly after the type and before the argument name.
                    # Thus, we only take the last in the list of identifiers
                    while see(parser, lexer.TokenType.IDENTIFIER):
                        argname = parser.token.value
                        advance(parser)
                else:
                    argname = '__anonymous_arg_%d' % len(argnames)
        if see(parser, lexer.TokenType.LBRACKET):
            advance(parser)
            if not see(parser, lexer.TokenType.RBRACE):
                skip_expression(parser, [lexer.TokenType.RBRACKET])
            advance(parser)
            argty = ast.CArrayType(argty)
        argtys.append(argty)
        argnames.append(argname)
        if see(parser, lexer.TokenType.COMMA):
            advance(parser)
            continue
        break

    expect(parser, lexer.TokenType.RPAREN, "Expected ')'")
    return argtys, argnames, is_varargs

def skip_function_body(parser):
    skip_until(parser, (lexer.TokenType.SEMICOLON, lexer.TokenType.LBRACE), keep_last=True)
    if see(parser, lexer.TokenType.SEMICOLON):
        advance(parser)
    else:
        advance(parser)
        skip_until_paren(parser, lexer.TokenType.LBRACE, lexer.TokenType.RBRACE)

def parse_optional_identifier(parser):
    if see(parser, lexer.TokenType.IDENTIFIER):
        ident = parser.token.value
        advance(parser)
        return ident
    return None

def parse_enum(parser):
    expect(parser, lexer.TokenType.ENUM, "Expected 'enum'")
    name = parse_optional_identifier(parser)
    skip_until(parser, lexer.TokenType.LBRACE)
    enumerators = []
    while not see(parser, lexer.TokenType.RBRACE):
        if see(parser, lexer.TokenType.PPDIRECTIVE):
            parse_pp_directive(parser)
            continue
        name = parser.token.value
        expect(parser, lexer.TokenType.IDENTIFIER, "Expected identifier")
        skip_expression(parser, (lexer.TokenType.COMMA, lexer.TokenType.RBRACE))
        enumerators.append(name)
        if not see(parser, lexer.TokenType.COMMA):
            break
        advance(parser)
    expect(parser, lexer.TokenType.RBRACE, "Expecter '}'")
    return name, enumerators

def parse_struct_or_union(parser):
    typename = parse_optional_identifier(parser)
    if not parser.token.type == lexer.TokenType.LBRACE:
        return typename, None, None
    skip_until(parser, lexer.TokenType.LBRACE)
    tys = []
    names = []
    while not see(parser, lexer.TokenType.RBRACE):
        if see(parser, lexer.TokenType.PPDIRECTIVE):
            parse_pp_directive(parser)
            continue

        tys.append(parse_typeexpr(parser))
        if see(parser, lexer.TokenType.IDENTIFIER):
            name = parser.token.value
        else:
            name = '__anonymous_field_%d' % len(names)
        names.append(name)
        skip_until(parser, lexer.TokenType.SEMICOLON)
    expect(parser, lexer.TokenType.RBRACE, "Expecter '}'")
    return typename, tys, names
    
def parse_function_pointer(parser, retty):
    advance(parser)
    advance(parser)
    name = parser.token.value
    expect(parser, lexer.TokenType.IDENTIFIER, "Expected identifier")
    expect(parser, lexer.TokenType.RPAREN, "Expected ')'")
    argtys, argnames, is_varargs = parse_function_argument_list(parser)
    # TODO: Handle varargs?
    return ast.CFunctionPointerType(retty, argtys, argnames, location=retty.location), name
    
def parse_typedef(parser):
    location = parser.token.location
    ty = parse_typeexpr(parser)
    if see(parser, lexer.TokenType.LPAREN, lexer.TokenType.OPERATOR) and parser.next_token.value == '*':
        ty, name = parse_function_pointer(parser, ty)
        expect(parser, lexer.TokenType.SEMICOLON, "Expected ';'")
        return ast.CTypedefDef(name, ty, location=location)

    name = parser.token.value
    expect(parser, lexer.TokenType.IDENTIFIER, "Expected identifier")
    expect(parser, lexer.TokenType.SEMICOLON, "Expected ';'")
    match ty:
        case ast.CAnonymousType(typ):
            ty = typ
    return ast.CTypedefDef(name, ty, location=location)

def skip_until_paren(parser, opening, closing):
    while not see(parser, closing):
        if see(parser, opening):
            advance(parser)
            skip_until_paren(parser, opening, closing)
        else:
            advance(parser)
    advance(parser)

def skip_until_end_of_declaration(parser):
    while not see(parser, lexer.TokenType.SEMICOLON):
        if see(parser, lexer.TokenType.LBRACE):
            advance(parser)
            skip_until_paren(parser, lexer.TokenType.LBRACE, lexer.TokenType.RBRACE)         
        else:
            advance(parser)
    advance(parser)

def parse_top(parser):
    #print("TOP", parser.token, parser.next_token)
    location = parser.token.location
    match parser.token.type:
        case lexer.TokenType.PPDIRECTIVE:
            return parse_pp_directive(parser)
        case lexer.TokenType.TYPEDEF:
            advance(parser)
            return parse_typedef(parser)
        case lexer.TokenType.STRUCT:
            advance(parser)
            name, ftys, fnames = parse_struct_or_union(parser)
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';'")
            return ast.CStructDef(name, ftys, fnames, location=location)
        case lexer.TokenType.UNION:
            advance(parser)
            name, ftys, fnames = parse_struct_or_union(parser)
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';'")
            return ast.CUnionDef(name, ftys, fnames, location=location)
        case lexer.TokenType.ENUM:
            name, enumerators = parse_enum(parser)
            expect(parser, lexer.TokenType.SEMICOLON, "Expected ';'")
            return ast.CEnumDef(name, enumerators, location=location)
        case _:
            # This looks use of a macro at the top-level. Skip the entire thing.
            if see(parser, lexer.TokenType.IDENTIFIER, lexer.TokenType.LPAREN):
                advance(parser)
                advance(parser)
                skip_until_paren(parser, lexer.TokenType.LPAREN, lexer.TokenType.RPAREN)
                if see(parser, lexer.TokenType.SEMICOLON):
                    advance(parser)
                return
            ty = parse_typeexpr(parser)
            
            # Function
            if see(parser, lexer.TokenType.IDENTIFIER, lexer.TokenType.LPAREN):
                name = parser.token.value
                advance(parser)
                argtys, argnames, is_varargs = parse_function_argument_list(parser)
                skip_function_body(parser)
                return ast.CFunctionDef(ty, name, argtys, argnames, is_varargs)
            elif see(parser, lexer.TokenType.IDENTIFIER):
                # Global variable
                name = parser.token.value
                advance(parser)
                skip_until(parser, lexer.TokenType.SEMICOLON)
                return ast.CGlobalVarDef(ty, name)
            else:
                # Don't know what this is, just skip it
                return None

def parse_module(parser):
    include_guard = None
    if see(parser, lexer.TokenType.PPDIRECTIVE, value='ifndef'):
        tokens = skip_until(parser, lexer.TokenType.PPDIRECTIVE_END)
        include_guard = tokens[1].value

        while not see(parser, lexer.TokenType.PPDIRECTIVE, value='endif'):
            res = parse_top(parser)
            if res is not None:
                parser.defs.append(res)

        to_remove = []
        for x in parser.defs:
            if type(x) == ast.CConstDefine and x.name == include_guard:
                to_remove.append(x)
        parser.defs = [x for x in parser.defs if x not in to_remove]
    else:
        res = parse_top(parser)
        if res is not None:
            parser.defs.append(res)
    return ast.CModuleDef(parser.lexer.filename, parser.defs)


def parse_text(full_filename, filename, text, ignore_tokens, default_macros):
    parser = ParserState(filename, text, ignore_tokens, default_macros)
    module_ast = parse_module(parser)
    assert parser.errors == [], parser.errors
    return module_ast

def parse_file(full_filename, filename, ignore_tokens, default_macros):
    ignore_tokens = ignore_tokens.copy()
    ignore_tokens.add('inline')
    ignore_tokens.add('extern')
    ignore_tokens.add('static')
    with open(full_filename) as f:
        text = f.read()
        return parse_text(full_filename, filename, text, ignore_tokens, default_macros)

if __name__ == '__main__':
    files = [
            "/usr/include/SDL2/begin_code.h",
            "/usr/include/SDL2/close_code.h",
            "/usr/include/SDL2/SDL_assert.h",
            "/usr/include/SDL2/SDL_atomic.h",
            "/usr/include/SDL2/SDL_audio.h",
            "/usr/include/SDL2/SDL_bits.h",
            "/usr/include/SDL2/SDL_blendmode.h",
            "/usr/include/SDL2/SDL_clipboard.h",
            "/usr/include/SDL2/SDL_config.h",
            "/usr/include/SDL2/SDL_cpuinfo.h",
            "/usr/include/SDL2/SDL_egl.h",
            "/usr/include/SDL2/SDL_endian.h",
            "/usr/include/SDL2/SDL_error.h",
            "/usr/include/SDL2/SDL_events.h",
            "/usr/include/SDL2/SDL_filesystem.h",
            "/usr/include/SDL2/SDL_gamecontroller.h",
            "/usr/include/SDL2/SDL_gesture.h",
            "/usr/include/SDL2/SDL_guid.h",
            "/usr/include/SDL2/SDL.h",
            "/usr/include/SDL2/SDL_haptic.h",
            "/usr/include/SDL2/SDL_hidapi.h",
            "/usr/include/SDL2/SDL_hints.h",
            "/usr/include/SDL2/SDL_image.h",
            "/usr/include/SDL2/SDL_joystick.h",
            "/usr/include/SDL2/SDL_keyboard.h",
            "/usr/include/SDL2/SDL_keycode.h",
            "/usr/include/SDL2/SDL_loadso.h",
            "/usr/include/SDL2/SDL_locale.h",
            "/usr/include/SDL2/SDL_log.h",
            "/usr/include/SDL2/SDL_main.h",
            "/usr/include/SDL2/SDL_messagebox.h",
            "/usr/include/SDL2/SDL_metal.h",
            "/usr/include/SDL2/SDL_misc.h",
            "/usr/include/SDL2/SDL_mixer.h",
            "/usr/include/SDL2/SDL_mouse.h",
            "/usr/include/SDL2/SDL_mutex.h",
            "/usr/include/SDL2/SDL_name.h",
            "/usr/include/SDL2/SDL_opengles2_gl2ext.h",
            "/usr/include/SDL2/SDL_opengles2_gl2.h",
            "/usr/include/SDL2/SDL_opengles2_gl2platform.h",
            "/usr/include/SDL2/SDL_opengles2.h",
            "/usr/include/SDL2/SDL_opengles2_khrplatform.h",
            "/usr/include/SDL2/SDL_opengles.h",
            "/usr/include/SDL2/SDL_opengl_glext.h",
            "/usr/include/SDL2/SDL_opengl.h",
            "/usr/include/SDL2/SDL_pixels.h",
            "/usr/include/SDL2/SDL_platform.h",
            "/usr/include/SDL2/SDL_power.h",
            "/usr/include/SDL2/SDL_quit.h",
            "/usr/include/SDL2/SDL_rect.h",
            "/usr/include/SDL2/SDL_render.h",
            "/usr/include/SDL2/SDL_revision.h",
            "/usr/include/SDL2/SDL_rwops.h",
            "/usr/include/SDL2/SDL_scancode.h",
            "/usr/include/SDL2/SDL_sensor.h",
            "/usr/include/SDL2/SDL_shape.h",
            "/usr/include/SDL2/SDL_stdinc.h",
            "/usr/include/SDL2/SDL_surface.h",
            "/usr/include/SDL2/SDL_system.h",
            "/usr/include/SDL2/SDL_syswm.h",
            "/usr/include/SDL2/SDL_test_assert.h",
            "/usr/include/SDL2/SDL_test_common.h",
            "/usr/include/SDL2/SDL_test_compare.h",
            "/usr/include/SDL2/SDL_test_crc32.h",
            "/usr/include/SDL2/SDL_test_font.h",
            "/usr/include/SDL2/SDL_test_fuzzer.h",
            "/usr/include/SDL2/SDL_test.h",
            "/usr/include/SDL2/SDL_test_harness.h",
            "/usr/include/SDL2/SDL_test_images.h",
            "/usr/include/SDL2/SDL_test_log.h",
            "/usr/include/SDL2/SDL_test_md5.h",
            "/usr/include/SDL2/SDL_test_memory.h",
            "/usr/include/SDL2/SDL_test_random.h",
            "/usr/include/SDL2/SDL_thread.h",
            "/usr/include/SDL2/SDL_timer.h",
            "/usr/include/SDL2/SDL_touch.h",
            "/usr/include/SDL2/SDL_ttf.h",
            "/usr/include/SDL2/SDL_types.h",
            "/usr/include/SDL2/SDL_version.h",
            "/usr/include/SDL2/SDL_video.h",
            "/usr/include/SDL2/SDL_vulkan.h",
    ]
    for file in files:
        module = parse_file(file, file, {'SDL_DEPRECATED', 'SDL_SCANF_FORMAT_STRING', 'SDL_INOUT_Z_CAP', 'SDL_OUT_Z_CAP', 'SDL_IN_BYTECAP', 'SDL_OUT_BYTECAP', 'SDLMAIN_DECLSPEC', 'SDL_PRINTF_FORMAT_STRING', 'SDL_FORCE_INLINE', 'DECLSPEC', 'SDLCALL', 'extern', 'SDL_AUDIOCVT_PACKED'})
        import pprint
        pprint.pprint(module)