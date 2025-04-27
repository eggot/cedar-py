from dataclasses import dataclass, field
from typing import List, Optional
import frontend.astnodes as ast
import backend.ir as ir

class REBytecodeCompiler:
    ANCHOR_START = 1 # ^
    ANCHOR_END = 2 # $
    ANCHOR_WORD = 3 # \b
    CHARCLASS = 4
    CHARCLASS_INV = 5
    QUANTIFIER = 6
    ALTERNATION = 7
    SEQUENCE = 8
    DOT = 9
    POSITIVE_LOOKAHEAD = 10
    CAPTURING_GROUP = 11

    def __init__(self):
        self.capturing_group_mapping = {}
        self.num_capturing_groups = 0

    def compile(self, ast: ast.RENode) -> List[int]:
        """Compiles the AST into bytecode."""
        bytecode = []
        self._visit(ast, bytecode)
        return bytecode

    def _visit(self, node: ast.RENode, bytecode: List[int]):
        if isinstance(node, ast.RELiteral):
            self._compile_literal(node, bytecode)
        elif isinstance(node, ast.RECharClass):
            self._compile_char_class(node, bytecode)
        elif isinstance(node, ast.RECapturingGroup):
            bytecode.append(self.CAPTURING_GROUP)
            bytecode.append(self.num_capturing_groups)
            self.num_capturing_groups += 1
            self._visit(node.expr, bytecode)
        elif isinstance(node, ast.RENamedCapturingGroup):
            bytecode.append(self.CAPTURING_GROUP)
            bytecode.append(self.num_capturing_groups)
            self.capturing_group_mapping[node.name] = self.num_capturing_groups
            self.num_capturing_groups += 1
            self._visit(node.expr, bytecode)
        elif isinstance(node, ast.REAlternation):
            self._compile_alternation(node, bytecode)
        elif isinstance(node, ast.RESequence):
            bytecode.append(self.SEQUENCE)
            idx = len(bytecode)
            bytecode.append(-1)
            for factor in node.factors:
                self._visit(factor, bytecode)
            bytecode[idx] = len(bytecode) - idx
        elif isinstance(node, ast.REQuantifier):
            self._compile_quantifier(node, bytecode)
        elif isinstance(node, ast.REPositiveLookahead):
            self._compile_positive_lookahead(node, bytecode)
        elif isinstance(node, ast.REAnchor):
            self._compile_anchor(node, bytecode)
        elif isinstance(node, ast.REDot):
            bytecode.append(self.DOT)
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")

    def _compile_literal(self, node: ast.RELiteral, bytecode: List[int]):
        bytecode.append(ord(node.value))

    def _compile_char_class(self, node: ast.RECharClass, bytecode: List[int]):
        bytecode.append(self.CHARCLASS_INV if node.inverted else self.CHARCLASS)
        idx = len(bytecode)
        bytecode.append(-1) # Placeholder
        for char_range in node.ranges:
            bytecode.append(ord(char_range[0]))
            bytecode.append(ord(char_range[1]))
        bytecode[idx] = len(bytecode) - idx

    def _compile_quantifier(self, node: ast.REQuantifier, bytecode: List[int]):
        bytecode.append(self.QUANTIFIER)
        bytecode.append(node.min)
        bytecode.append(node.max if node.max is not None else 255)  # 255 for unlimited
        self._visit(node.atom, bytecode)

    def _compile_positive_lookahead(self, node: ast.REPositiveLookahead, bytecode: List[int]):
        bytecode.append(self.POSITIVE_LOOKAHEAD)
        self._visit(node.expr, bytecode)

    def _compile_alternation(self, node: ast.REAlternation, bytecode: List[int]):
        bytecode.append(self.ALTERNATION)
        self._visit(node.left, bytecode)
        idx = len(bytecode)
        bytecode.append(-1) # PLACEHOLDER for "goto"
        self._visit(node.right, bytecode)
        bytecode[idx] = len(bytecode) - idx

    def _compile_anchor(self, node: ast.REAnchor, bytecode: List[int]):
        if node.value == '^':
            bytecode.append(self.ANCHOR_START)
        elif node.value == '$':
            bytecode.append(self.ANCHOR_END)
        elif node.value == 'b':
            bytecode.append(self.ANCHOR_WORD)
        else:
            assert False, node

def compile_regex(reast):
    compiler = REBytecodeCompiler()
    return compiler.compile(reast), compiler.num_capturing_groups, compiler.capturing_group_mapping