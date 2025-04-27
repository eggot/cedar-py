import re
from enum import Enum, auto
from dataclasses import dataclass
from frontend.astnodes import Location

class TokenType(Enum):
    BOOL = auto()
    FLOAT = auto()
    INT = auto()
    LET = auto()
    ON = auto()
    UNION = auto()
    SYMBOL = auto()
    STRING = auto()
    REGEX = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    QUESTION = auto()
    NULL = auto()
    EXCLAMATION = auto()
    IF = auto()
    ELSE = auto()
    LPAREN = auto()
    RPAREN = auto()
    COLON = auto()
    SEMICOLON = auto()
    RETURN = auto()
    WHILE = auto()
    FOR = auto()
    CONTINUE = auto()
    BREAK = auto()
    IMPLICIT = auto()
    IN = auto()
    BITINV = auto()
    SHIFT = auto()
    EXPONENT = auto()
    TYPE = auto()
    MATCH = auto()
    CASE = auto()
    CAST = auto()
    OPERATOR = auto()
    WHERE = auto()
    IDENTIFIER = auto()
    ASSIGN = auto()
    IMPORT = auto()
    EXPORT = auto()
    ASSERT = auto()
    PASS = auto()
    DOT = auto()
    EOF = auto()
    ERROR = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    location: Location

class LexerState:
    def __init__(self, filename, text):
        self.filename = filename
        self.text = text + '\n'
        self.line = 1
        self.column = 1
        self.index = 0
        self.line_start = 0
        self.emit_queue = []
        self.paren_stack = 0 # How many parenthesis we're inside
        self.insert_implicit_semicolon_if_newline_next = False
        self.regex_can_follow = False

import codecs

def unescape_string(s: str) -> str:
    # Remove the surrounding quotes
    if s.startswith("'") and s.endswith("'"):
        s = s[1:-1]
    elif s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    
    # Unescape the string content
    return codecs.decode(s, 'unicode_escape')

def lex(state: LexerState) -> Token:
    while True:
        if state.emit_queue:
            return state.emit_queue.pop(0)

        insert_implicit_semicolon_if_newline_next = state.insert_implicit_semicolon_if_newline_next
        state.insert_implicit_semicolon_if_newline_next = False
        
        if len(state.text) == state.index:
            if insert_implicit_semicolon_if_newline_next:
                state.regex_can_follow = False
                return Token(TokenType.SEMICOLON, ';', Location(state.filename, state.line, state.column))
            return Token(TokenType.EOF, "<end of file>", Location(state.filename, state.line, state.column))

        match = None
        if state.regex_can_follow:
            match = REGEX_REGEX.match(state.text, state.index)

        if not match:
            match = TOKEN_REGEX.match(state.text, state.index)
            assert match is not None, state.text[state.index:state.index + 10]
        
        state.index = match.end()
        token_type = match.lastgroup
        token_value = match.group(token_type)
        token_location = Location(state.filename, state.line, match.start() - state.line_start + 1)
        
        if token_type == 'IMPORT':
            token_value = token_value[len('import '):]

        if token_type == 'IGNORE':
            num_newlines = token_value.count("\n")
            state.line += num_newlines
            state.insert_implicit_semicolon_if_newline_next = insert_implicit_semicolon_if_newline_next
            continue
        
        elif token_type == 'ERROR':
            return Token(TokenType.ERROR, token_value, token_location)
        
        elif token_type == 'NEWLINE':
            if insert_implicit_semicolon_if_newline_next:
                state.emit_queue.append(Token(TokenType.SEMICOLON, ';', Location(state.filename, state.line, state.column)))
            state.line += token_value.count("\n")
            state.line_start = state.index
            continue
        
        elif token_type == 'RBRACE' and insert_implicit_semicolon_if_newline_next:
            state.emit_queue.append(Token(TokenType.SEMICOLON, ';', Location(state.filename, state.line, state.column)))
            state.emit_queue.append(Token(TokenType.RBRACE, '}', Location(state.filename, state.line, state.column)))
            state.insert_implicit_semicolon_if_newline_next = True
            continue

        else:
            if token_value in ('(', '['):
                state.paren_stack += 1
            elif token_value in (')', ']') and state.paren_stack > 0:
                state.paren_stack -= 1
            
            token_type_enum = TokenType[token_type]
            if token_type_enum == TokenType.STRING:
                token_value = unescape_string(token_value)

            state.insert_implicit_semicolon_if_newline_next = token_type_enum in INSERT_IMPLICIT_SEMICOLON and state.paren_stack == 0
            state.regex_can_follow = token_type_enum in REGEX_CAN_FOLLOW
            return Token(token_type_enum, token_value, token_location)
        assert False, "should not reach here"


