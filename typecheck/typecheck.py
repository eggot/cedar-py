import os
import frontend.astnodes as ast
import backend.ir as ir
from typecheck import declare
from dataclasses import dataclass
from typecheck.recompiler import compile_regex

@dataclass
class LoopContext:
    break_label: str
    continue_label: str
    is_expression: bool
    dest_variable: str
    dest_type: ir.Type

@dataclass
class FunctionState:
    retty: ir.Type
    local_symbols: 'List[dict]'
    access_locals: 'List[dict]'
    implicit_symbols: 'List[dict]'
    loops: 'List[LoopContext]'
    regexs: 'List[fndef]'

def describe(irty):
    match irty:
        case ir.UninferredType():
            return "uninferred"
        case ir.BoolType():
            return "bool"
        case ir.IntegerType(bits, signed):
            return "i%s" % bits if signed else "u%s" % bits
        case ir.VoidType():
            return "void"
        case ir.FloatType(bits):
            return {32: "float", 64: "double"}[bits]
        case ir.TupleType(positional, named, names):
            p = [describe(ty) for ty in positional] + ["%s: %s" % (name, describe(ty)) for ty, name in zip(named, names)]
            return "(%s)" % ", ".join(p)
        case ir.UnionType(types):
            return "|".join(describe(t) for t in types)
        case ir.PointerType(ty):
            return "%s*" % describe(ty)
        case ir.TypeDefinition(filename=filename, name=name):
            basename = os.path.basename(filename)
            namespace = os.path.splitext(basename)[0]
            return f"{namespace}.{name}"
        case ir.ArrayType(ty):
            return f"{describe(ty)}[]"
        case ir.OptionType(ty):
            return f"{describe(ty)}?"
        case ir.FunctionType(retty, argtys, argnames):
            p = ["%s %s" % (describe(t), n) for t, n in zip(argtys, argnames)]
            return "%s(%s)" % (describe(retty), ", ".join(p))
        case ir.CNamedType(name=name):
            return name
        case ir.CStructDefinition(name=name):
            return name
        case ir.CConstType(ty):
            return f"{describe(ty)} const"
        case ir.CTypedefDefinition(name=name):
            return name
        case _:
            assert False, irty

def is_error(ir_instr):
    return type(ir_instr) == ir.CompileError

def lookup_local(function_state, name):
    for d in reversed(function_state.local_symbols):
        if name in d:
            for acc in reversed(function_state.access_locals):
                if name in acc:
                    return acc[name]
            return ir.LoadLocal(d[name], name)
    return None

def lookup_implicit(function_state, ty):
    for d in reversed(function_state.implicit_symbols):
        if ty in d:
            return d[ty]
    return None

def new_local_temp(function_state, ty):
    num = sum(len(d) for d in function_state.local_symbols)
    name = "__temp%s__" % num
    function_state.local_symbols[-1][name] = ty
    return name


def typecheck_instr(ty, instr, return_none=False):
    match (ty, instr):
        case (_, ir.CompileError()):
            assert False, instr
        case (ir.IntegerType(bits, signed), ir.LoadInteger(_, value)):
            if signed:
                if -2**(bits - 1) <= value < 2 ** (bits - 1):
                    return ir.LoadInteger(ty, value)
            elif 0 <= value < 2 ** bits:
                    return ir.LoadInteger(ty, value)
            assert False, (ty, value)
        case (ir.OptionType(t), ir.UntypedNull()):
            return ir.Null(ty, location=instr.location)
        case (ir.PointerType(_), ir.UntypedNull()):
            return ir.Null(ty, location=instr.location)
        case (ir.PointerType(target), _) if instr.ty == target:
            return ir.AddressOf(ty, instr)
        case (ty, instr) if instr.ty == ty:
            return instr
        case (ir.UnionType(types), instr) if instr.ty in types:
            return ir.MakeUnion(ty, instr)
        case (ir.TupleType(), instr) if type(instr.ty) == ir.TupleType and ty != instr.ty:
            # Drop named slots only present in rhs
            # run typecheck_instr on all remaining slots
            assert False, "not yet implemented"
        case (ir.OptionType(t), instr) if instr.ty == t:
            return ir.MakeOptional(ty, instr)
        case (ir.CTypedefDefinition(name='size_t'), _) if type(instr.ty) == ir.IntegerType:
            return instr
        case (ir.ArrayType(), _) if instr.ty == ir.ArrayType(ir.UninferredType()):
            instr.__dict__['ty'].__dict__['elty'] = ty.elty
            return instr
        case (ir.CNamedType('int'), _) if type(instr.ty) == ir.IntegerType:
            return instr
        case (ir.IntegerType(bits, signed), _) if type(instr.ty) == ir.IntegerType and instr.ty.bits <= bits:
            return instr
        case (ir.PointerType(ir.CConstType(ir.CNamedType('char'))), _) if hasattr(instr, 'string_literal'):
            return ir.LoadCString(ty, instr.string_literal)
    if return_none:
        return None
    assert False, (ty, type(instr))


def unify_types_from_branches(ty0, ty1):
    if ty0 == ty1:
        return ty0
    elif ty0 == ir.ExitType():
        return ty1
    elif ty1 == ir.ExitType():
        return ty0
    elif ty0 == ir.VoidType():
        return ir.OptionType(ty1)
    elif ty1 == ir.VoidType():
        return ir.OptionType(ty0)
    elif type(ty0) == type(ty1) == ir.UnionType:
        tys = ty0.types
        for t in ty1:
            if t not in tys:
                tys.append(t)
        return ir.UnionType(tuple(tys))
    else:
        return ir.UnionType((ty0, ty1))

def type_of_stmt_block(stmts):
    if len(stmts) > 0:
        match stmts[-1]:
            case ir.IgnoreValue(expr):
                return expr.ty
            case ir.Return():
                return ir.ExitType()
            case ir.ReturnValue():
                return ir.ExitType()
    return ir.VoidType()

def typecheck_stmt_block(module_decls, ir_module, function_state, local_decls, nodes):
    result = []
    for node in nodes:
        result.extend(typecheck_stmt(module_decls, ir_module, function_state, local_decls, node))
    return result

def contains_new_identifier_expr(expr: ast.Expr) -> bool:
    # Base case: If the expression is a NewIdentifierExpr, return True
    if isinstance(expr, ast.NewIdentifierExpr):
        return True
    
    # Recursively check all attributes of the expression that are instances of Expr or List[Expr]
    for field in expr.__dataclass_fields__:
        value = getattr(expr, field)
        
        # If the field is an expression, check it recursively
        if isinstance(value, ast.Expr):
            if contains_new_identifier_expr(value):
                return True
        
        # If the field is a list, check each element
        if isinstance(value, list):
            for item in value:
                if isinstance(item, ast.Expr) and contains_new_identifier_expr(item):
                    return True
    
    return False

def dereference_pointer(module_decls, ir_expr):
    match ir_expr.ty:
        case ir.PointerType(ir.TypeDefinition(filename=filename)):
            module = module_decls[filename]
            for fn in module.functions:
                if fn.name == '__unpack__' and fn.retty == ir_expr.ty.target:
                    return ir.CallFunction(fn.retty, fn, (ir_expr,))
    return ir.DereferencePointer(ir_expr.ty.target, ir_expr, location=ir_expr.location)

