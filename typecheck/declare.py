import frontend.astnodes as ast
import backend.ir as ir
from dataclasses import dataclass
import math


LAYOUT_CACHE = {}
MACHINE_DEF = None

def load_machine_def(machine_def):
    machine_def = machine_def.copy()
    for t in list(machine_def['types'].values()):
        machine_def['types'][ir.CNamedType(t['typename'], None)] = t
    machine_def['types']['padding'] = create_padding_info(machine_def['types'])
    global MACHINE_DEF
    MACHINE_DEF = machine_def['types']


def make_ir_for_asttype(filename, astty):
    match astty:
        case ast.TypeDef():
            # NOTE: At this point the TypeDefinition isn't fully
            # intialized as the constructors are missing. However,
            # we need to declare all types before we can define the
            # constructors, thus, we leave the list of constructors
            # out here.
            tagless = len(astty.constructors) == 0 or any(ctor.tag_value == ast.IdentifierExpr('void') for ctor in astty.constructors)
            return ir.TypeDefinition(filename, astty.name, 'uninitialized', 'uninitialized', exported=astty.export, tagless=tagless)
        case ast.CStructDef():
            if astty.field_names is None:
                return ir.CStructDefinition(filename, astty.name, None, None, None, None)
            return ir.CStructDefinition(filename, astty.name, 'uninitialized', 'uninitialized', 'uninitialized', 'uninitialized')
        case ast.CUnionDef():
            return ir.CUnionDefinition(filename, astty.name, 'uninitialized', 'uninitialized')
        case ast.CEnumDef():
            return ir.CStructDefinition(filename, astty.name, astty.enumerators)
        case ast.CTypedefDef():
            return ir.CTypedefDefinition(filename, astty.name, 'uninitialized')
    return None

def declare_module_types(ast_module):
    types = []
    for node in ast_module.defs:
        res = make_ir_for_asttype(ast_module.filename, node)
        if res is not None:
            types.append(res)
    main_module = ast_module.main_module if type(ast_module) == ast.ModuleDef else False
    return ir.ModuleDefinition(ast_module.filename, 'uninitialized', 'uninitialized', types, 'uninitialized', main_module)

def lookup_type(ir_modules, filenames, tyname, current_module, on_failure=None):
    found = None
    found_non_exported = None
    for filename in filenames:
        mod = ir_modules[filename]
        for ty in mod.types:
            if ty.name == tyname:
                if type(found) == ir.CStructDefinition and found.field_names is None:
                    found = ty
                elif found is not None:
                    assert False, "ambigious typename '%s'" % tyname
                elif type(ty) in (ir.CStructDefinition, ir.CUnionDefinition, ir.CEnumDefinition, ir.CTypedefDefinition) or ty.exported or current_module == ty.filename:
                    found = ty
                else:
                    found_non_exported = (filename, tyname)
    if not found and on_failure:
        return on_failure
    if not found and found_non_exported:
        assert False, "attempting to import non-exported type %s:%s" % found_non_exported
    assert found, (tyname, filenames)
    return found
    