INSERT_IMPLICIT_SEMICOLON = (TokenType.CONTINUE, TokenType.BREAK, TokenType.RETURN, TokenType.RPAREN,
                             TokenType.FLOAT, TokenType.INT, TokenType.STRING, TokenType.IDENTIFIER,
                             TokenType.PASS, TokenType.RBRACKET, TokenType.IMPORT, TokenType.BOOL,
                             TokenType.NULL, TokenType.RBRACE, TokenType.SYMBOL, TokenType.REGEX)

REGEX_CAN_FOLLOW = (TokenType.ASSIGN, TokenType.CASE, TokenType.RETURN, TokenType.ASSERT, TokenType.BREAK, TokenType.CONTINUE,
                    TokenType.LPAREN, TokenType.LBRACKET, TokenType.LBRACE, TokenType.OPERATOR)

def _make_token_regex():
    token_patterns = [
        (r'[ \t]+|//.*(?=\n)', 'IGNORE'),  # Ignore whitespace
        (r'\btrue|false\b', TokenType.BOOL.name),
        (r'\d+\.\d+', TokenType.FLOAT.name),
        (r'\b0b[_01]+|0x[\d_0-9a-fA-F]+|[\d_]+\b', TokenType.INT.name),
        (r'\'(?:\\.|[^\'])*\'|"(?:\\.|[^"])*"', TokenType.STRING.name),
        (r'\[', TokenType.LBRACKET.name),
        (r'\]', TokenType.RBRACKET.name),
        (r'\{', TokenType.LBRACE.name),
        (r'\}', TokenType.RBRACE.name),
        (r',', TokenType.COMMA.name),
        (r'#([a-zA-Z_][a-zA-Z0-9_]*|\'(?:\\.|[^\'])*\'|"(?:\\.|[^"])*")', TokenType.SYMBOL.name),
        (r'\bif\b', TokenType.IF.name),
        (r'\bnull\b', TokenType.NULL.name),
        (r'\belse\b', TokenType.ELSE.name),
        (r'\btype\b', TokenType.TYPE.name),
        (r'\bmatch\b', TokenType.MATCH.name),
        (r'\bcase\b', TokenType.CASE.name),
        (r'\bcast\b', TokenType.CAST.name),
        (r'\blet\b', TokenType.LET.name),
        (r'\bunion\b', TokenType.UNION.name),
        (r'\bon\b', TokenType.ON.name),
        (r'\(', TokenType.LPAREN.name),
        (r'\)', TokenType.RPAREN.name),
        (r'\bassert\b', TokenType.ASSERT.name),
        (r'\breturn\b', TokenType.RETURN.name),
        (r'\bimplicit\b', TokenType.IMPLICIT.name),
        (r'\bwhile\b', TokenType.WHILE.name),
        (r'\bfor\b', TokenType.FOR.name),
        (r'\bin\b', TokenType.IN.name),
        (r'\bcontinue\b', TokenType.CONTINUE.name),
        (r'\bbreak\b', TokenType.BREAK.name),
        (r'\bpass\b', TokenType.PASS.name),
        (r'\.\.|\+|-|\*|/|%|<<|>>|\||\^|&|<=|==|!=|>=|<|>|~|\bnot\b|\band\b|\bor\b', TokenType.OPERATOR.name),
        (r'=', TokenType.ASSIGN.name),
        (r':', TokenType.COLON.name),
        (r';', TokenType.SEMICOLON.name),
        (r'\.', TokenType.DOT.name),
        (r'\?', TokenType.QUESTION.name),
        (r'!', TokenType.EXCLAMATION.name),
        (r'\bwhere\b', TokenType.WHERE.name),
        (r'\bexport\b', TokenType.EXPORT.name),
        (r'import[ \t]+[^\s]+', TokenType.IMPORT.name),
        (r'[a-zA-Z_][a-zA-Z0-9_]*', TokenType.IDENTIFIER.name),
        (r'\n([ \t]*\n)*', 'NEWLINE'),
        (r'[^\s]+', 'ERROR'),
    ]

    return re.compile('|'.join('(?P<%s>%s)' % (pair[1], pair[0]) for pair in token_patterns))
TOKEN_REGEX = _make_token_regex()
REGEX_REGEX = re.compile(r'(?P<REGEX>/([^/\\]+(?:\\.[^/\\]*)*)/)')


if __name__ == '__main__':
    code = """
import foo/bar.ch
import foo/gazonk.ch in bar

type Data(int x, int y)

if x { 1 } else { 2 }
"""
    state = LexerState("filename.ch" ,code)
    while True:
        token = lex(state)
        if token.type == TokenType.EOF:
            break