def typecheck_pattern_match(module_decls, ir_module, function_state, local_decls, lhs, rhs, true_body, false_body, location):
    eq_list = []
    decl_list = []
    store_list = []
    error_list = []

    # Typecheck the entire top-level RHS first
    rhs_ir = typecheck_expr(module_decls, ir_module, function_state, local_decls, rhs)

    # If the RHS typechecking results in an error, return the error immediately
    if is_error(rhs_ir):
        return [rhs_ir]

    def deconstruct_pattern(lhs_expr, rhs_type, rhs_ir):
        if type(rhs_type) == ir.PointerType:
            deconstruct_pattern(lhs_expr, rhs_type.target, dereference_pointer(module_decls, rhs_ir)) # ir.DereferencePointer(rhs_type.target, rhs_ir, location=rhs_ir.location))
            return
        match lhs_expr:
            # Optional == null
            case ast.NullExpr():
                eq_list.append(ir.OptionalIsEmpty(ir.BoolType(), rhs_ir, location=lhs_expr.location))

            # Option type
            case ast.CallExpr(ast.IdentifierExpr('Some'), args, None):
                ty, ctor = lookup_constructor([ir_module], 'Some', ir_module.filename)
                if ty:
                    error_list.append(ir.CompileError(f"Constructor 'Some' must not be defined", location=lhs_expr.location))
                    return
                eq_list.append(ir.UnaryOp(ir.BoolType(), "!", ir.OptionalIsEmpty(ir.BoolType(), rhs_ir, location=lhs_expr.location)))
                deconstruct_pattern(args.positional[0], rhs_type.target, ir.OptionalGetValue(rhs_type.target, rhs_ir))

            # Constructor Call Case
            case ast.CallExpr(ast.IdentifierExpr(ctor_name), args, None):
                ty, ctor = lookup_constructor([ir_module], ctor_name, ir_module.filename)
                if not ty or not ctor:
                    error_list.append(ir.CompileError(f"Constructor '{ctor_name}' not found", location=lhs_expr.location))
                    return

                # Validate that the RHS type matches the expected constructor type
                if rhs_type != ty:
                    error_list.append(ir.CompileError(f"Type mismatch: expected constructor '{ctor_name}', got {describe(rhs_type)}", location=lhs_expr.location))
                    return

                if ty.tagless:
                    error_list.append(ir.CompileError(f"Cannot match on tagless type {describe(ty)}"))
                    return

                # Check the __index__ member to ensure the constructor matches
                if len(ty.constructors) > 1:
                    tag_index = ctor.layout_names.index("__index__")
                    tag_ty = ctor.layout_types[tag_index]
                    tag_ir = ir.LoadMember(tag_ty, rhs_ir, "__index__")

                    # Compare the tag in the RHS with the expected constructor tag
                    expected_tag_value = [c.name for c in ty.constructors].index(ctor_name)
                    eq_list.append(ir.BinaryOp(ir.BoolType(), tag_ir, '==', ir.LoadInteger(tag_ty, expected_tag_value), location=lhs_expr.location))

                # Recursively deconstruct the constructor fields
                for arg_expr, field_ty, field_name in zip(args.positional, ctor.field_types, ctor.field_names):
                    deconstruct_pattern(arg_expr, field_ty, ir.LoadMember(field_ty, rhs_ir, field_name))

            # Namespace Constructor Call Case
            case ast.CallExpr(ast.MemberExpr(ast.IdentifierExpr(namespace_name), name), args, None) if namespace := lookup(ir_module.namespaces, namespace_name):
                ty, ctor = lookup_constructor(namespace.modules, name, ir_module.filename)
                if rhs_type != ty:
                    error_list.append(ir.CompileError(f"Type mismatch: expected '{describe(rhs_type)}', got '{describe(ty)}'", location=lhs_expr.location))
                    return
                match ty:
                    case ir.TypeDefinition():
                        # Check the __index_ member to ensure the constructor matches
                        if ty.tagless:
                            error_list.append(ir.CompileError(f"Cannot match on tagless type {describe(ty)}"))
                            return
                        if len(ty.constructors) > 1:
                            tag_index = ctor.layout_names.index("__index__")
                            tag_ty = ctor.layout_types[tag_index]
                            tag_ir = ir.LoadMember(tag_ty, rhs_ir, "__index__")

                            # Compare the tag in the RHS with the expected constructor tag
                            expected_tag_value = [c.name for c in ty.constructors].index(name)
                            eq_list.append(ir.BinaryOp(ir.BoolType(), tag_ir, '==', ir.LoadInteger(tag_ty, expected_tag_value), location=lhs_expr.location))

                        # Recursively deconstruct the constructor fields within the namespace
                        for arg_expr, field_ty, field_name in zip(args.positional, ctor.field_types, ctor.field_names):
                            deconstruct_pattern(arg_expr, field_ty, ir.LoadSubMember(field_ty, rhs_ir, field_name, ctor))
                    case ir.CStructDefinition():
                        # Recursively deconstruct the constructor fields within the namespace
                        for arg_expr, field_ty, field_name in zip(args.positional, ty.field_types, ty.field_names):
                            deconstruct_pattern(arg_expr, field_ty, ir.LoadMember(field_ty, rhs_ir, field_name))
                    case _:
                        error_list.append(ir.CompileError(f"Constructor '{name}' not found in namespace '{namespace_name}'", location=lhs_expr.location))
                        return


            # Tuple Destructuring Case
            case ast.TupleExpr(positional, named, names):
                if not isinstance(rhs_type, ir.TupleType):
                    error_list.append(ir.CompileError(f"Type mismatch: expected tuple, got {describe(rhs_type)}", location=lhs_expr.location))
                    return

                # Check positional elements
                if len(positional) != len(rhs_type.positional):
                    error_list.append(ir.CompileError(f"Tuple length mismatch: expected {len(positional)} elements, got {len(rhs_type.positional)}", location=lhs_expr.location))
                    return

                for idx, arg_expr in enumerate(positional):
                    deconstruct_pattern(arg_expr, rhs_type.positional[idx], ir.LoadTupleIndex(rhs_type.positional[idx], rhs_ir, idx))

                # Check named elements
                for name, arg_expr in zip(names, named):
                    if name not in rhs_type.names:
                        error_list.append(ir.CompileError(f"Tuple does not have a named field '{name}'", location=lhs_expr.location))
                        return

                    idx = rhs_type.names.index(name)
                    deconstruct_pattern(arg_expr, rhs_type.named[idx], ir.LoadMember(rhs_type.named[idx], rhs_ir, name))

            # Let-Binding Case (New Identifier)
            case ast.NewIdentifierExpr(name):
                # Let-binding: declare and store the value from rhs
                function_state.local_symbols[-1][name] = rhs_type
                decl_list.append(ir.DeclareLocal(rhs_type, name, location=lhs_expr.location))
                store_list.append(ir.StoreLocal(name, rhs_ir, location=lhs_expr.location))

            # Simple Identifier Expression Case
            case ast.IdentifierExpr(_):
                # Compare the lhs expression directly to the rhs_ir
                eq_list.append(ir.BinaryOp(ir.BoolType(), typecheck_expr(module_decls, ir_module, function_state, local_decls, lhs_expr), '==', rhs_ir, location=lhs_expr.location))

            case ast.RegexExpr(reast):
                if (rhs_type.filename, rhs_type.name) != ('__builtins__/string.ce', 'String'):
                    error_list.append(ir.CompileError(f"Regex can only match on strings; got {describe(rhs_type)}", location=lhs_expr.location))
                bytecode, num_capturing_groups, capturing_group_mappings = compile_regex(reast)
                function = compile_regex_function(ir_module, bytecode, num_capturing_groups, capturing_group_mappings, rhs_type)
                function_state.regexs.append(function)
                ir_call = ir.CallFunction(function.retty, function, (rhs_ir,))
                if function.retty == ir.BoolType():
                    eq_list.append(ir_call)
                else:
                    temp_name = "__match_%d" % sum(len(d) for d in function_state.local_symbols)
                    local_decls.append(ir.DeclareLocal(function.retty, temp_name))
                    eq_list.append(ir.UnaryOp(ir.BoolType(), '!', ir.OptionalIsEmpty(ir.BoolType(), ir.StoreLocalExpr(function.retty, temp_name, ir_call))))
                    for name, ty in zip(function.retty.target.names, function.retty.target.named):
                        decl_list.append(ir.DeclareLocal(ty, name))
                        store_list.append(ir.StoreLocal(name, ir.LoadMember(rhs_type, ir.OptionalGetValue(function.retty.target, ir.LoadLocal(function.retty, temp_name)), name)))
                        function_state.local_symbols[-1][name] = rhs_type
                    for idx, ty in enumerate(function.retty.target.positional):
                        name = "_%d" % idx
                        decl_list.append(ir.DeclareLocal(ty, name))
                        store_list.append(ir.StoreLocal(name, ir.LoadTupleIndex(rhs_type, ir.OptionalGetValue(function.retty.target, ir.LoadLocal(function.retty, temp_name)), idx)))
                        function_state.local_symbols[-1][name] = rhs_type
            # Fallback Case for Other BinaryOps (Equality Checks)
            case _:
                eq_list.append(ir.BinaryOp(ir.BoolType(), typecheck_expr(module_decls, ir_module, function_state, local_decls, lhs_expr), '==', rhs_ir, location=lhs_expr.location))

    # Start the recursive deconstruction or matching process
    deconstruct_pattern(lhs, rhs_ir.ty, rhs_ir)

    # If there are any type mismatch errors, return those errors
    if error_list:
        return error_list

    # Generate the body for the if statement
    ir_true_body = typecheck_stmt_block(module_decls, ir_module, function_state, local_decls, true_body.stmts)
    ir_false_body = typecheck_stmt_block(module_decls, ir_module, function_state, local_decls, false_body.stmts)

    # Combine equality checks with logical ANDs
    if eq_list:
        combined_condition = eq_list[0]
        for condition in eq_list[1:]:
            combined_condition = ir.BinaryOp(ir.BoolType(), combined_condition, '&&', condition, location=lhs.location)
    else:
        combined_condition = ir.LoadBool(ir.BoolType(), True, location=lhs.location)  # No conditions to check

    # Emit the if-else structure
    return [ir.IfElse(combined_condition, decl_list + store_list + ir_true_body, ir_false_body, location=lhs.location)]

