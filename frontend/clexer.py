from enum import Enum, auto
from dataclasses import dataclass
from frontend.astnodes import Location

# Enum for token types
class TokenType(Enum):
    IDENTIFIER = auto()
    PPDIRECTIVE = auto()
    PPDIRECTIVE_END = auto()
    INT_LITERAL = auto()
    FLOAT_LITERAL = auto()
    DOUBLE_LITERAL = auto()
    STRING_LITERAL = auto()
    CHAR_LITERAL = auto()
    OPERATOR = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    SEMICOLON = auto()
    COLON = auto()
    ASSIGN = auto()
    DOT = auto()
    ARROW = auto()
    QUESTION = auto()
    EXCLAMATION = auto()
    AT = auto()
    ELLIPSIS = auto()
    EOF = auto()
    ERROR = auto()

    # Type specifiers
    INT = auto()
    CHAR = auto()
    FLOAT = auto()
    DOUBLE = auto()
    VOID = auto()
    LONG = auto()
    SHORT = auto()
    SIGNED = auto()
    UNSIGNED = auto()
    STRUCT = auto()
    UNION = auto()
    ENUM = auto()

    # Keywords
    AUTO = auto()
    BREAK = auto()
    CASE = auto()
    CONST = auto()
    CONTINUE = auto()
    DEFAULT = auto()
    DO = auto()
    ELSE = auto()
    EXTERN = auto()
    FOR = auto()
    GOTO = auto()
    IF = auto()
    INLINE = auto()
    REGISTER = auto()
    RESTRICT = auto()
    RETURN = auto()
    SIZEOF = auto()
    STATIC = auto()
    SWITCH = auto()
    TYPEDEF = auto()
    VOLATILE = auto()
    WHILE = auto()
    BOOL = auto()
    COMPLEX = auto()
    IMAGINARY = auto()

# Token data class
@dataclass
class Token:
    type: TokenType
    value: str
    location: Location

# Lexer state class
class LexerState:
    def __init__(self, filename, text, ignore_tokens):
        self.filename = filename
        self.text = text + '\n'
        self.ignore_tokens = ignore_tokens
        self.line = 1
        self.column = 1
        self.index = 0
        self.line_start = 0
        self.in_preprocessor_directive = False

# List of keywords and type specifiers
keywords = {
    'auto': TokenType.AUTO, 'break': TokenType.BREAK, 'case': TokenType.CASE, 'const': TokenType.CONST,
    'continue': TokenType.CONTINUE, 'default': TokenType.DEFAULT, 'do': TokenType.DO, 'else': TokenType.ELSE,
    'extern': TokenType.EXTERN, 'for': TokenType.FOR, 'goto': TokenType.GOTO, 'if': TokenType.IF,
    'inline': TokenType.INLINE, 'register': TokenType.REGISTER, 'restrict': TokenType.RESTRICT, 'return': TokenType.RETURN,
    'sizeof': TokenType.SIZEOF, 'static': TokenType.STATIC, 'switch': TokenType.SWITCH, 'typedef': TokenType.TYPEDEF,
    'volatile': TokenType.VOLATILE, 'while': TokenType.WHILE, '_Bool': TokenType.BOOL, '_Complex': TokenType.COMPLEX,
    '_Imaginary': TokenType.IMAGINARY,
    'int': TokenType.INT, 'char': TokenType.CHAR, 'float': TokenType.FLOAT, 'double': TokenType.DOUBLE,
    'void': TokenType.VOID, 'long': TokenType.LONG, 'short': TokenType.SHORT, 'signed': TokenType.SIGNED,
    'unsigned': TokenType.UNSIGNED, 'struct': TokenType.STRUCT, 'union': TokenType.UNION, 'enum': TokenType.ENUM
}

# Set of operators and punctuations
operators = {
    '++', '--', '&&', '||', '>', '<=', '>=', '==', '!=', '<', '<<', '>>', '+', '-', '*', '/', '%', '&', '|', '^', '!', '~', '='
}
    
delimiters = {'(': TokenType.LPAREN, ')': TokenType.RPAREN,
              '[': TokenType.LBRACKET, ']': TokenType.RBRACKET,
              '{': TokenType.LBRACE, '}': TokenType.RBRACE,
               ',': TokenType.COMMA, ';': TokenType.SEMICOLON,
               ':': TokenType.COLON, '.': TokenType.DOT,
               '->': TokenType.ARROW, '?': TokenType.QUESTION,
               '!': TokenType.EXCLAMATION, '@': TokenType.AT}

def skip_until_matching_paren(state):
    matching = 1
    while matching > 0:
        char = state.text[state.index]
        print("skipping", char)
        state.index += 1
        if char == '(':
            matching += 1
        elif char == ')':
            matching -= 1
    print("done skipping", state.text[state.index:state.index+10])

    
