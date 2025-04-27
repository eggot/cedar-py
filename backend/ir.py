from dataclasses import dataclass, field
from typing import List, Optional
from frontend.astnodes import Location


@dataclass(eq=True, frozen=True)
class Type:
    pass

@dataclass(eq=True, frozen=True)
class CType:
    pass

@dataclass(eq=True, frozen=True)
class Instruction:
    location: Location = field(compare=False, repr=False, kw_only=True, default=None)

@dataclass(eq=True, frozen=True)
class InstructionWithType(Instruction):
    ty: Type

@dataclass(eq=True, frozen=True)
class UntypedNull(Instruction):
    """
    Used only during typchecking; will not occur in typechecked IR.
    """


@dataclass(eq=True, frozen=True)
class CompileError(Instruction):
    """
    A special instruction that indicates that there was a type-checking error
    at this point in the program.
    """
    description: str

    def __repr__(self):
        return f"CompileError({self.description}, {self.location})"


@dataclass(eq=True, frozen=True)
class FunctionDefinition:
    filename: str
    retty: Type
    name: str
    argtys_implicit: List[Type]
    argnames_implicit: List[str]
    argtys: List[Type]
    argnames: List[str]
    body: List[Instruction]
    exported: bool

@dataclass(eq=True, frozen=True)
class GlobalVariableDefinition:
    filename: str
    ty: Type
    name: str
    value: Instruction

@dataclass(eq=True, frozen=True)
class TypeConstructor:
    name: str
    field_types: List[Type]
    field_names: List[str]
    without_arglist: bool

    # The order of the fields in memory might be different than
    # the order given when the constructor is called (to reduce padding).
    # Also, these lists might contain more elements as the padding is
    # explicit here.
    layout_types: List[Type]
    layout_names: List[str]

    # TODO: We only support integer tag values at the moment.
    tag_value: int

@dataclass(eq=True, frozen=True)
class TypeDefinition(Type):
    filename: str
    name: str
    constructors: List[TypeConstructor]
    common_names: List[str]
    exported: bool
    tagless: bool
    optimize_layout: bool = True

    def __hash__(self):
        return hash((self.filename, self.name))


@dataclass(eq=True, frozen=True)
class CConstType(CType):
    target: Type

@dataclass(eq=True, frozen=True)
class CStructDefinition(CType):
    filename: str
    name: str
    field_types: List[Type]
    field_names: List[str]

    # The order of the the field in memory is the same as the order given in the source,
    # however, the lists below have padding explicit.
    layout_types: List[Type]
    layout_names: List[str]

@dataclass(eq=True, frozen=True)
class CTypedefDefinition(CType):
    filename: str
    name: str
    definition: 'CType'

@dataclass(eq=True, frozen=True)
class CUnionDefinition(CType):
    filename: str
    name: str
    field_types: List[Type]
    field_names: List[str]

@dataclass(eq=True, frozen=True)
class CEnumDefinition(CType):
    filename: str
    name: str
    enumerators: List[str]

@dataclass(eq=True, frozen=True)
class CFunctionDefinition:
    filename: str
    retty: Type
    name: str
    argtys: List[Type]
    argnames: List[str]
    varargs: bool

@dataclass(eq=True, frozen=True)
class CGlobalVariableDefinition:
    filename: str
    ty: Type
    name: str
    has_address: bool
    assignable: bool

@dataclass(eq=True, frozen=True)
class Namespace:
    name: str
    modules: List['ModuleDefinition']

@dataclass(eq=True, frozen=True)
class ModuleDefinition:
    filename: str
    functions: List[FunctionDefinition]
    variables: List[GlobalVariableDefinition]
    types: List[TypeDefinition]
    namespaces: List[Namespace]
    main_module: bool


@dataclass(eq=True, frozen=True)
class PaddingType(Type):
    """
    The entire memory area where a struct instance is stored is completely
    initialized (there are no uninitialied padding bytes as in C). This enables
    the compiler to use memcmp for comparisons, but it forces the backend to emit
    initialization code for padding bytes. This type is used for those fields of
    a struct that are padding.
    """
    bytes: int

