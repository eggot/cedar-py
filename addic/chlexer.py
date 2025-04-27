import re
from enum import Enum, auto
from dataclasses import dataclass
from typing import Generator, List, Union
form chast import Location

class TokenType(Enum):
    BOOL = auto()
    FLOAT = auto()
    INT = auto()
    STRING = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    QUESTION = auto()
    IF = auto()
    FN = auto()
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
    OPERATOR = auto()
    WHERE = auto()
    IDENTIFIER = auto()
    ASSIGN = auto()
    IMPORT = auto()
    EXPORT = auto()
    INDENT = auto()
    DEDENT = auto()
    PASS = auto()
    DOT = auto()
    EOF = auto()
    ERROR = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    location: Location

def lex(source: str, start_line=1) -> Generator[Token, None, None]:
    source = source + '\n'
    INSERT_IMPLICIT_SEMICOLON = (TokenType.CONTINUE, TokenType.BREAK, TokenType.RETURN, TokenType.RPAREN,
                                 TokenType.FLOAT, TokenType.INT, TokenType.STRING, TokenType.IDENTIFIER,
                                 TokenType.PASS, TokenType.RBRACKET, TokenType.IMPORT, TokenType.BOOL)
    # Define the regular expression patterns for each token type
    token_patterns = [
        (r'true|false', TokenType.BOOL.name),
        (r'\d+\.\d+', TokenType.FLOAT.name),
        (r'\b\d+|0b[01]+|0x[\da-fA-F]+\b', TokenType.INT.name),
        (r'\'(?:\\.|[^\'])*\'|"(?:\\.|[^"])*"', TokenType.STRING.name),
        (r'\[', TokenType.LBRACKET.name),
        (r'\]', TokenType.RBRACKET.name),
        (r'\{', TokenType.LBRACE.name),
        (r'\}', TokenType.RBRACE.name),
        (r',', TokenType.COMMA.name),
        (r'\?', TokenType.QUESTION.name),
        (r'\bif\b', TokenType.IF.name),
        (r'\bfn\b', TokenType.FN.name),
        (r'\belse\b', TokenType.ELSE.name),
        (r'\btype\b', TokenType.TYPE.name),
        (r'\match\b', TokenType.MATCH.name),
        (r'\bcase\b', TokenType.CASE.name),
        (r'\(', TokenType.LPAREN.name),
        (r'\)', TokenType.RPAREN.name),
        (r'\breturn\b', TokenType.RETURN.name),
        (r'\bimplicit\b', TokenType.IMPLICIT.name),
        (r'\bwhile\b', TokenType.WHILE.name),
        (r'\bfor\b', TokenType.FOR.name),
        (r'\bin\b', TokenType.IN.name),
        (r'\bcontinue\b', TokenType.CONTINUE.name),
        (r'\bbreak\b', TokenType.BREAK.name),
        (r'\bpass\b', TokenType.PASS.name),
        (r'\.\.|\+|-|\*|/|%|<<|>>|\||\^|&|<|<=|==|!=|>=|>|~|\bnot\b|\band\b|\bor\b|', TokenType.OPERATOR.name),
        (r'=', TokenType.ASSIGN.name),
        (r': ', TokenType.COLON.name),
        (r';', TokenType.SEMICOLON.name),
        (r'\.', TokenType.DOT.name),
        (r'\bwhere\b', TokenType.WHERE.name),
        (r'\bexport\b', TokenType.EXPORT.name),
        (r'import[ \t]+[^\s]+', TokenType.IMPORT.name),
        (r'[a-zA-Z_][a-zA-Z0-9_]*', TokenType.IDENTIFIER.name),
        (r'\n([ \t]*\n)*', 'NEWLINE'),
        (r'[ \t]+|#.*(?=\n)', 'IGNORE'),  # Ignore whitespace
        (r'[^\s]+', 'ERROR'),
    ]

    token_regex = '|'.join('(?P<%s>%s)' % (pair[1], pair[0]) for pair in token_patterns)
    line_start = 0
    indentation_stack = [0]
    prev_token = None

    paren_stack = []
    location = Location(1, 1)
    for mo in re.finditer(token_regex, source):
        if mo.group(0) in ('(', '[', '{'):
            paren_stack.append(mo.group(0))
        elif mo.group(0) in (')', ']', '}') and len(paren_stack) > 0:
            paren_stack.pop()

        token_type = mo.lastgroup
        if mo.lastgroup == 'IGNORE':
            continue
        if token_type == 'ERROR':
            #print("Not reconized token: ", mo.group(0))
            #assert False, mo.group(0)
            yield Token(TokenType.ERROR, mo.group(token_type), location)
        elif token_type is not None:
            value = mo.group(token_type)
            location = Location(line=source.count('\n', 0, mo.start()) + start_line, column=mo.start() - line_start + 1)

            if token_type == "NEWLINE":
                if token_type == "NEWLINE" and prev_token in INSERT_IMPLICIT_SEMICOLON:
                    prev_token = None
                    yield Token(TokenType.SEMICOLON, value, location)
                line_start = mo.end()
                # Calculate the new indentation level
                indent = len(re.match(r' *', source[mo.end():]).group(0))
                prev_indent = indentation_stack[-1]

                if indent > prev_indent and len(paren_stack) == 0:
                    yield Token(TokenType.INDENT, '<indent>', location)
                    indentation_stack.append(indent)
                elif indent < prev_indent and len(paren_stack) == 0:
                    while indent < prev_indent:
                        yield Token(TokenType.DEDENT, '<dedent>', location)
                        indentation_stack.pop()
                        prev_indent = indentation_stack[-1]

            else:
                t = TokenType[token_type]
                prev_token = t
                yield Token(t, value, location)

    if prev_token in INSERT_IMPLICIT_SEMICOLON:
        yield Token(TokenType.SEMICOLON, value, location)

    yield Token(TokenType.EOF, "<end of file>", location)