def lex(state: LexerState) -> Token:
    while state.index < len(state.text):
        char = state.text[state.index]

        # Handle escaped newlines (backslash followed by a newline)
        if char == '\\' and state.index + 1 < len(state.text) and state.text[state.index + 1] == '\n':
            # Skip both the backslash and the newline
            state.index += 2
            state.line += 1
            state.line_start = state.index
            continue

        # Skip whitespaces
        if char.isspace():
            if char == '\n':
                if state.in_preprocessor_directive:
                    state.in_preprocessor_directive = False
                    state.index += 1
                    state.line += 1
                    state.line_start = state.index
                    return Token(TokenType.PPDIRECTIVE_END, "\n", Location(state.filename, state.line, state.column))
                state.line += 1
                state.line_start = state.index + 1
            state.index += 1
            continue

        # Skip single-line comments
        if state.text.startswith('//', state.index):
            while state.index < len(state.text) and state.text[state.index] != '\n':
                state.index += 1
            continue

        # Skip multi-line comments
        if state.text.startswith('/*', state.index):
            state.index += 2  # Skip the '/*'
            while state.index < len(state.text) and not state.text.startswith('*/', state.index):
                if state.text[state.index] == '\n':
                    state.line += 1
                    state.line_start = state.index + 1
                state.index += 1
            state.index += 2  # Skip the '*/'
            continue

        # Process identifiers and keywords
        if char.isalpha() or char == '_':
            start_index = state.index
            while state.index < len(state.text) and (state.text[state.index].isalnum() or state.text[state.index] == '_'):
                state.index += 1
            value = state.text[start_index:state.index]
            token_type = keywords.get(value, TokenType.IDENTIFIER)
            if value in state.ignore_tokens:
                if state.text[state.index] == '(':
                    state.index += 1
                    skip_until_matching_paren(state)
                continue
            return Token(token_type, value, Location(state.filename, state.line, start_index - state.line_start + 1))

        # Process integer and float literals (including hexadecimals)
        if char.isdigit() or (char == '0' and state.index + 1 < len(state.text) and state.text[state.index + 1].lower() == 'x'):
            start_index = state.index
            has_dot = False
            if state.text[state.index:state.index + 2].lower() == '0x':
                # Hexadecimal literal
                state.index += 2
                while state.index < len(state.text) and (state.text[state.index].isdigit() or state.text[state.index].lower() in 'abcdef'):
                    state.index += 1
                value = state.text[start_index:state.index]
                return Token(TokenType.INT_LITERAL, value, Location(state.filename, state.line, start_index - state.line_start + 1))
            else:
                # Decimal or floating-point literal
                while state.index < len(state.text) and (state.text[state.index].isdigit() or (state.text[state.index] == '.' and not has_dot)):
                    if state.text[state.index] == '.':
                        has_dot = True
                    state.index += 1
                value = state.text[start_index:state.index]
                if state.text[state.index] == 'f':
                    token_type = TokenType.FLOAT_LITERAL
                elif state.text[state.index] == 'd' or has_dot:
                    token_type = TokenType.DOUBLE_LITERAL
                else:
                    token_type = TokenType.INT_LITERAL
                return Token(token_type, value, Location(state.filename, state.line, start_index - state.line_start + 1))

        # Process string literals
        if char == '"':
            start_index = state.index
            state.index += 1
            while state.index < len(state.text) and state.text[state.index] != '"':
                if state.text[state.index] == '\\' and state.index + 1 < len(state.text):
                    state.index += 2  # Skip escaped characters
                else:
                    state.index += 1
            state.index += 1  # Skip closing quote
            value = state.text[start_index + 1:state.index - 1]
            return Token(TokenType.STRING_LITERAL, value, Location(state.filename, state.line, start_index - state.line_start + 1))

        # Process character literals
        if char == "'":
            start_index = state.index
            state.index += 1
            if state.index < len(state.text) and state.text[state.index] == '\\':  # Escape sequence
                state.index += 2
            else:
                state.index += 1
            state.index += 1  # Skip closing quote
            value = state.text[start_index:state.index]
            return Token(TokenType.CHAR_LITERAL, value, Location(state.filename, state.line, start_index - state.line_start + 1))

        # Process operators
        for oplen in (2, 1):
            op = state.text[state.index:state.index + oplen]
            if op in operators:    
                start_index = state.index
                state.index += oplen
                return Token(TokenType.OPERATOR, op, Location(state.filename, state.line, start_index - state.line_start + 1))

        # Elipsis (...)
        if state.text[state.index:state.index + 3] == '...':
            start_index = state.index
            state.index += 3
            return Token(TokenType.ELLIPSIS, '...', Location(state.filename, state.line, start_index - state.line_start + 1))
            
        delim = state.text[state.index]
        if delim in delimiters:    
            ty = delimiters[delim]
            start_index = state.index
            state.index += 1
            return Token(ty, delim, Location(state.filename, state.line, start_index - state.line_start + 1))

        # Handle preprocessor directives
        if char == '#':
            state.index += 1
            while state.text[state.index] in ' \t':
                state.index += 1
            start_index = state.index
            state.index += 1
            state.in_preprocessor_directive = True
            while state.index < len(state.text) and not state.text[state.index].isspace():
                state.index += 1
            value = state.text[start_index:state.index]
            return Token(TokenType.PPDIRECTIVE, value, Location(state.filename, state.line, start_index - state.line_start + 1))

        # Anything else is an error
        start_index = state.index
        state.index += 1
        return Token(TokenType.ERROR, char, Location(state.filename, state.line, start_index - state.line_start + 1))

    # Return EOF at the end of the input
    return Token(TokenType.EOF, "<end of file>", Location(state.filename, state.line, state.index - state.line_start + 1))


# Usage example
if __name__ == '__main__':
    code = open('SDL.h').read()
    state = LexerState("SDL.h", code)
    
    while True:
        token = lex(state)
        if token.type == TokenType.EOF:
            break
        print(token)
