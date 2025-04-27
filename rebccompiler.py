from typing import List, Optional
from dataclasses import dataclass

@dataclass
class RENode:
    pass

@dataclass
class RELiteral(RENode):
    value: str

@dataclass
class REDot(RENode):
    """Match any value"""

@dataclass
class RECharClass(RENode):
    inverted: bool
    ranges: List['(str, str)']

@dataclass
class RECapturingGroup(RENode):
    expr: RENode
    group_number: int

@dataclass
class REPositiveLookahead(RENode):
    expr: RENode

@dataclass
class REAlternation(RENode):
    left: RENode
    right: RENode

@dataclass
class RESequence(RENode):
    factors: List[RENode]

@dataclass
class REQuantifier(RENode):
    atom: RENode
    min: int
    max: Optional[int] = None

@dataclass
class REAnchor(RENode):
    value: str  # '^', '$', 'b'

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

    def compile(self, ast: RENode) -> List[int]:
        """Compiles the AST into bytecode."""
        bytecode = []
        self._visit(ast, bytecode)
        return bytecode

    def _visit(self, node: RENode, bytecode: List[int]):
        if isinstance(node, RELiteral):
            self._compile_literal(node, bytecode)
        elif isinstance(node, RECharClass):
            self._compile_char_class(node, bytecode)
        elif isinstance(node, RECapturingGroup):
            bytecode.append(self.CAPTURING_GROUP)
            bytecode.append(node.group_number)
            self._visit(node.expr, bytecode)
        elif isinstance(node, REAlternation):
            self._compile_alternation(node, bytecode)
        elif isinstance(node, RESequence):
            bytecode.append(self.SEQUENCE)
            idx = len(bytecode)
            bytecode.append(-1)
            for factor in node.factors:
                self._visit(factor, bytecode)
            bytecode[idx] = len(bytecode) - idx
        elif isinstance(node, REQuantifier):
            self._compile_quantifier(node, bytecode)
        elif isinstance(node, REPositiveLookahead):
            self._compile_positive_lookahead(node, bytecode)
        elif isinstance(node, REAnchor):
            self._compile_anchor(node, bytecode)
        elif isinstance(node, REDot):
            bytecode.append(self.DOT)
        else:
            raise ValueError(f"Unsupported node type: {type(node)}")

    def _compile_literal(self, node: RELiteral, bytecode: List[int]):
        bytecode.append(ord(node.value))

    def _compile_char_class(self, node: RECharClass, bytecode: List[int]):
        bytecode.append(self.CHARCLASS_INV if node.inverted else self.CHARCLASS)
        idx = len(bytecode)
        bytecode.append(-1) # Placeholder
        for char_range in node.ranges:
            bytecode.append(ord(char_range[0]))
            bytecode.append(ord(char_range[1]))
        bytecode[idx] = len(bytecode) - idx

    def _compile_quantifier(self, node: REQuantifier, bytecode: List[int]):
        bytecode.append(self.QUANTIFIER)
        bytecode.append(node.min)
        bytecode.append(node.max if node.max is not None else 255)  # 255 for unlimited
        self._visit(node.atom, bytecode)

    def _compile_positive_lookahead(self, node: REPositiveLookahead, bytecode: List[int]):
        bytecode.append(self.POSITIVE_LOOKAHEAD)
        self._visit(node.expr, bytecode)

    def _compile_alternation(self, node: REAlternation, bytecode: List[int]):
        bytecode.append(self.ALTERNATION)
        self._visit(node.left, bytecode)
        idx = len(bytecode)
        bytecode.append(-1) # PLACEHOLDER for "goto"
        self._visit(node.right, bytecode)
        bytecode[idx] = len(bytecode) - idx

    def _compile_anchor(self, node: REAnchor, bytecode: List[int]):
        if node.value == '^':
            bytecode.append(self.ANCHOR_START)
        elif node.value == '$':
            bytecode.append(self.ANCHOR_END)
        elif node.value == 'b':
            bytecode.append(self.ANCHOR_WORD)
        else:
            assert False, node

### Bytecode Decompiler