def typecheck_args(callee_name, decltys, argnames, arg_values, location, is_varargs=False):
    if is_varargs:
        if len(argnames) > len(arg_values):
            msg = f"{callee_name} expect at least {len(argnames)} arguments, but got {len(arg_values)}"
            assert False, msg
        new_arg_values = list(arg_values[:])
        for idx, name, argty, val in zip(range(len(argnames)), argnames, decltys, arg_values):
            res = typecheck_instr(argty, val, return_none=True)
            if res is None:
                msg = f"{location}: Argument #{idx} '{name}' of function '{callee_name}' expect '{describe(argty)}' but got '{describe(val.ty)}'"
                assert False, msg
            new_arg_values[idx] = res
        return new_arg_values
    else: 
        if len(argnames) != len(arg_values):
            msg = f"{location}: {callee_name} expect {len(argnames)} arguments, but got {len(arg_values)}"
            assert False, msg
        new_arg_values = []
        for idx, name, argty, val in zip(range(len(argnames)), argnames, decltys, arg_values):
            res = typecheck_instr(argty, val, return_none=True)
            if res is None:
                msg = f"{location}: Argument #{idx} '{name}' of function '{callee_name}' expect '{describe(argty)}' but got '{describe(val.ty)}'"
                assert False, msg
            new_arg_values.append(res)
        return new_arg_values
        

def typecheck_expr_call_func(function_state, fn, ir_positional, location):
    match fn:
        case ir.CFunctionDefinition(varargs=varargs):
            ir_positional = typecheck_args(fn.name, fn.argtys, fn.argnames, ir_positional, location, is_varargs=varargs)
            return ir.CallCFunction(fn.retty, fn, ir_positional)
        case ir.LoadLocal(ir.FunctionType(), name):
            ir_positional = typecheck_args(name, fn.ty.argtys, fn.ty.argnames, ir_positional, location)
            return ir.CallFunctionPointer(fn.ty.retty, fn, ir_positional)
        case ir.FunctionDefinition():
            explicit_args = []
            provided_implicits = {}
            for arg in ir_positional:
                if arg.ty in fn.argtys_implicit:
                    provided_implicits[arg.ty] = arg
                else:
                    explicit_args.append(arg)
            
            implicit_args = []
            for ty in fn.argtys_implicit:
                if ty in provided_implicits:
                    implicit_args.append(provided_implicits[ty])
                else:
                    locname = lookup_implicit(function_state, ty)
                    assert locname is not None, ty
                    implicit_args.append(ir.LoadLocal(ty, locname))

            final_arguments = implicit_args + typecheck_args(fn.name, fn.argtys, fn.argnames, explicit_args, location)
            return ir.CallFunction(fn.retty, fn, final_arguments)
    assert False, "not implemented: %s" % fn

def typecheck_expr_call(module_decls, ir_module, function_state, local_decls, node, target_modules, callee_name, location):
    location = node.location
    local_ir = lookup_local(function_state, callee_name)
    ty, ctor = lookup_constructor(target_modules, callee_name, ir_module.filename)

    if local_ir is not None and ty is not None:
        assert False, "ambigious call to %s" % callee_name

    ir_positional = tuple(typecheck_expr(module_decls, ir_module, function_state, local_decls, a) for a in node.args.positional)
    match ty:
        case ir.TypeDefinition():
            ir_positional = typecheck_args(ty.name, ctor.field_types, ctor.field_names, ir_positional, location)
            temp_name = new_local_temp(function_state, ty)
            local_decls.append(ir.DeclareLocal(ty, temp_name, location=location))
            stmt = ir.InitInstance(ty, ir.LoadLocal(ty, temp_name, location=location), ctor, ir_positional)
            return ir.ExprWithStmt(ty, [stmt], ir.LoadLocal(ty, temp_name, location=location))
        case ir.CStructDefinition():
            ir_positional = typecheck_args(ty.name, ty.field_types, ty.field_names, ir_positional, location)
            temp_name = new_local_temp(function_state, ty)
            local_decls.append(ir.DeclareLocal(ty, temp_name, location=location))
            stmt = ir.InitCInstance(ty, ir.LoadLocal(ty, temp_name, location=location), ir_positional)
            return ir.ExprWithStmt(ty, [stmt], ir.LoadLocal(ty, temp_name, location=location))
        case ir.CUnionDefinition():
            return ir.MakeCInstance(ty, ir_positional)
    
    ir_module, fn = lookup_function(target_modules, callee_name, ir_module.filename)
    if local_ir is not None and fn is not None:
        assert False, "ambigious call to %s" % callee_name

    if fn is not None:
        return typecheck_expr_call_func(function_state, fn, ir_positional, node.location)
    
    if local_ir is None:
        search = ", ".join(m.filename for m in target_modules)
        assert False, f"No symbol {callee_name} in {search}"
    assert local_ir is not None, callee_name
    return typecheck_expr_call_func(function_state, local_ir, ir_positional, node.location)