@dataclass(eq=True, frozen=True)
class UninferredType(Type):
    pass

@dataclass(eq=True, frozen=True)
class IntegerType(Type):
    bits: int
    signed: bool

@dataclass(eq=True, frozen=True)
class FloatType(Type):
    bits: int

@dataclass(eq=True, frozen=True)
class BoolType(Type):
    pass

@dataclass(eq=True, frozen=True)
class VoidType(Type):
    pass

@dataclass(eq=True, frozen=True)
class ExitType(Type):
    """
    This type is used to communicate that a code path is exited and does not yield a value.
    For example, 'return', 'break', and 'continue', have this type.
    """
    pass

@dataclass(eq=True, frozen=True)
class PointerType(Type):
    target: Type

@dataclass(eq=True, frozen=True)
class OptionType(Type):
    target: Type

@dataclass(eq=True, frozen=True)
class UnionType(Type):
    types: List[Type]

@dataclass(eq=True, frozen=True)
class ArrayType(Type):
    elty: 'Type'

@dataclass(eq=True, frozen=True)
class TupleType(Type):
    positional: List[Type]
    named: List[Type]
    names: List[str]

    # The order of the fields in memory might be different than
    # the order given when the constructor is called (to reduce padding).
    # Also, these lists might contain more elements as the padding is
    # explicit here.
    layout_types: List[Type]
    layout_names: List['str|int']

@dataclass(eq=True, frozen=True)
class FunctionType(Type):
    retty: Type
    argtys: List[Type]
    argnames: List[str]

@dataclass(eq=True, frozen=True)
class RttiType(Type):
    pass

@dataclass(eq=True, frozen=True)
class CNamedType(Type):
    name: str
    typekind: str

@dataclass(eq=True, frozen=True)
class CArrayType(Type):
    elty: 'CType'

@dataclass(eq=True, frozen=True)
class CFunctionPointerType(Type):
    retty: Type
    argtys: List[Type]
    argnames: List[str]
    varargs: bool

@dataclass(eq=True, frozen=True)
class CUnknownType(Type):
    name: str
    typekind: str


@dataclass(eq=True, frozen=True)
class DeclareLocal(Instruction):
    declare_type: Type
    name: str

@dataclass(eq=True, frozen=True)
class StoreLocal(Instruction):
    name: str
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class StoreAtAddress(Instruction):
    address: InstructionWithType
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class ReturnValue(Instruction):
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class Return(Instruction):
    pass

@dataclass(eq=True, frozen=True)
class Assert(Instruction):
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class IgnoreValue(Instruction):
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class Scope(Instruction):
    body: List[Instruction]

@dataclass(eq=True, frozen=True)
class IfElse(Instruction):
    cond: InstructionWithType
    true_body: List[Instruction]
    false_body: List[Instruction]

@dataclass(eq=True, frozen=True)
class Goto(Instruction):
    label: str

@dataclass(eq=True, frozen=True)
class Label(Instruction):
    label: str

@dataclass(eq=True, frozen=True)
class LoadInteger(InstructionWithType):
    value: int

@dataclass(eq=True, frozen=True)
class LoadSymbol(InstructionWithType):
    value: str

@dataclass(eq=True, frozen=True)
class LoadBool(InstructionWithType):
    value: bool

@dataclass(eq=True, frozen=True)
class LoadFloat(InstructionWithType):
    value: str

@dataclass(eq=True, frozen=True)
class LoadCString(InstructionWithType):
    value: str

@dataclass(eq=True, frozen=True)
class LoadString(InstructionWithType):
    value: str

@dataclass(eq=True, frozen=True)
class LoadCGlobal(InstructionWithType):
    var: CGlobalVariableDefinition

@dataclass(eq=True, frozen=True)
class Null(InstructionWithType):
    pass

@dataclass(eq=True, frozen=True)
class LoadLocal(InstructionWithType):
    name: str

@dataclass(eq=True, frozen=True)
class LoadGlobal(InstructionWithType):
    filename: str
    name: str

@dataclass(eq=True, frozen=True)
class LoadFunction(InstructionWithType):
    name: str

