from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(eq=True, frozen=True)
class Location:
    filename: str
    line: int
    column: int

@dataclass
class SyntaxError:
    location: Location
    msg: str
    got: str

@dataclass
class ASTNode:
    location: Location = field(compare=False, repr=False, kw_only=True, default=None)

@dataclass
class TypeExpr(ASTNode):
    pass

@dataclass
class Definition(ASTNode):
    pass

@dataclass
class Expr(ASTNode):
    pass

@dataclass
class Stmt(ASTNode):
    pass

    
@dataclass
class NamedType(TypeExpr):
    namespace: str
    name: str

@dataclass
class ArrayType(TypeExpr):
    elty: TypeExpr

@dataclass
class TupleType(TypeExpr):
    positional: List[TypeExpr]
    named: List[TypeExpr]
    names: List[str]

@dataclass
class UnionType(TypeExpr):
    types: List[TypeExpr]
    
@dataclass
class PointerType(TypeExpr):
    target: TypeExpr

@dataclass
class OptionType(TypeExpr):
    target: TypeExpr

@dataclass
class ErrorType(TypeExpr):
    target: TypeExpr

@dataclass
class FunctionType(TypeExpr):
    retty: TypeExpr
    argtys: List[TypeExpr]
    argnames: List[str]


@dataclass
class ModuleDef(Definition):
    filename: str
    defs: List[Definition]
    main_module: bool

@dataclass
class ImportDef(Definition):
    filename: str
    namespace: str
    parameters: 'TupleExpr'

@dataclass
class FunctionDef(Definition):
    export: bool
    retty: TypeExpr
    name: str
    argtys_implicit: List[TypeExpr]
    argnames_implicit: List[str]
    argtys: List[TypeExpr]
    argnames: List[str]
    body: List[Stmt]

@dataclass
class TypeConstructor(ASTNode):
    name: str
    field_types: List[TypeExpr]
    field_names: List[str]
    tag_value: Expr

@dataclass
class TypeDef(Definition):
    export: bool
    name: str
    constructors: List[TypeConstructor]

@dataclass
class VariableDef(Definition):
    export: bool
    ty: TypeExpr
    name: str
    value: Expr


@dataclass
class CTypeExpr(TypeExpr):
    pass

@dataclass
class CDefinition(Definition):
    pass

@dataclass
class CModuleDef(Definition):
    filename: str
    defs: List[CDefinition]

@dataclass
class CVariableDef(CDefinition):
    ty: CTypeExpr
    name: str

@dataclass
class CUnionDef(CDefinition):
    name: str
    field_types: List[CTypeExpr]
    field_names: List[str]

@dataclass
class CStructDef(CDefinition):
    name: str
    field_types: List[CTypeExpr]
    field_names: List[str]

@dataclass
class CEnumDef(CDefinition):
    name: str
    enumerators: List[str]

@dataclass
class CTypedefDef(CDefinition):
    name: str
    definition: CTypeExpr

@dataclass
class CFunctionDef(CDefinition):
    retty: CTypeExpr
    name: str
    argtys: List[CTypeExpr]
    argnames: List[str]
    varargs: bool

@dataclass
class CGlobalVarDef(CDefinition):
    ty: CTypeExpr
    name: str

@dataclass
class CConstDefine(CDefinition):
    ty: CTypeExpr
    name: str
    undefined: bool

@dataclass
class CInclude(CDefinition):
    filename: str

@dataclass
class CNamedType(CTypeExpr):
    name: str
    typekind: str = None # 'struct', 'union', 'union'

@dataclass
class CPointerType(CTypeExpr):
    target: CTypeExpr

@dataclass
class CConstType(CTypeExpr):
    target: CTypeExpr

@dataclass
class CFunctionPointerType(CTypeExpr):
    retty: CTypeExpr
    argtys: List[CTypeExpr]
    argnames: List[str]

@dataclass
class CArrayType(CTypeExpr):
    elty: CTypeExpr

@dataclass
class CAnonymousType(CTypeExpr):
    tydef: CDefinition

@dataclass
class IntegerExpr(Expr):
    value: int

@dataclass
class StringExpr(Expr):
    value: str

@dataclass
class RegexExpr(Expr):
    value: 'RENode'

@dataclass
class SymbolExpr(Expr):
    value: str

@dataclass
class FloatExpr(Expr):
    value: str # NOTE: Keep float as string, because we don't yet know how it should be represented

@dataclass
class IndexExpr(Expr):
    target: Expr
    indices: List[Expr]

@dataclass
class MemberExpr(Expr):
    target: Expr
    member: str

@dataclass
class BoolExpr(Expr):
    value: bool

@dataclass
class NullExpr(Expr):
    pass

@dataclass
class IdentifierExpr(Expr):
    name: str

@dataclass
class NewIdentifierExpr(Expr):
    name: str
    implicit: bool

@dataclass
class WhereExpr(Expr):
    expr: Expr
    stmts: List[Stmt]

@dataclass
class TupleExpr(Expr):
    positional: List[Expr]
    named: List[Expr]
    names: List[str]
    
@dataclass
class ArrayExpr(Expr):
    elems: List[Expr]
    
@dataclass
class ForExpr(Expr):
    iterator: Expr
    iterable: Expr
    body: Stmt

@dataclass
class WhileExpr(Expr):
    cond: Expr
    body: Stmt

@dataclass
class IfExpr(Expr):
    cond: Expr
    true_body: Stmt
    false_body: Stmt

@dataclass
class IfCaseExpr(Expr):
    cond: Expr
    pattern: Expr
    true_body: Stmt
    false_body: Stmt

@dataclass
class CallExpr(Expr):
    func: Expr
    args: TupleExpr
    block: 'BlockStmt'

@dataclass
class TypeOfExpr(Expr):
    expr: Expr

@dataclass
class AllocateExpr(Expr):
    allocator: Expr
    data: Expr

@dataclass
class BinaryOpExpr(Expr):
    lhs: Expr
    op: str
    rhs: Expr

@dataclass
class CastExpr(Expr):
    type: Expr
    expr: Expr


@dataclass
class BinaryElseExpr(Expr):
    lhs: Expr
    stmt: 'BlockStmt'

@dataclass
class UnaryOpExpr(Expr):
    op: str
    expr: Expr

@dataclass
class NoExpr(Expr):
    """
    Used when no expression given, e.g., for 'return'.
    """
    def __repr__(self):
        return "NoExpr"
NoExpr = NoExpr()


@dataclass
class BlockStmt(Stmt):
    stmts: List[Stmt]

@dataclass
class PassStmt(Stmt):
    pass

@dataclass
class BreakStmt(Stmt):
    value: Expr

@dataclass
class ContinueStmt(Stmt):
    value: Expr

@dataclass
class ReturnStmt(Stmt):
    value: Expr

@dataclass
class AssertStmt(Stmt):
    value: Expr

@dataclass
class ExprStmt(Stmt):
    expr: Expr

@dataclass
class AssignStmt(Stmt):
    lhs: Expr
    rhs: Expr




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

@dataclass
class RENamedCapturingGroup(RENode):
    expr: RENode
    name: str

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