def typecheck_expr(module_decls, ir_module, function_state, local_decls, node):
    location = node.location
    match node:

        case ast.BoolExpr(b):
            return ir.LoadBool(ir.BoolType(), b, location=location)

        case ast.IntegerExpr(i):
            return ir.LoadInteger(ir.IntegerType(32, signed=True), i, location=location)

        case ast.FloatExpr(f):
            return ir.LoadFloat(ir.FloatType(32), f, location=location)

        case ast.RegexExpr(reast):
            bytecode, num_capturing_groups, capturing_group_mappings = compile_regex(reast)
            str_ty = lookup(module_decls['__builtins__/string.ce'].types, 'String')
            function = compile_regex_function(ir_module, bytecode, num_capturing_groups, capturing_group_mappings, str_ty)
            function_state.regexs.append(function)
            ty = ir.FunctionType(function.retty, function.argtys, function.argnames)
            return ir.LoadGlobal(ty, function.filename, function.name)

        case ast.SymbolExpr(s):
            ty = lookup(module_decls['__builtins__/symbol.ce'].types, 'Symbol')
            ctor = ty.constructors[0]
            temp_name = new_local_temp(function_state, ty)
            local_decls.append(ir.DeclareLocal(ty, temp_name, location=location))
            args = [ir.LoadSymbol(ir.IntegerType(32, False), s, location=location)]
            stmt = ir.InitInstance(ty, ir.LoadLocal(ty, temp_name, location=location), ctor, args)
            return ir.ExprWithStmt(ty, [stmt], ir.LoadLocal(ty, temp_name, location=location))

        case ast.StringExpr(s):
            str_ty = lookup(module_decls['__builtins__/string.ce'].types, 'String')
            ctor = str_ty.constructors[0]
            temp_name = new_local_temp(function_state, str_ty)
            arr_ty = ir.ArrayType(ir.IntegerType(8, False))
            local_decls.append(ir.DeclareLocal(str_ty, temp_name, location=location))
            local_decls.append(ir.DeclareLocal(arr_ty, temp_name + "_array", location=location))
            stmts = [
                ir.StoreLocal(temp_name + "_array", ir.MakeArrayFromPointer(arr_ty, len(s), ir.LoadString(ir.PointerType(ir.IntegerType(8, False)), s, location=location))),
                ir.InitInstance(str_ty, ir.LoadLocal(str_ty, temp_name, location=location), ctor, [ir.LoadLocal(arr_ty, temp_name + "_array")])]
            x = ir.ExprWithStmt(str_ty, stmts, ir.LoadLocal(str_ty, temp_name, location=location))
            x.__dict__['string_literal'] = s
            return x

        case ast.IdentifierExpr(name):
            local_ir = lookup_local(function_state, name)
            if local_ir is None:
                assert False, ir.CompileError("No symbol '%s' in scope" % name, location=location)
            else:
                return local_ir #ir.LoadLocal(local_ty, name, location=location)
            
        case ast.NullExpr():
            return ir.UntypedNull(location=location)
        
        # [1, 2, 3, 4]
        case ast.ArrayExpr(elems):
            ir_elems = tuple(typecheck_expr(module_decls, ir_module, function_state, local_decls, el) for el in elems)
            if len(ir_elems) == 0:
                return ir.MakeArray(ir.ArrayType(ir.UninferredType()), tuple(), location=location)
            else:
                ty = ir_elems[0].ty
                for el in ir_elems:
                    if ty != el.ty:
                        return ir.CompileError("Conflicting types in array: '%s' vs '%s'" % (describe(ty), describe(el.ty)), location=location)
                return ir.MakeArray(ir.ArrayType(ty), ir_elems)
        
        # lower..upper
        case ast.BinaryOpExpr(lower, "..", upper):
            ir_lower = typecheck_expr(module_decls, ir_module, function_state, local_decls, lower)
            ir_upper = typecheck_expr(module_decls, ir_module, function_state, local_decls, upper)
            if type(ir_lower.ty) != ir.IntegerType or type(ir_upper.ty) != ir.IntegerType:
                return ir.CompileError(f"Lower and upper limits of range must be integer values, got '{describe(ir_lower.ty)}' and '{describe(ir_upper.ty)}'", location=node.location)
            ty = lookup(module_decls['__builtins__/range.ce'].types, 'Range')
            ctor = ty.constructors[0]
            temp_name = new_local_temp(function_state, ty)
            local_decls.append(ir.DeclareLocal(ty, temp_name, location=location))
            args = [ir_lower, ir_upper]
            stmt = ir.InitInstance(ty, ir.LoadLocal(ty, temp_name, location=location), ctor, args)
            return ir.ExprWithStmt(ty, [stmt], ir.LoadLocal(ty, temp_name, location=location))
        
        # x else y
        case ast.BinaryElseExpr(lhs, rhs):
            temp_name = "__tempelse_%d" % id(node)
            result_name = "__resultelse_%d" % id(node)

            ir_lhs = typecheck_expr(module_decls, ir_module, function_state, local_decls, lhs)
            if is_error(ir_lhs):
                return ir_lhs
            if type(ir_lhs.ty) not in (ir.OptionType,):
                return ir.CompileError(f"Can't apply operator 'else' to type '{describe(ir_lhs.ty)}'")

            rhs_decls = []
            function_state.local_symbols.append({})
            ir_rhs_body = typecheck_stmt_block(module_decls, ir_module, function_state, rhs_decls, rhs.stmts)
            function_state.local_symbols.pop()

            if len(ir_rhs_body) > 0 and type(ir_rhs_body[-1]) == ir.IgnoreValue:
                rhs_ty = ir_rhs_body[-1].value.ty
                ir_rhs_body[-1] = ir.StoreLocal(result_name, ir_rhs_body[-1].value)
            else:
                return ir.CompileError(f"Right-hand side of binary else must yield a value")

            if ir_lhs.ty.target != rhs_ty:
                return ir.CompileError(f"Right-hand side of operator 'else' must be of type {describe(ir_lhs.ty.target)}; got {describe(ir_rhs.ty)}")
            local_decls.append(ir.DeclareLocal(ir_lhs.ty, temp_name))
            local_decls.append(ir.DeclareLocal(ir_lhs.ty.target, result_name))
            stmts = [
                ir.StoreLocal(temp_name, ir_lhs),
                ir.IfElse(ir.OptionalIsEmpty(ir.BoolType(), ir.LoadLocal(ir_lhs.ty, temp_name)), ir_rhs_body, [
                    ir.StoreLocal(result_name, ir.OptionalGetValue(ir_lhs.ty.target, ir.LoadLocal(ir_lhs.ty, temp_name)))
                ])
            ]
            return ir.ExprWithStmt(ir_lhs.ty.target, stmts, ir.LoadLocal(ir_lhs.ty.target, result_name))


        # x + y
        case ast.BinaryOpExpr(lhs, op, rhs):
            ir_lhs = typecheck_expr(module_decls, ir_module, function_state, local_decls, lhs)
            ir_rhs = typecheck_expr(module_decls, ir_module, function_state, local_decls, rhs)
            if is_error(ir_lhs):
                return ir_lhs
            if is_error(ir_rhs):
                return ir_rhs
            if ir_lhs.ty != ir_rhs.ty:
                return ir.CompileError("Can't apply binary operator '%s' to types '%s' and '%s'" % (op, describe(ir_lhs.ty), describe(ir_rhs.ty)))
            if op in ('<', '<=', '!=', '==', '>=', '>'):
                ty = ir.BoolType()
            else:
                ty = ir_lhs.ty
            return ir.BinaryOp(ty, ir_lhs, op, ir_rhs, location=location)

        # -y
        case ast.UnaryOpExpr('-', expr):
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            if is_error(ir_expr):
                return ir_lhs
            ty = ir_expr.ty
            return ir.UnaryOp(ty, '-', ir_expr, location=location)

        # &<expr>
        case ast.UnaryOpExpr('&', expr):
            #if type(expr) in (ast.IdentifierExpr, ast.IndexExpr, ast.MemberExpr)

            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            if is_error(ir_expr):
                return ir_expr
            if type(ir_expr) not in (ir.LoadLocal, ): # FILL MORE HERE
                return ir.CompileError("Cannot take the address of expression")
            if type(ir_expr) == ir.LoadCGlobal and not ir_expr.has_address:
                return ir.CompileError("Cannot take the address of this C global")
            return ir.AddressOf(ir.PointerType(ir_expr.ty), ir_expr, location=location)
        
        # *<expr>
        case ast.UnaryOpExpr('*', expr):
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            if is_error(ir_expr):
                return ir_expr
            if type(ir_expr.ty) != ir.PointerType:
                return ir.CompileError(f"Cannot dereference non-pointer type '{describe(ir_expr.ty)}'")
            return dereference_pointer(module_decls, ir_expr)
        
        # type(<expr>)
        case ast.TypeOfExpr(expr):
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            if is_error(ir_expr):
                return ir_expr
            return ir.MakeRtti(ir.RttiType(), ir_expr.ty)
        
        # cast(type) expr
        case ast.CastExpr(ty, expr):
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            namespaces = {ns.name:[m.filename for m in ns.modules] for ns in ir_module.namespaces}
            ir_ty = declare.resolve_type(ty, module_decls, namespaces, ir_module.filename)
            return ir.CastExpr(ir_ty, ir_expr)
        
        # <expr> where { <stmts> }
        case ast.WhereExpr(expr, body):
            function_state.local_symbols.append({})
            
            ir_stmts = []
            for stmt in body:
                ir_stmts.extend(typecheck_stmt(module_decls, ir_module, function_state, local_decls, stmt))
            
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            function_state.local_symbols.pop()
            temp_name = new_local_temp(function_state, ir_expr.ty)
            

            local_decls.append(ir.DeclareLocal(ir_expr.ty, temp_name, location=location))
            ir_stmts.append(ir.StoreLocal(temp_name, ir_expr, location=location))
            return ir.ExprWithStmt(ir_expr.ty, [ir.Scope(ir_stmts)], ir.LoadLocal(ir_expr.ty, temp_name, location=location))

        # (1, 2, named_slot: 3.0)
        case ast.TupleExpr(positional, named, names):
            ir_positional = [typecheck_expr(module_decls, ir_module, function_state, local_decls, p) for p in positional]
            ir_named = [typecheck_expr(module_decls, ir_module, function_state, local_decls, p) for p in named]
            ty = ir.TupleType(tuple(i.ty for i in ir_positional), tuple(i.ty for i in ir_named), tuple(names), 'uninitialized', 'uninitialized')
            declare.optimize_datatype_layout(ty)

            temp_name = new_local_temp(function_state, ty)
            local_decls.append(ir.DeclareLocal(ty, temp_name, location=location))
            stmt = ir.InitTuple(ty, ir.LoadLocal(ty, temp_name, location=location), ir_positional, ir_named, names)
            return ir.ExprWithStmt(ty, [stmt], ir.LoadLocal(ty, temp_name, location=location))
        
        # foo[bar]
        case ast.IndexExpr(target, indices):
            ir_target = typecheck_expr(module_decls, ir_module, function_state, local_decls, target)
            ir_indices = [typecheck_expr(module_decls, ir_module, function_state, local_decls, i) for i in indices]
            if type(ir_target.ty) == ir.TupleType:
                if len(ir_indices) != 1:
                    return ir.CompileError("Tuple values can only be index by one index", location=location)
                elif type(ir_indices[0]) != ir.LoadInteger:
                    return ir.CompileError("Tuple values can only be indexed by integer literal values", location=location)
                elif ir_indices[0].value >= len(ir_target.ty.positional):
                    return ir.CompileError("Tuple value index out of bounds", location=location)
                ty = ir_target.ty.positional[ir_indices[0].value]
                return ir.LoadTupleIndex(ty, ir_target, ir_indices[0].value)
            elif type(ir_target.ty) == ir.ArrayType:
                if len(ir_indices) != 1:
                    return ir.CompileError("Arrays can only be index by one index", location=location)
                elif type(ir_indices[0].ty) != ir.IntegerType:
                    return ir.CompileError("Arrays only be indexed by integer values", location=location)
                return ir.LoadArrayIndex(ir_target.ty.elty, ir_target, ir_indices[0])

            ir_module, fn = lookup_function([module_decls[ir_target.ty.filename]], '__getindex__', ir_module.filename)
            assert fn is not None, 'Cant index value of type %s' % describe(ir_target.ty)
            return typecheck_expr_call_func(function_state, fn, (ir_target,) + tuple(ir_indices), node.location)

        # cstring("string")
        case ast.CallExpr(ast.IdentifierExpr("cstring"), ast.TupleExpr([ast.StringExpr(value)], named=[], names=[]), None):
            return ir.LoadCString(ir.PointerType(ir.CConstType(ir.CNamedType('char', None))), value)

        # char("c")
        case ast.CallExpr(ast.IdentifierExpr("char"), ast.TupleExpr([ast.StringExpr(value)], named=[], names=[]), None):
            assert len(value) == 1
            return ir.LoadInteger(ir.IntegerType(8, False), ord(value[0]))

        # namespace.function(...)
        case ast.CallExpr(ast.MemberExpr(ast.IdentifierExpr(namespace_name), fnname), _args, _block) if namespace := lookup(ir_module.namespaces, namespace_name):
            return typecheck_expr_call(module_decls, ir_module, function_state, local_decls, node, namespace.modules, fnname, node.location)

        # expr.function(...)
        case ast.CallExpr(ast.MemberExpr(target, fnname), _args, _block):
            ir_target = typecheck_expr(module_decls, ir_module, function_state, local_decls, target)
            location = node.location
            ir_positional = tuple(typecheck_expr(module_decls, ir_module, function_state, local_decls, a) for a in node.args.positional)

            if type(ir_target.ty) == ir.ArrayType:
                if fnname == 'append':
                    if len(ir_positional) != 1:
                        return ir.CompileError("Array.append expects one argument")
                    if ir_target.ty.elty == ir.UninferredType():
                        ir_target.ty.__dict__['elty'] = ir_positional[0].ty
                    elif ir_positional[0].ty != ir_target.ty.elty:
                        return ir.CompileError(f"Array.append expects argument of type {describe(ir_target.ty.elty)}; got {describe(ir_positional[0].ty)}")
                    return ir.ArrayAppend(ir.VoidType(), ir_target, ir_positional[0])
                elif fnname == 'pop':
                    if len(ir_positional) != 0:
                        return ir.CompileError("Array.pop expects no arguments")
                return ir.ArrayPop(ir_target.ty.elty, ir_target)


            ir_module, fn = lookup_function([module_decls[ir_target.ty.filename]], fnname, ir_module.filename)
            assert fn is not None, fnname
            return typecheck_expr_call_func(function_state, fn, (ir_target,) + ir_positional, node.location)
            #return typecheck_expr_call(module_decls, ir_module, function_state, local_decls, node, modules, fnname)

        # funcname(args)
        case ast.CallExpr(ast.IdentifierExpr(fnname), _args, _block):
            namespace = lookup(ir_module.namespaces, 'implicit')
            return typecheck_expr_call(module_decls, ir_module, function_state, local_decls, node, namespace.modules, fnname, node.location)

        # namespace.member
        case ast.MemberExpr(ast.IdentifierExpr(namespace_name), name) if namespace := lookup(ir_module.namespaces, namespace_name):
            module, var = lookup_variable(namespace.modules, name, return_none_if_not_found=True)
            ty, ctor = lookup_constructor(namespace.modules, name, ir_module.filename)
            if var is not None and var.ty is None:
                return ir.CompileError(f"C variable '{var.name}' from {module.filename} can not be used as it's type can't be determined.")
            elif ctor is not None:
                if not ctor.without_arglist:
                    return ir.CompileError(f"Constructor {ty.filename}:{ctor.name} requires an argument list")
                temp_name = new_local_temp(function_state, ty)
                local_decls.append(ir.DeclareLocal(ty, temp_name, location=location))
                stmt = ir.InitInstance(ty, ir.LoadLocal(ty, temp_name, location=location), ctor, ())
                return ir.ExprWithStmt(ty, [stmt], ir.LoadLocal(ty, temp_name, location=location))
            match var:
                case ir.CGlobalVariableDefinition():
                    return ir.LoadCGlobal(var.ty, var)
        
        # structtype.fieldname
        case ast.MemberExpr(target, name):
            if type(target) == ast.IdentifierExpr and name == '__tag__':
                ns = lookup(ir_module.namespaces, 'implicit')
                ty, ctor = lookup_constructor(ns.modules, target.name, ir_module.filename)
                if ty is not None:
                    return ir.LoadInteger(ir.IntegerType(16, False), ty.constructors.index(ctor))
            ir_target = typecheck_expr(module_decls, ir_module, function_state, local_decls, target)
            if is_error(ir_target):
                return ir_target

            if type(ir_target) == ir.__TypeDowncast:
                ctor = ir_target.ctor
                idx = ctor.field_names.index(name)
                ty = ctor.field_types[idx]
                return ir.LoadSubMember(ty, ir_target.target, name, ctor)

            if type(ir_target.ty) == ir.PointerType:
                ir_target = dereference_pointer(module_decls, ir_target)

            if type(ir_target.ty) == ir.TupleType:
                if name not in ir_target.ty.names:
                    return ir.CompileError(f"Tuple value has no slot named '{name}'", location=location)
                idx = ir_target.ty.names.index(name)
                ty = ir_target.ty.named[idx]
                return ir.LoadMember(ty, ir_target, name)
            # NOTE: This also handles the case when accessing a field on a datatype with only one constructor
            elif type(ir_target.ty) == ir.TypeDefinition and name in ir_target.ty.common_names or name == '__tag__':
                if name == '__tag__':
                    return ir.LoadTagValue(ir.IntegerType(32, True), ir_target)
                elif name == '__index__':
                    ctor = ir_target.ty.constructors[0]
                    idx = ctor.layout_names.index(name)
                    ty = ctor.layout_types[idx]
                    return ir.LoadSubMember(ty, ir_target, name, ctor)
                else:
                    ctor = ir_target.ty.constructors[0]
                    idx = ctor.field_names.index(name)
                    ty = ctor.field_types[idx]
                    return ir.LoadCommonMember(ty, ir_target, name)
            elif type(ir_target.ty) == ir.TypeDefinition and any(name == c.name for c in ir_target.ty.constructors):
                ctor = [c for c in ir_target.ty.constructors if name == c.name][0]
                return ir.__TypeDowncast('ctor of type', ir_target, ctor)
            elif type(ir_target.ty) == ir.CStructDefinition:
                if name not in ir_target.ty.field_names:
                    assert False, ir.CompileError(f"Type {describe(ir_target.ty)} does not have a field '{name}'")
                idx = ir_target.ty.field_names.index(name)
                return ir.LoadMember(ir_target.ty.field_types[idx], ir_target, name)
            elif type(ir_target.ty) == ir.ArrayType:
                if name != 'length':
                    assert False, ir.CompileError(f"Type {describe(ir_target.ty)} does not have a field '{name}'")
                return ir.LoadMember(ir.IntegerType(32, False), ir_target, 'length')
            else:
                assert False, f"{location}:Type %s has no field '%s'" % (describe(ir_target.ty), name)

        # if cond { ... }
        case ast.IfExpr(cond, true_body, false_body):
            ir_cond = typecheck_expr(module_decls, ir_module, function_state, local_decls, cond)
            if is_error(ir_cond):
                return ir_cond
            if ir_cond.ty != ir.BoolType():
                assert False, ir.CompileError(f"Expected 'bool' for condition to if", location=location)
            true_decls = []
            function_state.local_symbols.append({})
            ir_true_body = typecheck_stmt_block(module_decls, ir_module, function_state, true_decls, true_body.stmts)
            function_state.local_symbols[-1] = {}
            false_decls = []
            ir_false_body = typecheck_stmt_block(module_decls, ir_module, function_state, false_decls, false_body.stmts)
            function_state.local_symbols.pop()
            true_type = type_of_stmt_block(ir_true_body)
            false_type = type_of_stmt_block(ir_false_body)
            ty = unify_types_from_branches(true_type, false_type)
            temp_name = new_local_temp(function_state, ty)
            
            for ir_body in (ir_true_body, ir_false_body):
                if len(ir_body) > 0 and type(ir_body[-1]) == ir.IgnoreValue:
                    ir_value = ir_body[-1].value
                    typed_ir_value = typecheck_instr(ty, ir_value)
                    ir_body[-1] = ir.StoreLocal(temp_name, typed_ir_value)
            
            local_decls.append(ir.DeclareLocal(ty, temp_name, location=location))
            stmts = []
            if type(ty) == ir.OptionType:
                stmts.append(ir.StoreLocal(temp_name, ir.Null(ty)))
            stmts.append(ir.IfElse(ir_cond, true_decls + ir_true_body, false_decls + ir_false_body, location=location))
            return ir.ExprWithStmt(ty, stmts, ir.LoadLocal(ty, temp_name, location=location))

        # for iterator in iterable:
        case ast.ForExpr(ast.IdentifierExpr(name), iterable, body):
            ir_iterable = typecheck_expr(module_decls, ir_module, function_state, local_decls, iterable)

            rngty = ir_iterable.ty
            idx = ir_iterable.ty.constructors[0].field_names.index('lower')
            itty = ir_iterable.ty.constructors[0].field_types[idx]
            
            h = id(node)
            exit_lbl = "_exitloop_lbl_%d" % h
            enter_lbl = "_enterloop_lbl_%d" % h
            reenter_lbl = "_reenterloop_lbl_%d" % h

            result_var = "_loopresult_%d" % h
            context = LoopContext(exit_lbl, reenter_lbl, True, result_var, None)
            function_state.local_symbols.append({name: itty})
            function_state.loops.append(context)
            body_decls = []
            ir_body = typecheck_stmt_block(module_decls, ir_module, function_state, body_decls, body.stmts)
            function_state.local_symbols.pop()
            function_state.loops.pop()

            if context.dest_type is None:
                return ir.CompileError("Loop in expression context must yield a value using 'break' or 'continue")
            local_decls.append(ir.DeclareLocal(context.dest_type, result_var))

            iterable_name = '_iterable_%d' % h
            body_decls.append(ir.DeclareLocal(rngty, iterable_name, location=location))
            body_decls.append(ir.DeclareLocal(itty, name, location=location))
            cond = ir.BinaryOp(ir.BoolType(), ir.LoadLocal(itty, name), '<', ir.LoadMember(itty, ir.LoadLocal(rngty, iterable_name), 'upper'))
            step = ir.StoreLocal(name, ir.BinaryOp(itty, ir.LoadLocal(itty, name), '+', ir.LoadInteger(itty, 1)))
            stmts = [ir.StoreLocal(iterable_name, ir_iterable),
                     ir.StoreLocal(name, ir.LoadMember(itty, ir.LoadLocal(rngty, iterable_name), 'lower')),
                     ir.Goto(enter_lbl),
                     ir.Label(reenter_lbl),
                     step,
                     ir.Label(enter_lbl),
                     ir.IfElse(cond, ir_body + [ir.Goto(reenter_lbl)], []),
                     ir.Label(exit_lbl)]
            if type(context.dest_type) == ir.OptionType:
                init_value = ir.Null(context.dest_type)
            elif type(context.dest_type) == ir.ArrayType:
                init_value = ir.MakeArray(context.dest_type, ())
            return ir.ExprWithStmt(context.dest_type, [ir.StoreLocal(result_var, init_value), ir.Scope(body_decls + stmts)], ir.LoadLocal(context.dest_type, result_var))

        # while cond:
        case ast.WhileExpr(cond, body):
            ir_cond = typecheck_expr(module_decls, ir_module, function_state, local_decls, cond)

            h = id(node)
            exit_lbl = "_exitloop_lbl_%d" % h
            enter_lbl = "_enterloop_lbl_%d" % h

            result_var = "_loopresult_%d" % h
            context = LoopContext(exit_lbl, enter_lbl, True, result_var, None)
            function_state.local_symbols.append({})
            function_state.loops.append(context)
            body_decls = []
            ir_body = typecheck_stmt_block(module_decls, ir_module, function_state, body_decls, body.stmts)
            function_state.local_symbols.pop()
            function_state.loops.pop()

            if context.dest_type is None:
                return ir.CompileError("Loop in expression context must yield a value using 'break' or 'continue")
            local_decls.append(ir.DeclareLocal(context.dest_type, result_var))

            stmts = [ir.Label(enter_lbl),
                     ir.IfElse(ir_cond, ir_body + [ir.Goto(enter_lbl)], []),
                     ir.Label(exit_lbl)]
            if type(context.dest_type) == ir.OptionType:
                init_value = ir.Null(context.dest_type)
            elif type(context.dest_type) == ir.ArrayType:
                init_value = ir.MakeArray(context.dest_type, ())
            return ir.ExprWithStmt(context.dest_type, [ir.StoreLocal(result_var, init_value), ir.Scope(body_decls + stmts)], ir.LoadLocal(context.dest_type, result_var))

        case _:
            assert False, node