def resolve_type(ast_type, ir_modules, namespaces, current_module):
    match ast_type:
        case ast.NamedType('implicit', 'u8'):
            return ir.IntegerType(8, signed=False)
        case ast.NamedType('implicit', 'u16'):
            return ir.IntegerType(16, signed=False)
        case ast.NamedType('implicit', 'u32'):
            return ir.IntegerType(32, signed=False)
        case ast.NamedType('implicit', 'u64'):
            return ir.IntegerType(64, signed=False)
        case ast.NamedType('implicit', 'i8'):
            return ir.IntegerType(8, signed=True)
        case ast.NamedType('implicit', 'i16'):
            return ir.IntegerType(16, signed=True)
        case ast.NamedType('implicit', 'i32'):
            return ir.IntegerType(32, signed=True)
        case ast.NamedType('implicit', 'i64'):
            return ir.IntegerType(64, signed=True)
        case ast.NamedType('implicit', 'int'):
            return ir.IntegerType(32, signed=True)
        case ast.NamedType('implicit', 'uint'):
            return ir.IntegerType(32, signed=False)
        case ast.NamedType('implicit', 'byte'):
            return ir.IntegerType(8, signed=False)
        case ast.NamedType('implicit', 'float'):
            return ir.FloatType(32)
        case ast.NamedType('implicit', 'bool'):
            return ir.BoolType()
        case ast.NamedType('implicit', 'void'):
            return ir.VoidType()
        case ast.CConstType(ty):
            return ir.CConstType(resolve_type(ty, ir_modules, namespaces, current_module))
        case ast.CNamedType(name, None) if ir.CNamedType(name, None) in MACHINE_DEF:
            return ir.CNamedType(name, None)
        case ast.CArrayType(elty):
            return ir.CArrayType(resolve_type(elty, ir_modules, namespaces, current_module))
        case ast.CNamedType('void', None):
            return ir.VoidType()
        case ast.CNamedType(name, typekind):
            return lookup_type(ir_modules, namespaces['implicit'], name, ir.CUnknownType(name, typekind), current_module)
        case ast.CFunctionPointerType(retty, argtys, argnames):
            argtys = tuple(resolve_type(p, ir_modules, namespaces, current_module) for p in argtys)
            return ir.CFunctionPointerType(resolve_type(retty, ir_modules, namespaces, current_module), argtys, tuple(argnames), varargs=False)
        case ast.NamedType(namespace, name):
            assert namespace is not None
            return lookup_type(ir_modules, namespaces[namespace], name, current_module)
        case ast.PointerType(target):
            return ir.PointerType(resolve_type(target, ir_modules, namespaces, current_module))
        case ast.TupleType(positional, named, names):
            positional = tuple(resolve_type(p, ir_modules, namespaces, current_module) for p in positional)
            named = tuple(resolve_type(p, ir_modules, namespaces, current_module) for p in named)
            return ir.TupleType(positional, named, tuple(names), 'uninitialized', 'uninitialized')
        case ast.UnionType(types):
            def order(ty):
                return repr(ty)
            return ir.UnionType(tuple(sorted((resolve_type(t, ir_modules, namespaces, current_module) for t in types), key=order)))
        case ast.FunctionType(retty, argtys, argnames):
            argtys = tuple(resolve_type(p, ir_modules, namespaces, current_module) for p in argtys)
            return ir.FunctionType(resolve_type(retty, ir_modules, namespaces, current_module), argtys, tuple(argnames))
        case ast.ArrayType(ty):
            return ir.ArrayType(resolve_type(ty, ir_modules, namespaces, current_module))
        case ast.OptionType(ty):
            return ir.OptionType(resolve_type(ty, ir_modules, namespaces, current_module))
        case _:
            assert False, ast_type


def declare_module_rest_one(node, ir_modules, namespaces, ast_module, global_vars, funcs, imported_namespaces, current_module):
    match node:
        case ast.VariableDef():
            ty = resolve_type(node.ty, ir_modules, namespaces, ast_module.filename)
            global_vars.append(ir.GlobalVariableDefinition(ast_module.filename, ty, node.name, 'uninitialized'))

        case ast.FunctionDef():
            retty = resolve_type(node.retty, ir_modules, namespaces, ast_module.filename)
            argtys = tuple(resolve_type(argty, ir_modules, namespaces, ast_module.filename) for argty in node.argtys)
            argtys_implicit = tuple(resolve_type(argty, ir_modules, namespaces, ast_module.filename) for argty in node.argtys_implicit)
            if node.name == '__unpack__':
                retty.__dict__['optimize_layout'] = False
            funcs.append(ir.FunctionDefinition(ast_module.filename, retty, node.name, argtys_implicit, tuple(node.argnames_implicit), argtys, tuple(node.argnames), 'uninitialized', exported=node.export))

        case ast.TypeDef():
            ctors = []
            for idx, ctor in enumerate(node.constructors):
                if ctor.field_types is not None:
                    ftys = tuple(resolve_type(fty, ir_modules, namespaces, ast_module.filename) for fty in ctor.field_types)
                    fnames = tuple(ctor.field_names)
                    without_arglist = False
                else:
                    ftys = ()
                    fnames = ()
                    without_arglist = True
                
                if ctor.tag_value is None or ctor.tag_value == ast.IdentifierExpr('void'):
                    tag_value = idx
                elif type(ctor.tag_value) == ast.IntegerExpr:
                    tag_value = ctor.tag_value.value
                else:
                    assert False, f"Unsupported tag value {ctor.tag_value}"
                ctors.append(ir.TypeConstructor(ctor.name, ftys, fnames, without_arglist, layout_types='uninitialized', layout_names='uninitialized', tag_value=tag_value))
            tydef = lookup_type(ir_modules, [ast_module.filename], node.name, current_module)
            # Ugly hack
            tydef.__dict__['constructors'] = tuple(ctors)

        case ast.CTypedefDef():
            tydef = lookup_type(ir_modules, [ast_module.filename], node.name, current_module)
            # Ugly hack
            tydef.__dict__['definition'] = resolve_type(node.definition, ir_modules, namespaces, ast_module.filename)

        case ast.CStructDef():
            if node.field_types is not None:
                ftys = tuple(resolve_type(fty, ir_modules, namespaces, ast_module.filename) for fty in node.field_types)
                fnames = tuple(node.field_names)
            else:
                ftys = None
                fnames = None
            cstruct = lookup_type(ir_modules, [ast_module.filename], node.name, current_module)
            # Ugly hack
            cstruct.__dict__['field_names'] = fnames
            cstruct.__dict__['field_types'] = ftys

        case ast.ImportDef(filename, namespace):
            if namespace not in imported_namespaces:
                imported_namespaces[namespace] = ir.Namespace(namespace, [])
            imported_namespaces[namespace].modules.append(ir_modules[filename])

        case ast.CFunctionDef():
            retty = resolve_type(node.retty, ir_modules, namespaces, ast_module.filename)
            argtys = [resolve_type(argty, ir_modules, namespaces, ast_module.filename) for argty in node.argtys]
            funcs.append(ir.CFunctionDefinition(ast_module.filename, retty, node.name, argtys, node.argnames, node.varargs))

        case ast.CConstDefine():
            if node.ty:
                ty = resolve_type(node.ty, ir_modules, namespaces, ast_module.filename)
            else:
                ty = None
            global_vars.append(ir.CGlobalVariableDefinition(ast_module.filename, ty, node.name, has_address=False, assignable=False))