@dataclass(eq=True, frozen=True)
class StoreLocalExpr(InstructionWithType):
    name: str
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class __TypeDowncast(InstructionWithType):
    target: InstructionWithType
    ctor: TypeConstructor

@dataclass(eq=True, frozen=True)
class CastExpr(InstructionWithType):
    expr: InstructionWithType

@dataclass(eq=True, frozen=True)
class LoadTupleIndex(InstructionWithType):
    target: InstructionWithType
    index: int

@dataclass(eq=True, frozen=True)
class LoadArrayIndex(InstructionWithType):
    target: InstructionWithType
    index: InstructionWithType

@dataclass(eq=True, frozen=True)
class ArrayAppend(InstructionWithType):
    array: InstructionWithType
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class ArrayPop(InstructionWithType):
    array: InstructionWithType

@dataclass(eq=True, frozen=True)
class LoadMember(InstructionWithType):
    target: InstructionWithType
    member: str

@dataclass(eq=True, frozen=True)
class LoadSubMember(InstructionWithType):
    target: InstructionWithType
    member: str
    ctor: TypeConstructor

@dataclass(eq=True, frozen=True)
class LoadTagValue(InstructionWithType):
    target: InstructionWithType

@dataclass(eq=True, frozen=True)
class LoadCommonMember(InstructionWithType):
    # Load a member that is common between all constructors
    target: InstructionWithType
    member: str

@dataclass(eq=True, frozen=True)
class Cast(InstructionWithType):
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class AddressOf(InstructionWithType):
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class DereferencePointer(InstructionWithType):
    value: InstructionWithType


@dataclass(eq=True, frozen=True)
class BinaryOp(InstructionWithType):
    lhs: InstructionWithType
    op: str
    rhs: InstructionWithType

@dataclass(eq=True, frozen=True)
class UnaryOp(InstructionWithType):
    op: str
    expr: InstructionWithType

@dataclass(eq=True, frozen=True)
class MakeRtti(InstructionWithType):
    target: Type

@dataclass(eq=True, frozen=True)
class InitInstance(InstructionWithType):
    target: InstructionWithType
    ctor: TypeConstructor
    arguments: List[InstructionWithType]

@dataclass(eq=True, frozen=True)
class InitCInstance(InstructionWithType):
    target: InstructionWithType
    arguments: List[InstructionWithType]

@dataclass(eq=True, frozen=True)
class CallFunction(InstructionWithType):
    func: FunctionDefinition
    arguments: List[InstructionWithType]

@dataclass(eq=True, frozen=True)
class CallCFunction(InstructionWithType):
    func: CFunctionDefinition
    arguments: List[InstructionWithType]

@dataclass(eq=True, frozen=True)
class CallFunctionPointer(InstructionWithType):
    func: FunctionDefinition
    arguments: List[InstructionWithType]

@dataclass(eq=True, frozen=True)
class InitTuple(InstructionWithType):
    target: InstructionWithType
    positional: List[InstructionWithType]
    named: List[InstructionWithType]
    names: List[str]

@dataclass(eq=True, frozen=True)
class MakeUnion(InstructionWithType):
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class MakeOptional(InstructionWithType):
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class OptionalIsEmpty(InstructionWithType):
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class OptionalGetValue(InstructionWithType):
    value: InstructionWithType

@dataclass(eq=True, frozen=True)
class MakeArray(InstructionWithType):
    elems: List[InstructionWithType]

@dataclass(eq=True, frozen=True)
class MakeArrayFromPointer(InstructionWithType):
    length: int
    pointer: InstructionWithType

@dataclass(eq=True, frozen=True)
class MakePointerFromArray(InstructionWithType):
    array: InstructionWithType

@dataclass(eq=True, frozen=True)
class ExprWithStmt(InstructionWithType):
    """
    Basically, an expression that requires some statements
    to be executed before it can be executed.
    """
    stmts: List[Instruction]
    expr: InstructionWithType

@dataclass(eq=True, frozen=True)
class RegexMatch(InstructionWithType):
    target: InstructionWithType
    bytecode: tuple
    num_groups: int
    group_mappings: tuple