def typecheck_stmt(module_decls, ir_module, function_state, local_decls, node):
    location = node.location
    match node:

        # return
        case ast.ReturnStmt(ast.NoExpr):
            if function_state.retty != ir.VoidType():
                descr = f"Can't return 'void' from function returning '{describe(function_state.retty)}'"
                return [ir.CompileError(descr, location=location)]
            else:
                return [ir.Return(location=location)]

        # return <expr>
        case ast.ReturnStmt(expr):
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            if is_error(ir_expr):
                return [ir_expr]
            typed_ir_expr = typecheck_instr(function_state.retty, ir_expr)
            if typed_ir_expr is None:
                descr = f"Can't return '{describe(ir_expr.ty)}' from function returning '{describe(function_state.retty)}'"
                return [ir.CompileError(descr, location=location)]
            else:
                return [ir.ReturnValue(typed_ir_expr, location=location)]

        # assert <expr>
        case ast.AssertStmt(expr):
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            if is_error(ir_expr):
                return [ir_expr]
            if ir_expr.ty != ir.BoolType():
                return [ir.CompileError(f"Expected 'bool' for condition to assert", location=location)]
            else:
                return [ir.Assert(ir_expr, location=location)]

        # let <name> = <expr>
        case ast.AssignStmt(ast.NewIdentifierExpr(name, is_implicit), expr):
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            local_ir = lookup_local(function_state, name)
            implicit_local = lookup_implicit(function_state, ir_expr.ty) if is_implicit else None
            if local_ir is not None:
                return [ir.IgnoreValue(ir_expr), ir.CompileError("Can't redefine local '%s'" % name, location=location)]
            if is_implicit and implicit_local is not None:
                return [ir.IgnoreValue(ir_expr), ir.CompileError("There is already an implicit with type '%s'" % describe(ir_expr.ty), location=location)]
            if is_error(ir_expr):
                return [ir_expr]
            if type(ir_expr) == ir.UntypedNull:
                return [ir.CompileError("Can't assign untyped 'null' to fresh variable '%s' without type declaration" % name, location=location)]                
            function_state.local_symbols[-1][name] = ir_expr.ty
            if is_implicit:
                function_state.implicit_symbols[-1][ir_expr.ty] = name

            local_decls.append(ir.DeclareLocal(ir_expr.ty, name))
            return [ir.StoreLocal(name, ir_expr)]
        
        # <name> = <expr>
        case ast.AssignStmt(ast.IdentifierExpr(name), expr):
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            local_ir = lookup_local(function_state, name)
            if local_ir is None:
                return [ir.IgnoreValue(ir_expr), ir.CompileError("Undefined variable '%s'" % name, location=location)]
            if is_error(ir_expr):
                return [ir_expr]
            typed_ir_expr = typecheck_instr(local_ir.ty, ir_expr)
            return [ir.StoreLocal(name, typed_ir_expr)]

        # (<expr>, <expr>) = <expr>
        case ast.AssignStmt(lhs, rhs) if type(lhs) == ast.TupleExpr:
            ir_rhs = typecheck_expr(module_decls, ir_module, function_state, local_decls, rhs)
            if type(ir_rhs.ty) != ir.TupleType:
                return [ir_rhs, ir.CompileError(f"Type '{describe(ir_rhs.ty)}' is not decomposable")]
            lhs = node.lhs
            if len(ir_rhs.ty.positional) != len(lhs.positional):
                return [ir_rhs, ir.CompileError(f"Can't decompose tuple with {len(ir_rhs.ty.positional)} positional slots into {len(lhs.positional)} slots")]
            stmts = []
            temp_name = new_local_temp(function_state, ir_rhs.ty)
            stmts.append(ir.DeclareLocal(ir_rhs.ty, temp_name, location=location))
            stmts.append(ir.StoreLocal(temp_name, ir_rhs, location=location))
            for idx, l in enumerate(lhs.positional):
                new_node = ast.AssignStmt(l, ast.IndexExpr(ast.IdentifierExpr(temp_name), [ast.IntegerExpr(idx)], location=l.location))
                stmts.extend(typecheck_stmt(module_decls, ir_module, function_state, local_decls, new_node))
            lut = dict(zip(lhs.names, lhs.named))
            for name in sorted(lhs.names):
                l = lut[name]
                new_node = ast.AssignStmt(l, ast.MemberExpr(ast.IdentifierExpr(temp_name), name, location=l.location))
                stmts.extend(typecheck_stmt(module_decls, ir_module, function_state, local_decls, new_node))
            return stmts

        # *ptr = src
        case ast.AssignStmt(ast.UnaryOpExpr('*', ptr), src):
            ir_ptr = typecheck_expr(module_decls, ir_module, function_state, local_decls, ptr)
            ir_src = typecheck_expr(module_decls, ir_module, function_state, local_decls, src)
            if type(ir_ptr.ty) != ir.PointerType:
                assert False, ir.CompileError(f"Cannot dereference non-pointer type '{describe(ir_ptr.ty)}'", location=node.location)
            if ir_ptr.ty.target != ir_src.ty:
                assert False, ir.CompileError(f"Cannot assign '{describe(ir_src.ty)}' to '{describe(ir_ptr.ty.target)}'", location=node.location)

            if type(ir_ptr.ty.target) == ir.TypeDefinition:
                module = module_decls[ir_ptr.ty.target.filename]
                mod, fn = lookup_function([module], '__pack__', ir_module.filename)
                if fn is not None:
                    return [ir.IgnoreValue(ir.CallFunction(ir.VoidType(), fn, (ir_src, ir_ptr), location=location))]

            return [ir.StoreAtAddress(ir_ptr, ir_src)]

        # if lhs == TypCtor(33, let x) { ... }
        case ast.ExprStmt(ast.IfCaseExpr(lhs, rhs, true_body, false_body)):
            return typecheck_pattern_match(module_decls, ir_module, function_state, local_decls, rhs, lhs, true_body, false_body, location)

        # if cond { ... }
        case ast.ExprStmt(ast.IfExpr(cond, true_body, false_body)):
            ir_cond = typecheck_expr(module_decls, ir_module, function_state, local_decls, cond)
            if is_error(ir_cond):
                return [ir_cond]
            unwrap_optional = None
            unwrap_type = None
            if type(ir_cond.ty) == ir.OptionType:
                if type(ir_cond) == ir.LoadLocal:
                    unwrap_optional = ir_cond.name
                    unwrap_type = ir_cond.ty
                ir_cond = ir.UnaryOp(ir.BoolType(), "!", ir.OptionalIsEmpty(ir.BoolType(), ir_cond))
            if ir_cond.ty != ir.BoolType():
                return [ir.CompileError(f"Expected 'bool' for condition to if", location=location)]
            true_decls = []
            if unwrap_optional:
                function_state.access_locals.append({unwrap_optional: ir.OptionalGetValue(unwrap_type.target, ir.LoadLocal(unwrap_type, unwrap_optional))})
            ir_true_body = typecheck_stmt_block(module_decls, ir_module, function_state, true_decls, true_body.stmts)
            if unwrap_optional:
                function_state.access_locals.pop()
            false_decls = []
            ir_false_body = typecheck_stmt_block(module_decls, ir_module, function_state, false_decls, false_body.stmts)
            return [ir.IfElse(ir_cond, true_decls + ir_true_body, false_decls + ir_false_body)]
        
        # for iterator in iterable:
        case ast.ExprStmt(ast.ForExpr(ast.IdentifierExpr(name), iterable, body)):
            ir_iterable = typecheck_expr(module_decls, ir_module, function_state, local_decls, iterable)
            assert not is_error(ir_iterable), ir_iterable
            rngty = ir_iterable.ty
            idx = ir_iterable.ty.constructors[0].field_names.index('lower')
            itty = ir_iterable.ty.constructors[0].field_types[idx]
            
            h = id(node)
            exit_lbl = "_exitloop_lbl_%d" % h
            enter_lbl = "_enterloop_lbl_%d" % h
            reenter_lbl = "_reenterloop_lbl_%d" % h

            function_state.local_symbols.append({name: itty})
            function_state.loops.append(LoopContext(exit_lbl, reenter_lbl, False, None, None))
            body_decls = []
            ir_body = typecheck_stmt_block(module_decls, ir_module, function_state, body_decls, body.stmts)
            function_state.local_symbols.pop()
            function_state.loops.pop()


            iterable_name = '_iterable_%d' % h
            body_decls.append(ir.DeclareLocal(rngty, iterable_name, location=location))
            body_decls.append(ir.DeclareLocal(itty, name, location=location))
            cond = ir.BinaryOp(ir.BoolType(), ir.LoadLocal(itty, name), '<', ir.LoadMember(itty, ir.LoadLocal(rngty, iterable_name), 'upper'))
            step = ir.StoreLocal(name, ir.BinaryOp(itty, ir.LoadLocal(itty, name), '+', ir.LoadInteger(itty, 1)))
            stmts = [ir.StoreLocal(iterable_name, ir_iterable),
                     ir.StoreLocal(name, ir.LoadMember(itty, ir.LoadLocal(rngty, iterable_name), 'lower')),
                     ir.Goto(enter_lbl),
                     ir.Label(reenter_lbl),
                     step,
                     ir.Label(enter_lbl),
                     ir.IfElse(cond, ir_body + [ir.Goto(reenter_lbl)], []),
                     ir.Label(exit_lbl)]
            return [ir.Scope(body_decls + stmts)]

        # for iterator in iterable:
        case ast.ExprStmt(ast.WhileExpr(cond, body)):
            ir_cond = typecheck_expr(module_decls, ir_module, function_state, local_decls, cond)

            h = id(node)
            exit_lbl = "_exitloop_lbl_%d" % h
            enter_lbl = "_enterloop_lbl_%d" % h

            function_state.local_symbols.append({})
            function_state.loops.append(LoopContext(exit_lbl, enter_lbl, False, None, None))
            body_decls = []
            ir_body = typecheck_stmt_block(module_decls, ir_module, function_state, body_decls, body.stmts)
            function_state.local_symbols.pop()
            function_state.loops.pop()


            stmts = [ir.Label(enter_lbl),
                     ir.IfElse(ir_cond, ir_body + [ir.Goto(enter_lbl)], []),
                     ir.Label(exit_lbl)]
            return [ir.Scope(body_decls + stmts)]
        
        case ast.BreakStmt(ast.NoExpr):
            if len(function_state.loops) == 0:
                return [ir.CompileError("'break' outside loop")]
            context = function_state.loops[-1]
            if context.is_expression:
                return [ir.CompileError("'break' without value is illegal in expression context")]
            return [ir.Goto(context.break_label)]
        
        case ast.BreakStmt(expr):
            if len(function_state.loops) == 0:
                return [ir.CompileError("'break' outside loop")]
            context = function_state.loops[-1]
            if not context.is_expression:
                return [ir.CompileError("'break' with value illegal in statement context")]
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            if context.dest_type is None:
                context.dest_type = ir.OptionType(ir_expr.ty)
            elif context.det_type != ir.OptionType(ir_expr.ty):
                return [ir.CompileError(f"Loop yields value of type '{describe(ir.OptionType(ir_expr.ty))}'; but yields type '{describe(context.dest_type)}' elsewhere")]
            return [ir.StoreLocal(context.dest_variable, ir.MakeOptional(context.dest_type, ir_expr)), ir.Goto(context.break_label)]

        case ast.ContinueStmt(ast.NoExpr):
            if len(function_state.loops) == 0:
                return [ir.CompileError("'continue' outside loop")]
            context = function_state.loops[-1]
            if context.is_expression:
                return [ir.CompileError("'continue' without value is illegal in expression context")]
            return [ir.Goto(context.continue_label)]

        case ast.ContinueStmt(expr):
            if len(function_state.loops) == 0:
                return [ir.CompileError("'continue' outside loop")]
            context = function_state.loops[-1]
            if not context.is_expression:
                return [ir.CompileError("'continue' with value illegal in statement context")]
            ir_expr = typecheck_expr(module_decls, ir_module, function_state, local_decls, expr)
            if context.dest_type is None:
                context.dest_type = ir.ArrayType(ir_expr.ty)
            elif context.det_type.elty != ir.ArrayType(ir_expr.ty):
                return [ir.CompileError(f"Loop yields value of type '{describe(ir.ArrayType(ir_expr.ty))}'; but yields type '{describe(context.dest_type)}' elsewhere")]
            return [ir.IgnoreValue(ir.ArrayAppend(ir.VoidType(), ir.LoadLocal(context.dest_type, context.dest_variable), ir_expr)), ir.Goto(context.continue_label)]


        case ast.ExprStmt(expr):
            return [ir.IgnoreValue(typecheck_expr(module_decls, ir_module, function_state, local_decls, expr))]
        case _:
            assert False, node