def declare_module_rest(ast_module, ir_modules):
    namespaces = {'implicit': [ast_module.filename]}
    for node in ast_module.defs:
        match node:
            case ast.ImportDef():
                namespaces.setdefault(node.namespace, []).append(node.filename)
            case ast.CInclude():
                namespaces['implicit'].append(node.filename)

    funcs = []
    global_vars = []
    imported_namespaces = {'implicit': ir.Namespace('implicit', [ir_modules[ast_module.filename]])}
    for node in ast_module.defs:
        declare_module_rest_one(node, ir_modules, namespaces, ast_module, global_vars, funcs, imported_namespaces, ast_module.filename)

    # Ugly hack
    ir_modules[ast_module.filename].__dict__['variables'] = global_vars
    ir_modules[ast_module.filename].__dict__['functions'] = funcs
    ir_modules[ast_module.filename].__dict__['namespaces'] = list(imported_namespaces.values())




def datatype_align_and_size(ty):
    if type(ty) == ir.PointerType:
        mdef = MACHINE_DEF['void*']
        return mdef['alignment'], mdef['size']
    elif type(ty) != ir.TypeDefinition and ty in MACHINE_DEF:
        mdef = MACHINE_DEF[ty]
        return mdef['alignment'], mdef['size']
    elif ty == ir.BoolType():
        return 1, 1
    return optimize_datatype_layout(ty)

def emit_padding(size, padding, field_types, field_names):
    padinfo = MACHINE_DEF['padding']
    while padding > 0:
        for num_bytes, datatype in padinfo:
            if padding >= num_bytes and size % num_bytes == 0:
                break
        else:
            assert False, "Bug: padding=%d, pads=%s" % (padding, padinfo)
        padding -= num_bytes
        size += num_bytes
        field_types.append(datatype)
        field_names.append("__pad%s__" % len(field_names))
        


def struct_alignment_and_padding(fields):
    if len(fields) == 0:
        return [], [], 1, 0
    # Fields is a list of tuples (size, align)
    
    field_info = [(fty, fname, datatype_align_and_size(fty)) for fty, fname in fields]
    # Step 1: Find the struct alignment (maximum alignment of any field)
    struct_alignment = max(align for (_fty, _fname, (_size, align)) in field_info)
    
    # Step 2: Initialize the size of the struct to 0
    current_size = 0

    # Step 3: Place each field with proper alignment
    fieldtypes_result = []
    fieldnames_result = []
    for (fty, fname, (align, size)) in field_info:
        padding = (align - (current_size % align)) % align
        emit_padding(current_size, padding, fieldtypes_result, fieldnames_result)
        current_size += padding        
        current_size += size

        fieldtypes_result.append(fty)
        fieldnames_result.append(fname)
    
    # The final size and alignment of the struct
    return fieldtypes_result, fieldnames_result, struct_alignment, current_size

def type_key(tydef):
    key = tydef
    if type(tydef) == ir.TypeDefinition:
        key = (tydef.filename, tydef.name)
    return key