class REBytecodeDecompiler:
    def __init__(self):
        self.index = 0  # Tracks the current index in the bytecode list
        self.bytecode = []

    def decompile(self, bytecode: List[int]) -> RENode:
        """Decompiles the bytecode back into an AST."""
        self.bytecode = bytecode
        self.index = 0
        return self._parse()

    def _parse(self) -> RENode:
        """Parses the bytecode into an AST recursively."""
        instr = self.bytecode[self.index]

        if instr == REBytecodeCompiler.ANCHOR_START:
            self.index += 1
            return REAnchor('^')

        elif instr == REBytecodeCompiler.ANCHOR_END:
            self.index += 1
            return REAnchor('$')

        elif instr == REBytecodeCompiler.ANCHOR_WORD:
            self.index += 1
            return REAnchor('b')

        elif instr == REBytecodeCompiler.CHARCLASS:
            return self._parse_char_class()

        elif instr == REBytecodeCompiler.QUANTIFIER:
            return self._parse_quantifier()

        elif instr == REBytecodeCompiler.POSITIVE_LOOKAHEAD:
            return self._parse_positive_lookahead()

        elif instr == REBytecodeCompiler.ALTERNATION:
            return self._parse_alternation()
        
        elif instr == REBytecodeCompiler.DOT:
            self.index += 1
            return REDot()

        elif instr == REBytecodeCompiler.SEQUENCE:
            end = self.bytecode[self.index + 1] + self.index
            self.index += 2
            nodes = []
            while self.index < end:
                nodes.append(self._parse())
            return RESequence(nodes)
        else:
            # Assume it's a literal character
            self.index += 1
            return RELiteral(chr(instr))


    def _parse_char_class(self) -> RECharClass:
        """Parses a character class from bytecode."""
        self.index += 1  # Skip CHARCLASS instruction
        ranges = []
        chars = []
        
        while self.bytecode[self.index] != REBytecodeCompiler.CHARCLASS_END:
            start = chr(self.bytecode[self.index])
            end = chr(self.bytecode[self.index + 1])
            if start == end:
                chars.append(start)
            else:
                ranges.append(RECharRange(start=start, end=end))
            self.index += 2
        
        self.index += 1  # Skip CHARCLASS_END
        return RECharClass(ranges=ranges, chars=chars)

    def _parse_quantifier(self) -> REQuantifier:
        """Parses a quantifier from bytecode."""
        self.index += 1  # Skip QUANTIFIER instruction
        min_val = self.bytecode[self.index]
        max_val = self.bytecode[self.index + 1]
        max_val = None if max_val == 255 else max_val
        self.index += 2
        
        atom = self._parse()  # The quantifier applies to the next node
        return REQuantifier(atom=atom, min=min_val, max=max_val)

    def _parse_positive_lookahead(self) -> REPositiveLookahead:
        """Parses a positive lookahead from bytecode."""
        self.index += 1  # Skip POSITIVE_LOOKAHEAD instruction       
        atom = self._parse()  # The lookahead applies to the next node
        return REPositiveLookahead(atom=atom)

    def _parse_alternation(self) -> REAlternation:
        """Parses an alternation from bytecode."""
        self.index += 1  # Skip ALTERNATION instruction
        left = self._parse()  # Parse left side
        self.index += 1 # Skip the "goto"
        right = self._parse()  # Parse right side
        return REAlternation(left=left, right=right)


@dataclass(frozen=True)
class MatchResult:
    pc: int
    sp: int
    matched: bool
    groups: int # bitmask of assigned groups

def bc_match(bytecode, string):
    captures = {}
    final_s = _bc_match(bytecode, string, 0, 0, captures)
    for i in sorted(captures.keys()):
        if (1 << i) & final_s.groups:
            print("%d: %s" % (i, captures[i]))
    return final_s.matched

def bc_is_word_char(s):
    x = ord(s)
    return ord('a') <= x <= ord('z') or ord('A') <= ord('Z') or ord('0') <= x <= ord('9') or s == '_'