def compile_regex_function(ir_module, bytecode, num_groups, group_mappings, string_ty):
    if num_groups > 0:
        names = tuple(sorted(group_mappings.keys()))
        named = tuple([string_ty] * len(group_mappings))
        positional = tuple([string_ty] * (num_groups - len(group_mappings)))
        retty = ir.OptionType(ir.TupleType(positional, named, names, 'uninitialized', 'uninitialized'))
        declare.optimize_datatype_layout(retty)
    else:
        retty = ir.BoolType()
    fnname = "regex_%d" % (abs(hash(tuple(bytecode))))

    argtys = (string_ty,)
    argnames = ('string',)
    gmappings = tuple((k, group_mappings[k]) for k in sorted(group_mappings.keys()))
    body = [ir.ReturnValue(ir.RegexMatch(retty, ir.LoadLocal(string_ty, 'string'), bytecode, num_groups, gmappings))]
    return ir.FunctionDefinition(ir_module.filename, retty, fnname, (), (), argtys, argnames, body, True)

def typecheck_function(module_decls, ir_module, ir_function, fn):
    args = dict(zip(ir_function.argnames, ir_function.argtys))
    args.update(dict(zip(ir_function.argnames_implicit, ir_function.argtys_implicit)))
    function_state = FunctionState(ir_function.retty, [args], [{}], [dict(zip(ir_function.argtys_implicit, ir_function.argnames_implicit))], [], [])
    body = []
    local_decls = []
    for stmt in fn.body:
        body.extend(typecheck_stmt(module_decls, ir_module, function_state, local_decls, stmt))
    ir_function.__dict__['body'] = tuple(local_decls + body)

    str_ty = lookup(module_decls['__builtins__/string.ce'].types, 'String')
    for fndef in function_state.regexs:
        ir_module.functions.append(fndef)

