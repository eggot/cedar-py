from dataclasses import dataclass
from typing import List, Optional

@dataclass(eq=True, frozen=True)
class Location:
    line: int
    column: int

@dataclass
class ASTNode:
    location: Location

@dataclass
class TypeExpr(ASTNode):
    pass

@dataclass
class NamedType(TypeExpr):
    name: str

@dataclass
class ArrayType(TypeExpr):
    elty: TypeExpr

@dataclass
class TupleType(TypeExpr):
    unnamed: List[TypeExpr]
    named: List[TypeExpr]
    names: List[str]

@dataclass
class PointerType(TypeExpr):
    target: TypeExpr

@dataclass
class OptionalType(TypeExpr):
    target: TypeExpr

@dataclass
class ErrorType(TypeExpr):
    target: TypeExpr






@dataclass
class GlobalDef(ASTNode):
    pass

@dataclass
class Expr(ASTNode):
    pass

@dataclass
class Stmt(ASTNode):
    pass

@dataclass
class Module:
    body: List[ASTNode]

@dataclass
class Argument(ASTNode):
    name: str
    type: TypeExpr
    implicit: bool

@dataclass
class Constructor(ASTNode):
    name: str
    fields: List[Argument]
    without_arglist: bool
    exported: bool

@dataclass
class TypeDefinition(GlobalDef):
    name: str
    constructors: List[Constructor]
    type_parameters: List[str]
    exported: bool


@dataclass
class BoolLiteralExpr(Expr):
    value: bool

@dataclass
class FloatLiteralExpr(Expr):
    value: float

@dataclass
class IntLiteralExpr(Expr):
    value: int

@dataclass
class StringLiteralExpr(Expr):
    value: str

@dataclass
class IdentExpr(Expr):
    name: str

@dataclass
class BinaryOpExpr(Expr):
    op: str
    lhs: Expr
    rhs: Expr

@dataclass
class ComparisonExpr(Expr):
    op: str
    lhs: Expr
    rhs: Expr

@dataclass
class IfExpr(Expr):
    cond: Expr
    ontrue: Expr
    onfalse: Expr

@dataclass
class WhereExpr(Expr):
    expr: Expr
    body: Stmt

@dataclass
class TupleExpr(Expr):
    unnamed: List[Expr]
    named: List[Expr]
    names: List[str]

@dataclass
class FunctionCallExpr(Expr):
    func: Expr
    args: TupleExpr

@dataclass
class ElementwiseFunctionCallExpr(Expr):
    func: Expr
    args: TupleExpr

@dataclass
class ReduceFunctionCallExpr(Expr):
    func: Expr
    args: TupleExpr

@dataclass
class NewExpr(Expr):
    ctorname: str
    args: TupleExpr

@dataclass
class ListLiteralExpr(Expr):
    elems: List[Expr]

@dataclass
class IndexExpr(Expr):
    target: Expr
    index: Expr

@dataclass
class SliceExpr(Expr):
    target: Expr
    begin_index: Expr
    end_index: Expr

@dataclass
class FieldAccessExpr(Expr):
    target: Expr
    field: str

@dataclass
class ElementwiseFieldAccessExpr(Expr):
    target: Expr
    field: str

@dataclass
class UnaryOpExpr(Expr):
    op: str
    expr: Expr

@dataclass
class FunctionDef(GlobalDef):
    name: str
    arguments: List[Argument]
    returntype: TypeExpr
    body: Stmt
    type_parameters: List[str]
    exported: bool

@dataclass
class InterfaceFunction(GlobalDef):
    name: str
    arguments: List[Argument]
    returntype: TypeExpr

@dataclass
class GlobalVariableDef(GlobalDef):
    name: str
    type: TypeExpr
    value: Expr
    exported: bool

@dataclass
class ImportDef(GlobalDef):
    filename: str
    # Only one of these two fields can be used at once
    imported_names: List[str]
    local_name: str

@dataclass
class VariableDecl(ASTNode):
    type: TypeExpr
    name: str
    implicit: bool
    
@dataclass
class VariableAssignmentStmt(Stmt):
    variable: VariableDecl
    init: Expr

@dataclass
class FieldAssignmentStmt(Stmt):
    target: Expr
    field: str
    value: Expr

@dataclass
class IndexAssignmentStmt(Stmt):
    target: Expr
    index: Expr
    value: Expr

@dataclass
class ExprStmt(Stmt):
    expr: Expr

@dataclass
class ReturnStmt(Stmt):
    value: Expr

@dataclass
class BlockStmt(Stmt):
    stmts: List[Stmt]

@dataclass
class ContinueStmt(Stmt):
    pass

@dataclass
class BreakStmt(Stmt):
    pass

@dataclass
class PassStmt(Stmt):
    pass


@dataclass
class SwitchCase:
    # NOTE: if match_expr == None, then this is the default case.
    expr: Optional[Expr]
    cond: Optional[Expr]
    body: Stmt

@dataclass
class SwitchStmt(Expr):
    expr: Expr
    cases: List[SwitchCase]

@dataclass
class WhileStmt(Stmt):
    cond: Expr
    body: Stmt

@dataclass
class IfStmt(Stmt):
    cond: Expr
    body: Stmt
    elsebody: Stmt

@dataclass
class ForStmt(Stmt):
    variable: VariableDecl
    iter: Expr
    body: Stmt