def _bc_match(bytecode, string, pc, sp, captures):
    instr = bytecode[pc]

    if instr == REBytecodeCompiler.SEQUENCE:
        end = bytecode[pc + 1] + pc + 1
        pc += 2
        groups = 0
        while pc < end:
            s = _bc_match(bytecode, string, pc, sp, captures)
            pc = s.pc
            sp = s.sp
            if not s.matched:
                return MatchResult(end, sp, False, 0)
            groups |= s.groups
        return MatchResult(end, sp, True, groups)
    elif instr == REBytecodeCompiler.CHARCLASS or instr == REBytecodeCompiler.CHARCLASS_INV:
        end = bytecode[pc + 1] + pc + 1
        if sp >= len(string):
            return MatchResult(end, sp, False, 0)
        pc += 2
        val = ord(string[sp])
        matched = False
        early_exit = MatchResult(end, sp + 1, True, 0)
        regular_exit = MatchResult(end, sp, False, 0)
        if instr == REBytecodeCompiler.CHARCLASS_INV:
            early_exit, regular_exit = regular_exit, early_exit
        while pc < end:
            lower = bytecode[pc]
            upper = bytecode[pc + 1]
            pc += 2
            if lower <= val <= upper:
                return early_exit
        return regular_exit
    elif instr == REBytecodeCompiler.QUANTIFIER:
        mn = bytecode[pc + 1]
        mx = bytecode[pc + 2]
        count = 0
        pc += 3
        groups = 0
        while count < mn:
            s = _bc_match(bytecode, string, pc, sp, captures)
            if not s.matched:
                return MatchResult(s.pc, sp, False, 0)
            sp = s.sp
            count += 1
            groups |= s.groups
        
        while mx == 255 or count < mx:
            s = _bc_match(bytecode, string, pc, sp, captures)
            if not s.matched:
                break
            sp = s.sp
            count += 1
            groups |= s.groups
        return MatchResult(s.pc, sp, True, groups)
    elif instr == REBytecodeCompiler.ALTERNATION:
        left_s = _bc_match(bytecode, string, pc + 1, sp, captures)
        if left_s.matched:
            pc = bytecode[left_s.pc] + left_s.pc # Skip RHS
            return MatchResult(pc, left_s.sp, True, left_s.groups)
        return _bc_match(bytecode, string, left_s.pc + 1, sp, captures)
    elif instr == REBytecodeCompiler.ANCHOR_START:
        return MatchResult(pc + 1, sp, sp == 0, 0)
    elif instr == REBytecodeCompiler.ANCHOR_END:
        return MatchResult(pc + 1, sp, sp == len(string), 0)
    elif instr == REBytecodeCompiler.ANCHOR_WORD:
        if sp == 0 or sp == len(string):
            result = True
        else:
            result = bc_is_word_char(string[sp - 1]) ^ bc_is_word_char(string[sp])
        return MatchResult(pc + 1, sp, result, 0)
    elif instr == REBytecodeCompiler.DOT:
        if sp + 1 < len(string):
            return MatchResult(pc + 1, sp + 1, True, 0)
        return MatchResult(pc + 1, sp, False, 0)
    elif instr == REBytecodeCompiler.POSITIVE_LOOKAHEAD:
        result = _bc_match(bytecode, string, pc + 1, sp, captures)
        return MatchResult(result.pc, sp, result.matched, result.groups)
    elif instr == REBytecodeCompiler.CAPTURING_GROUP:
        group_number = bytecode[pc + 1]
        result = _bc_match(bytecode, string, pc + 2, sp, captures)
        g = 0
        if result.matched:
            captures[group_number] = string[sp:result.sp]
            g = (1 << group_number)
        return MatchResult(result.pc, result.sp, result.matched, result.groups | g)
    else:
        # Everything else is a literal character
        m = sp < len(string) and string[sp] == chr(instr)
        return MatchResult(pc + 1, sp + 1, m, 0)



### Example usage
if 1:
    regex_ast = RESequence([RELiteral('a'), REQuantifier(REAlternation(RELiteral('_'), REAlternation(RELiteral('b'), RELiteral('B'))), 1, 4), RELiteral('c'), REDot(), RELiteral('z'), REAnchor('$')])
    compiler = REBytecodeCompiler()
    bytecode = compiler.compile(regex_ast)
    print("Compiled Bytecode:", bytecode)

    print(bc_match(bytecode, "ab"))
    print(bc_match(bytecode, "c"))
    print(bc_match(bytecode, "abbc z"))
    print(bc_match(bytecode, "aBbc z"))
    print(bc_match(bytecode, "abBbc z"))
    print(bc_match(bytecode, "abB_bc8zq"))

    regex_ast = RESequence([REQuantifier(REAlternation(RELiteral('a'), RELiteral('b')), 1, 4), REAnchor('b')])
    compiler = REBytecodeCompiler()
    bytecode = compiler.compile(regex_ast)
    print("Compiled Bytecode:", bytecode)

    print(bc_match(bytecode, "ab"))
    print(bc_match(bytecode, "aaba"))
    print(bc_match(bytecode, "aabac"))

    regex_ast = RESequence([REQuantifier(REAlternation(RELiteral('a'), RELiteral('b')), 1, 4), REPositiveLookahead(RELiteral('c'))])
    compiler = REBytecodeCompiler()
    bytecode = compiler.compile(regex_ast)
    print("Compiled Bytecode:", bytecode)

    print(bc_match(bytecode, "ab"))
    print(bc_match(bytecode, "aaba"))
    print(bc_match(bytecode, "aabac"))

    regex_ast = RECapturingGroup(RESequence([RELiteral('a'), RELiteral('b'), RELiteral('c')]), 0)
    compiler = REBytecodeCompiler()
    bytecode = compiler.compile(regex_ast)
    print("Compiled Bytecode:", bytecode)

    print(bc_match(bytecode, "ab"))
    print(bc_match(bytecode, "abc"))

    regex_ast = RECapturingGroup(REQuantifier(RECharClass(True, [('a', 'c'), ('0', '6')]), 1, 10), 0)
    compiler = REBytecodeCompiler()
    bytecode = compiler.compile(regex_ast)
    print("Compiled Bytecode:", bytecode)

    print(bc_match(bytecode, "a"))
    print(bc_match(bytecode, "6543210"))
    print(bc_match(bytecode, "987"))

    print("--")
    bytecode = [8, 18, 6, 1, 255, 11, 0, 7, 8, 4, 102, 111, 111, 6, 8, 4, 98, 97, 114]
    print(bc_match(bytecode, "foobar"))
