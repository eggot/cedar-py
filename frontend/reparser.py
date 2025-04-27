from dataclasses import dataclass
from typing import List, Optional, Union
import re
from pprint import pprint
import frontend.astnodes as ast

class RegexParser:
    def __init__(self, regex: str):
        self.regex = regex
        self.pos = 0
        self.current_char = self.regex[self.pos] if self.regex else None

    def advance(self):
        """Advance to the next character in the regex string."""
        self.pos += 1
        if self.pos < len(self.regex):
            self.current_char = self.regex[self.pos]
        else:
            self.current_char = None

    def parse(self) -> ast.RENode:
        """Entry point to start parsing the regex."""
        ast = self.regex_expr()
        if self.current_char is not None:
            raise SyntaxError(f"Unexpected character at position {self.pos}: '{self.current_char}'")
        return ast

    def regex_expr(self) -> ast.RENode:
        """Parse the top-level regex expression, supporting alternation."""
        term = self.regex_term()
        if self.current_char == '|':
            self.advance()
            right = self.regex_expr()
            return ast.REAlternation(left=term, right=right)
        return term

    def regex_term(self) -> ast.RENode:
        """Parse a sequence of factors (e.g., concatenation)."""
        factors = []
        while self.current_char and self.current_char not in '|)':
            factors.append(self.regex_factor())
        return ast.RESequence(factors=factors)

    def regex_factor(self) -> ast.RENode:
        """Parse a factor (a single unit, with possible repetition)."""
        atom = self.regex_atom()
        if self.current_char and self.current_char in '*+?':
            quantifier_char = self.current_char
            self.advance()
            if quantifier_char == '*':
                return ast.REQuantifier(atom=atom, min=0, max=None)
            elif quantifier_char == '+':
                return ast.REQuantifier(atom=atom, min=1, max=None)
            elif quantifier_char == '?':
                return ast.REQuantifier(atom=atom, min=0, max=1)
        elif self.current_char == '{':
            quantifier = self.parse_curly_quantifier()
            return ast.REQuantifier(atom=atom, min=quantifier['min'], max=quantifier['max'])
        return atom

    def regex_atom(self) -> ast.RENode:
        """Parse an atomic unit (character, group, or character class)."""
        if self.current_char == '(':
            return self.regex_group()
        elif self.current_char == '[':
            return self.regex_char_class()
        elif self.current_char == '^':
            self.advance()
            return ast.REAnchor(value='^')
        elif self.current_char == '$':
            self.advance()
            return ast.REAnchor(value='$')
        elif self.current_char == '\\' and self.peek() == 'b':
            self.advance()
            self.advance()
            return ast.REAnchor(value='b')
        elif re.match(r'[a-zA-Z0-9]', self.current_char):
            char = self.current_char
            self.advance()
            return ast.RELiteral(value=char)
        elif self.current_char == '.':
            self.advance()
            return ast.REDot()
        else:
            raise SyntaxError(f"Unexpected character: '{self.current_char}'")

    def regex_group(self) -> ast.RENode:
        """Parse a group expression: (abc), (?:...), or (?<name>...)."""
        assert self.current_char == '('
        self.advance()

        if self.current_char == '?':
            # Check for non-capturing group or named capturing group
            self.advance()

            if self.current_char == ':':
                # Non-capturing group (?:...)
                self.advance()
                group_expr = self.regex_expr()
                if self.current_char != ')':
                    raise SyntaxError(f"Unmatched '(' at position {self.pos}")
                self.advance()
                return group_expr

            elif self.current_char == '<':
                # Named capturing group (?<name>...)
                self.advance()
                name = self.parse_group_name()
                group_expr = self.regex_expr()
                if self.current_char != ')':
                    raise SyntaxError(f"Unmatched '(' at position {self.pos}")
                self.advance()
                return ast.RENamedCapturingGroup(name=name, expr=group_expr)

        # Regular capturing group (abc)
        group_expr = self.regex_expr()
        if self.current_char != ')':
            raise SyntaxError(f"Unmatched '(' at position {self.pos}")
        self.advance()
        return ast.RECapturingGroup(group_expr)

    def regex_char_class(self) -> ast.RECharClass:
        """Parse a character class like [a-z]."""
        assert self.current_char == '['
        self.advance()
        char_class = []
        inverted = False
        if self.current_char == '^':
            inverted = True
            self.advance()
        while self.current_char and self.current_char != ']':
            if self.current_char == '-':
                # Support ranges like a-z
                if len(char_class) > 0 and re.match(r'[a-zA-Z0-9]', self.peek()):
                    start = char_class.pop().value
                    self.advance()
                    end = self.current_char
                    if start >= end:
                        raise SyntaxError(f"Invalid range {start}-{end}")
                    char_class.append((start, end))
                else:
                    char_class.append(('-', '-'))
            else:
                char_class.append((self.current_char, self.current_char))
            self.advance()
        if self.current_char != ']':
            raise SyntaxError(f"Unmatched '[' at position {self.pos}")
        self.advance()
        return ast.RECharClass(inverted, char_class)

    def parse_curly_quantifier(self) -> dict:
        """Parse a {n}, {n,}, or {n,m} quantifier."""
        assert self.current_char == '{'
        self.advance()

        # Parse the lower bound (n)
        lower_bound = self.parse_number()

        upper_bound = None
        if self.current_char == ',':
            self.advance()
            # Optionally parse the upper bound (m)
            if self.current_char.isdigit():
                upper_bound = self.parse_number()

        if self.current_char != '}':
            raise SyntaxError(f"Unmatched '{{' at position {self.pos}")
        self.advance()

        if upper_bound is not None and lower_bound > upper_bound:
            raise SyntaxError(f"Invalid quantifier range {{{lower_bound},{upper_bound}}}")

        return {'min': lower_bound, 'max': upper_bound}

    def parse_number(self) -> int:
        """Parse a number inside a quantifier."""
        num_str = ''
        while self.current_char and self.current_char.isdigit():
            num_str += self.current_char
            self.advance()
        return int(num_str)

    def parse_group_name(self) -> str:
        """Parse the name of a named capturing group (?<name>...)."""
        name = ''
        while self.current_char and self.current_char.isalnum():
            name += self.current_char
            self.advance()
        if self.current_char != '>':
            raise SyntaxError(f"Expected '>' for named capturing group at position {self.pos}")
        self.advance()  # Move past the '>'
        return name

    def peek(self):
        """Peek at the next character without advancing."""
        if self.pos + 1 < len(self.regex):
            return self.regex[self.pos + 1]
        return None


def parse_regex(str):
    return RegexParser(str).parse()