def optimize_datatype_layout(tydef):
    key = type_key(tydef)
    if key in LAYOUT_CACHE:
        return LAYOUT_CACHE[key]
    align = 1
    size = 1
    if type(tydef) == ir.TupleType:
        all_fields = [(fty, fname) for fname, fty in enumerate(tydef.positional)] + [(fty, fname) for fname, fty in zip(tydef.names, tydef.named)]
        fieldtypes_w_padding, fieldnames_w_padding, align, size = struct_alignment_and_padding(all_fields)
        tydef.__dict__['layout_types'] = tuple(fieldtypes_w_padding)
        tydef.__dict__['layout_names'] = tuple(fieldnames_w_padding)
        LAYOUT_CACHE[key] = (align, size)
        return align, size
    elif type(tydef) == ir.CStructDefinition:
        all_fields = zip(tydef.field_types, tydef.field_names)
        fieldtypes_w_padding, fieldnames_w_padding, align, size = struct_alignment_and_padding(all_fields)
        tydef.__dict__['layout_types'] = tuple(fieldtypes_w_padding)
        tydef.__dict__['layout_names'] = tuple(fieldnames_w_padding)
        LAYOUT_CACHE[key] = (align, size)
        return align, size
    elif type(tydef) == ir.CTypedefDefinition:
        return datatype_align_and_size(tydef.definition)
    elif type(tydef) == ir.ArrayType:
        # Trigger optimization of element type
        datatype_align_and_size(tydef.elty)
        # TODO: How to get the proper alignment and size of types that are defined in-language
        return 8, 16
    elif type(tydef) == ir.OptionType:
        al, sz = datatype_align_and_size(tydef.target)
        return 8, 8 + sz
    elif type(tydef) == ir.FunctionType:
        return 16

    if type(tydef) != ir.TypeDefinition:
        assert False, tydef
    common_fields = list(zip(tydef.constructors[0].field_types, tydef.constructors[0].field_names))
    for ctor in tydef.constructors:
        new_common_fields = []
        for t, n in zip(ctor.field_types, ctor.field_names):
            if (t, n) in common_fields:
                new_common_fields.append((t, n))
        common_fields = new_common_fields
    if not tydef.tagless:
        assert len(tydef.constructors) <= 256
        bits = 8
        # We actually don't store the tag value, but instead an index value that is
        # guaranteed to have the values 0, 1, 2, ..., because this simplifies the
        # compiler and generated code. The actual tag value is then looked up in a
        # array using the index.
        tag = (ir.IntegerType(bits, False), '__index__')
        common_fields.append(tag)

    layouts = []
    for ctor in tydef.constructors:
        all_fields_except_tag = list(zip(ctor.field_types, ctor.field_names))
        if tydef.optimize_layout:
            all_fields_except_tag = sorted(all_fields_except_tag, key=lambda x: datatype_align_and_size(x[0]))
        fieldtypes_w_padding, fieldnames_w_padding, al, sz = struct_alignment_and_padding(all_fields_except_tag)
        size = max(size, sz)
        align = max(align, al)
        layouts.append((ctor, fieldtypes_w_padding, fieldnames_w_padding, sz))

    # Almost done, just add the padding to ensure all ctors have the same size and we're done.
    if not tydef.tagless:
        size += 1 # Add the space for the tag.
    final_size = size + (align - (size % align)) % align
    # NOTE: We add the tag last because it has the smallest size and alignment requirement
    # NOTE: We should ideally try to find common location for the __index__ field without having
    #       to add a byte to the end of the type.
    for ctor, fieldtypes_w_padding, fieldnames_w_padding, sz in layouts:
        padding = final_size - sz
        emit_padding(sz, padding, fieldtypes_w_padding, fieldnames_w_padding)
        if not tydef.tagless:
            assert fieldnames_w_padding[-1].startswith('__pad'), fieldnames_w_padding[-1]

            # Split up large padding (32 bit ints) into smaller, such that the tag take the last 8 bits only
            while fieldtypes_w_padding[-1].bits > 8:
                new_bits = fieldtypes_w_padding[-1].bits / 2
                fieldtypes_w_padding[-1] = ir.IntegerType(new_bits, False)
                fieldtypes_w_padding.append(ir.IntegerType(new_bits, False))
                fieldnames_w_padding.append('__pad%d__' % len(fieldtypes_w_padding))

            assert fieldtypes_w_padding[-1] == ir.IntegerType(8, False)
            fieldnames_w_padding[-1] = '__index__'

        ctor.__dict__['layout_types'] = tuple(fieldtypes_w_padding)
        ctor.__dict__['layout_names'] = tuple(fieldnames_w_padding)
    tydef.__dict__['common_names'] = tuple(fname for _fty, fname in common_fields)

    LAYOUT_CACHE[key] = (align, final_size)
    return align, final_size

def create_padding_info(datatypes):
    result = {}
    for ty, info in datatypes.items():
        if type(ty) == ir.IntegerType and ty.bits // 8 == info['alignment']:
            result[info['alignment']] = ty
    return sorted(result.items(), reverse=True)

def declare_datatype_layout(ir_modules):
    for ir_module in ir_modules.values():
        #import pprint
        #pprint.pprint(ir_module)
        for tydef in ir_module.types:
            if not isinstance(tydef, ir.CType):
                optimize_datatype_layout(tydef)