def lookup(lst, name):
    for l in lst:
        if l.name == name:
            return l
    return None

def lookup_constructor(ir_modules, name, current_module):
    found = None
    found_is_exported = False
    for ir_module in ir_modules:
        for ty in ir_module.types:
            if type(ty) == ir.TypeDefinition:
                for ctor in ty.constructors:
                    if ctor.name == name:
                        if found is None:
                            found = ty, ctor
                            found_is_exported = getattr(ty, 'exported', True) or current_module == ty.filename
                        else:
                            assert False, "ambigious constructor: %s.%s vs %s.%s" % (found[0].name, found[1], ty.name, ctor)
            elif ty.name == name and type(ty) in (ir.CStructDefinition, ir.CUnionDefinition):
                if found is None:
                    found = ty, None
                    found_is_exported = True
                else:
                    assert False, "ambigious constructor: %s.%s vs %s.%s" % (found[0].name, found[1], ty.name, ctor)
    if found is None:
        return None, None
    assert found_is_exported, "%s:%s (%s) is not exported" % (found[0].filename, found[0].name, found[1].name)
    return found

def lookup_function(ir_modules, name, current_module):
    found = None
    found_is_exported = False
    for ir_module in ir_modules:
        for fn in ir_module.functions:
            if fn.name == name:
                if found is None:
                    found_is_exported = getattr(fn, 'exported', True) or current_module == fn.filename
                    found = ir_module, fn
                else:
                    assert False, "ambigious function: %s/%s vs %s/%s" % (found[0].filename, found[1].name, ir_module.filename, fn.name)
    if found is None:
        return None, None
    assert found_is_exported, "%s:%s is not exported" % (found[0].filename, found[1].name)
    return found

def lookup_variable(ir_modules, name, return_none_if_not_found=False):
    found = None
    for ir_module in ir_modules:
        for var in ir_module.variables:
            if var.name == name:
                if found is None:
                    found = ir_module, var
                else:
                    assert False, "Ambigious %s/%s vs %s/%s" % (found[0].filename, found[1].name, ir_module.filename, var.name)
    if return_none_if_not_found and found is None:
        return None, None
    assert found, "Not found: %s" % name
    return found

def typecheck_module(module_decls, ast_module):
    ir_module = module_decls[ast_module.filename]
    for d in list(ast_module.defs):
        match d:
            case ast.FunctionDef():
                #print("typechecking function: ", d.name)
                ir_function = lookup(ir_module.functions, d.name)
                typecheck_function(module_decls, ir_module, ir_function, d)


if __name__ == '__main__':
    import frontend.parser as parser
    
    def test(code):
        filename = "test.ch"
        ast = parser.parse_text(filename, code)
        ir = typecheck_module(ast, {})
        #import pprint
        #pprint.pprint(ir)

    code = """
int test0():
    return 0

void test1():
    return

int test2(int x):
    return x

int test3():
    return

void test4():
    return 0

void test5():
    return x

void test6():
    let x = y

int test6():
    let x = 1
    return x

void test7():
    let x = 1
    let x = 2

void* test8():
    return null

void test9():
    let x = null

void test10():
    let x = 1 + 2

void test10():
    let x = a + b where:
        let a = 3
        let b = 1

(int, float) test11():
    return (99, 0.1)

void test12():
    (let x, let y) = (99, 0.1)

void test13():
    (b: let x, a: let y) = (a: 99, b: 0.1)

int|float test14():
    return 1
    return 1.0

#(int|float, float|int) test15():
#    return (1.0, 2)

"""
    test(code)