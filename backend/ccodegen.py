import backend.ir as ir
import json

BUILTINS = """
#include <assert.h>
#include <string.h>
#include <stdlib.h>
#include <string.h>
#include "cedar/re.h"
typedef unsigned char _ch_bool;
typedef struct { unsigned length; void* data; } _ch_array;

static _ch_bool array_equals(_ch_array lhs, _ch_array rhs, int element_size) {
    return (lhs.length == rhs.length) && (memcmp(lhs.data, rhs.data, lhs.length * element_size) == 0);
}

static void array_append(_ch_array* array, int element_size, void* element) {
    unsigned old_byte_size = array->length * element_size;
    unsigned new_byte_size = old_byte_size + element_size;
    void* new_data = 0;

    /* Check if array is on the stack (assuming stack grows towards lower addresses) */
    int stack_test;
    if ((void*)&stack_test < array->data) {
        new_data = malloc(new_byte_size);
        memcpy(new_data, array->data, old_byte_size);
    } else {
        new_data = realloc(array->data, new_byte_size);
    }

    /* Copy new element to the end of the array */
    memcpy((char*)new_data + old_byte_size, element, element_size);

    array->data = new_data;
    array->length++;
}

static void* array_pop(_ch_array* array, int element_size) {
    array->length -= 1;
    assert(array->length >= 0);
    return ((char*)array->data) + array->length * element_size;
}

static void* member_ptr(void* baseptr, unsigned char* lut, int index_offset) {
    int tag = ((unsigned char*)baseptr)[index_offset];
    int member_offset = lut[tag];
    return &((unsigned char*)baseptr)[member_offset];
}

static int type_tag(void* baseptr, int* lut, int index_offset) {
    int tag = ((unsigned char*)baseptr)[index_offset];
    return lut[tag];
}

"""


class FuncCodeGen:
    def __init__(self, machine_def, ir_modules):
        self.machine_def = machine_def
        self.ir_modules = ir_modules
        self.includes = set()
        self.decls = []
        self.code = []
        self.indent_level = 0
        self.generated_funcs = set()
        self.generated_types = {}
        self.generated_rtti = {}
        self.defined_symbols = {}
        self.defined_symbol_data = []
        self.defined_strings = {}
        self.defined_string_data = ""
        self.function_decls = []
        self.common_member_luts = {}


    def get_code(self):
        symdefs = ['static const char* _CH_SYMBOL_VALUES = "%s";' % "".join(self.defined_symbol_data)]
        byte_array = bytearray(self.defined_string_data.encode('utf-8'))
        strdefs = ['static unsigned char _CH_STRING_VALUES[] = {%s};' % ",".join(str(b) for b in byte_array)]
        return BUILTINS + "\n".join(list(self.includes) + symdefs + strdefs + self.decls + self.code)

    def indent(self):
        return "    " * self.indent_level
    
    def internalize_symbol(self, value):
        if value in self.defined_symbols:
            return self.defined_symbols[value]
        else:
            idx = sum(len(s) - 1 for s in self.defined_symbol_data)
            self.defined_symbols[value] = idx
            self.defined_symbol_data.append(value + "\\0")
            return idx
        
    def internalize_string(self, value):
        if value in self.defined_strings:
            return "&_CH_STRING_VALUES[%d]" % self.defined_strings[value]
        else:
            idx = self.defined_string_data.find(value)
            if idx == -1:
                idx = len(self.defined_string_data)
                self.defined_string_data += value
            self.defined_strings[value] = idx
            return "&_CH_STRING_VALUES[%d]" % idx

    def function_signature(self, func_def: ir.FunctionDefinition):
        args = list(zip(func_def.argtys_implicit, func_def.argnames_implicit)) + list(zip(func_def.argtys, func_def.argnames))
        arglist = ", ".join(f"{self.generate_type(arg_type)} {arg_name}" for arg_type, arg_name in args)
        return f"{self.generate_type(func_def.retty)} {self.func_name(func_def)}({arglist})"

    def declare_function(self, func_def: ir.FunctionDefinition):
        self.code.append(f"{self.function_signature(func_def)};")

    def generate(self, func_def: ir.FunctionDefinition):
        self.code.append(f"{self.function_signature(func_def)} {{")
        self.indent_level += 1
        self.function_decls = []
        begin_idx = len(self.code)
        for instruction in func_def.body:
            self.generate_instruction(instruction)
        self.indent_level -= 1
        self.code.append("}\n")
        if len(self.function_decls) > 0:
            self.code.insert(begin_idx, "".join(self.function_decls))

    def ctor_name(self, ctor):
        match ctor:
            case ir.TypeConstructor():
                return f"ch_ctor_{ctor.name}_{abs(hash(ctor))}"
            case ir.CStructDefinition():
                return f"ch_cstruct_{ctor.name}_{abs(hash(ctor))}"
        assert False, ctor
    
    def func_name(self, func_def):
        # Do not name-mangle the main function.
        if func_def.name == 'main' and self.ir_modules[func_def.filename].main_module:
            return 'main'
        return f"ch_func_{func_def.name}_{abs(hash(func_def.filename))}"
    
    def generate_tag_lut(self, ty):
        if (ty, '$$tag$$') in self.common_member_luts:
            return self.common_member_luts[(ty, '$$tag$$')]

        ctyname = self.generate_type(ty)
        lutname = f"LUT_tag_{ctyname.replace(' ', '_')}"
        values = ", ".join(str(ctor.tag_value) for ctor in ty.constructors)
        lut_decl = f"int {lutname}[] = {{ {values} }};\n"
        self.decls.append(lut_decl)
        self.common_member_luts[(ty, '$$tag$$')] = lutname
        return lutname
    
    def generate_common_member_lut(self, ty, fieldname):
        if (ty, fieldname) in self.common_member_luts:
            return self.common_member_luts[(ty, fieldname)]

        ctyname = self.generate_type(ty)
        lutname = f"LUT_{ctyname.replace(' ', '_')}_{fieldname}"
        offsets = ", ".join(f"offsetof({ctyname}, ch_{ty.constructors[i].name}.ch_{fieldname})" for i in range(len(ty.constructors)))
        lut_decl = f"unsigned char {lutname}[] = {{ {offsets} }};\n"
        self.decls.append(lut_decl)
        self.common_member_luts[(ty, fieldname)] = lutname
        return lutname
        
    
    def generate_get_index_function(self, array_type):
        eltyname = self.generate_type(array_type.elty)
        fnname = "get_index_array_of_" + eltyname.replace(" ", "_")
        if fnname in self.generated_funcs:
            return fnname
        self.decls.append(f"{eltyname}* {fnname}(_ch_array array, unsigned index) {{ assert(array.length > index); return &(({eltyname}*)array.data)[index]; }}")
        self.generated_funcs.add(fnname)
        return fnname

    def generate_type_definition(self, ty) -> str:
        # First, declare the union-of-structs corresponding to the type+concstructors.
        # NOTE: Since we're calling generate_type() recursively, we can't output directly to self.decls
        decls = []
        fname = ty.filename.replace("/", "_").replace(".", "_")
        tyname = f"ch_{ty.name}_{fname}_{abs(hash(ty))}"
        self.generated_types[ty] = "union " + tyname        
        self.decls.append(f"union {tyname};")

        decls.append("union %s {" % tyname)
        for ctor in ty.constructors:
            fields = " ".join("%s ch_%s;" % (self.generate_type(fty), fname) for fty, fname in zip(ctor.layout_types, ctor.layout_names))
            decls.append(f"    struct {{ {fields} }} ch_{ctor.name};")
        decls.append("};")

        # Second, emit macros for each constructor
        for idx, ctor in enumerate(ty.constructors):
            def init_value(fname):
                if fname in ctor.field_names:
                    return "eval_" + fname
                if fname == '__index__':
                    return str(idx)
                assert '__pad' in fname, (fname, ctor.field_names)
                return '0'
            ctorname = self.ctor_name(ctor)
            args = ", ".join(["target"] + ["arg_%s" % fname for fname in ctor.field_names])
            evals = "; ".join("%s eval_%s = arg_%s" % (self.generate_type(fty), fname, fname) for fty, fname in zip(ctor.field_types, ctor.field_names))
            inits = "; ".join("target.ch_%s.ch_%s = %s" % (ctor.name, fname, init_value(fname)) for fname in ctor.layout_names)
            decls.append("#define %s(%s) do { %s; %s; } while (0)" % (ctorname, args, evals, inits))
        self.decls.extend(decls)
        return "union " + tyname

    def generate_type(self, ty: ir.Type) -> str:
        if ty in self.generated_types:
            return self.generated_types[ty]
        match ty:
            case ir.IntegerType(bits, signed):
                return self.machine_def['types'][ty]['typename']
            case ir.FloatType(bits):
                return self.machine_def['types'][ty]['typename']
            case ir.VoidType():
                return "void"
            case ir.BoolType():
                return "_ch_bool"
            case ir.ArrayType(elty):
                return "_ch_array"
            case ir.CNamedType(name, None):
                return name
            case ir.CConstType(type):
                return f"{self.generate_type(type)} const"
            case ir.CNamedType(name, typekind):
                return f"{typekind} {name}"
            case ir.PointerType(target):
                return "%s*" % self.generate_type(target)
            case ir.PaddingType(bytes):
                return "uint%d_t" % (8 * bytes)
            case ir.RttiType():
                return "__ch_rtti"
            case ir.TupleType(positional, named, names, layout_types, layout_names):
                c_pos = " ".join("%s ch_%s;" % (self.generate_type(t), idx) for idx, t in enumerate(positional))
                name_dict = dict(zip(names, named))
                c_named = " ".join("%s ch_%s;" % (self.generate_type(name_dict[name]), name) for name in sorted(names))
                name = "ch_tuple_%d" % abs(hash(ty))
                self.decls.append(f"typedef struct {{ {c_pos} {c_named} }} {name};")
                self.generated_types[ty] = name

                all_fields = list(zip(positional, range(len(positional)))) + list(zip(named, names))
                args = ", ".join(["target"] + ["arg_%s" % fname for _fty, fname in all_fields])
                evals = " ".join("%s eval_%s = arg_%s;" % (self.generate_type(fty), fname, fname) for fty, fname in all_fields)

                all_field_names = [fname for (_fty, fname) in all_fields]
                inits = " ".join("target.ch_%s = eval_%s;" % (fname, fname) for fname in all_field_names)
                pad_inits = " ".join("target.ch_%s = 0;" % fname for fname in layout_names if fname not in all_field_names)
                self.decls.append("#define %s_ctor(%s) do { %s %s %s } while (0)" % (name, args, evals, inits, pad_inits))
                self.generated_types[ty] = name
                return name
            case ir.UnionType(types):
                mems = " ".join("%s _%s;" % (self.generate_type(t), idx) for idx, t in enumerate(types))
                name = "ch_union_%d" % abs(hash(ty))
                self.decls.append(f"typedef struct {{ int _tag; union {{ {mems} }} value; }} {name};")
                self.generated_types[ty] = name
                return name
            case ir.TypeDefinition():
                return self.generate_type_definition(ty)
            case ir.OptionType(t):
                cty = self.generate_type(t)
                name = "ch_option_%d" % abs(hash(ty))
                self.decls.append(f"typedef union {{ struct {{ unsigned char _has_value; {cty} _value; }} present; struct {{ unsigned char _has_value; }} absent; }} {name};")
                self.generated_types[ty] = name
                return name
            case ir.FunctionType(retty, argtys):
                arglist = ", ".join(f"{self.generate_type(arg_type)}" for arg_type in argtys)
                name = "_ch_funcptr_%d" % abs(hash(ty))
                self.decls.append(f"typedef {self.generate_type(retty)} (*{name})({arglist});")
                self.generated_types[ty] = name
                return name
            case ir.CStructDefinition():
                # Emit macro for constructor
                ctorname = self.ctor_name(ty)
                args = ", ".join(["target"] + ["arg_%s" % fname for fname in ty.field_names])
                inits = "; ".join("target.%s = arg_%s" % (fname, fname) for fname in ty.field_names)
                self.decls.append("#define %s(%s) do { %s; } while (0)" % (ctorname, args, inits))

                # TODO: For all these #includes here, we need to somehow handle that #defines in the
                # included file might name-clash with the generated code. Suggestion is to do #undef of everything
                # that isn't used in the generated code, and the remaining #defines we rename by repeating the definition
                # but under a different name that does not name-clash.
                self.includes.add(f'#include "{ty.filename}"')
                name = f"struct {ty.name}"
                self.generated_types[ty] = name
                return name
            case ir.CUnionDefinition():
                self.includes.add(f'#include "{ty.filename}"')
                return f"union {ty.name}"
            case ir.CEnumDefinition():
                self.includes.add(f'#include "{ty.filename}"')
                return f"enum {ty.name}"
            case ir.CTypedefDefinition():
                self.includes.add(f'#include "{ty.filename}"')
                return f"{ty.name}"
            case _:
                raise ValueError(f"Unknown type: {ty}")

    def generate_instruction(self, instruction: ir.Instruction):
        match instruction:
            case ir.StoreAtAddress(address, expr):
                self.code.append(f"{self.indent()}*{self.generate_expression(address)} = {self.generate_expression(expr)};")
            case ir.DeclareLocal(declare_type=declare_type, name=name):
                self.code.append(f"{self.indent()}{self.generate_type(declare_type)} {name};")
            case ir.StoreLocal(name=name, value=value):
                self.code.append(f"{self.indent()}{name} = {self.generate_expression(value)};")
            case ir.ReturnValue(ir.RegexMatch(retty, target_string, bytecode, num_groups, named_group_mappings)):
                string_ty = self.generate_type(target_string.ty)
                cretty = self.generate_type(retty)
                self.code.append(f"{self.indent()}{string_ty} s = {self.generate_expression(target_string)};")
                self.code.append(f"{self.indent()}struct Capture captures[{num_groups}];")
                self.code.append(f"{self.indent()}const char bytecode[{len(bytecode)}] = {{{', '.join(str(b) for b in bytecode)}}};")
                #struct MatchResult _bc_match(const char* bytecode, size_t bytecode_len, const char* string, size_t string_len, size_t pc, size_t sp, struct Capture* captures, size_t captures_count);
                self.code.append(f"{self.indent()}struct MatchResult r = _bc_match(bytecode, {len(bytecode)}, (const char*)s.ch_String.ch_data.data, s.ch_String.ch_data.length, 0, 0, captures, {num_groups});")
                if retty == ir.BoolType():
                    self.code.append(f"{self.indent()}return r.matched;")
                else:
                    self.code.append(f"{self.indent()}{cretty} result;")
                    self.code.append(f"{self.indent()}if (!r.matched) {{ result.absent._has_value = 0; return result; }}")
                    self.code.append(f"{self.indent()}result.present._has_value = 1;")

                    lut = {num: name for (name, num) in named_group_mappings}
                    for i in range(num_groups):
                        n = lut.get(i, i)
                        self.code.append(f"{self.indent()}result.present._value.ch_{n}.ch_String.ch_data.length = captures[{i}].end - captures[{i}].begin;")
                        self.code.append(f"{self.indent()}result.present._value.ch_{n}.ch_String.ch_data.data = (void*)captures[{i}].begin;")
                    self.code.append(f"return result;")
            case ir.ReturnValue(value=value):
                self.code.append(f"{self.indent()}return {self.generate_expression(value)};")
            case ir.Return():
                self.code.append(f"{self.indent()}return;")
            case ir.Assert(value=value):
                self.code.append(f"{self.indent()}assert({self.generate_expression(value)});")
            case ir.InitInstance(ty, target, ctor, args):
                c_target = self.generate_expression(target)
                c_args = ", ".join([c_target] + [self.generate_expression(a) for a in args])
                self.code.append(f"{self.indent()}{self.ctor_name(ctor)}({c_args});")
            case ir.InitCInstance(ty, target, args):
                c_target = self.generate_expression(target)
                c_args = ", ".join([c_target] + [self.generate_expression(a) for a in args])
                match ty:
                    case ir.CStructDefinition():
                        self.code.append(f"{self.indent()}{self.ctor_name(ty)}({c_args});")
                    case _:
                        assert False, ty
            case ir.InitTuple(ty, target, positional, named, names):
                c_target = self.generate_expression(target)
                ty_name = self.generate_type(ty)
                c_pos = [self.generate_expression(e) for e in positional]
                name_dict = dict(zip(names, named))
                c_named = [self.generate_expression(name_dict[name]) for name in sorted(names)]

                args = ", ".join([c_target] + c_pos + c_named)
                self.code.append(f"{self.indent()}{ty_name}_ctor({args});")
            case ir.IfElse(cond, true_body, false_body):
                self.code.append(f"{self.indent()}if ({self.generate_expression(cond)}) {{")
                self.indent_level += 1
                for instr in true_body:
                    self.generate_instruction(instr)
                self.indent_level -= 1
                self.code.append(f"{self.indent()}}} else {{")
                self.indent_level += 1
                for instr in false_body:
                    self.generate_instruction(instr)
                self.indent_level -= 1
                self.code.append(f"{self.indent()}}}")
            case ir.Goto(label):
                self.code.append(f"{self.indent()}goto {label};")
            case ir.Label(name):
                self.code.append(f"{name}:;")
            case ir.Scope(body=body):
                self.code.append(f"{self.indent()}{{")
                self.indent_level += 1
                for instr in body:
                    self.generate_instruction(instr)
                self.indent_level -= 1
                self.code.append(f"{self.indent()}}}")
            case ir.IgnoreValue(value=value):
                self.code.append(f"{self.indent()}{self.generate_expression(value)};")
            case ir.CompileError(description=description):
                self.code.append(f'assert(0 && "Compile error: {description}");')
            case _:
                raise ValueError(f"Unknown instruction: {instruction}")

    def generate_expression(self, expr: ir.Instruction) -> str:
        match expr:
            case ir.LoadInteger(value=value):
                return str(value)
            case ir.LoadBool(value=value):
                return "((_ch_bool)%d)" % value
            case ir.LoadFloat(value=value):
                return str(value)
            case ir.LoadCString(value=value):
                return json.dumps(value) # TODO: Escape properly
            case ir.LoadString(value=value):
                return self.internalize_string(value)
            case ir.LoadSymbol(value=value):
                return str(self.internalize_symbol(value))
            case ir.LoadLocal(name=name):
                return name
            case ir.StoreLocalExpr(name=name, value=value):
                return f"({name} = {self.generate_expression(value)})"
            case ir.LoadGlobal(filename=filename, name=name):
                return f"ch_func_{name}_{abs(hash(filename))}"
            case ir.LoadCGlobal(var=var):
                return var.name
            case ir.AddressOf(_ty, expr):
                return f"(&{self.generate_expression(expr)})"
            case ir.DereferencePointer(_ty, expr):
                return f"(*{self.generate_expression(expr)})"
            case ir.BinaryOp(ty, lhs, op, rhs):
                l = self.generate_expression(lhs)
                r = self.generate_expression(rhs)
                if op == '==' and type(lhs.ty) == ir.ArrayType:
                    return f"array_equals({l}, {r}, sizeof({self.generate_type(lhs.ty.elty)}))"
                if op == '==' and type(lhs.ty) not in (ir.IntegerType, ir.BoolType, ir.FloatType, ir.PointerType):
                    return f"(memcmp(&{l}, &{r}, sizeof({self.generate_type(lhs.ty)})) == 0)"
                return f"({l} {op} {r})" 
            case ir.UnaryOp(ty, op, expr):
                x = self.generate_expression(expr)
                return f"({op}{x})" 
            case ir.Cast(value=value, ty=ty):
                return f"({self.generate_type(ty)})({self.generate_expression(value)})"
            case ir.ExprWithStmt(_ty, stmts, expr):
                for stmt in stmts:
                    self.generate_instruction(stmt)
                return self.generate_expression(expr)
            case ir.Null(ir.OptionType(ty)):
                ty_name = self.generate_type(expr.ty)
                # TODO: All bytes nust be set to zero.
                return "(%s){ 0 }" % (ty_name)
            case ir.OptionalIsEmpty(ty, expr):
                return f"({self.generate_expression(expr)}.present._has_value == 0)"
            case ir.OptionalGetValue(ty, expr):
                return f"{self.generate_expression(expr)}.present._value"
            case ir.MakeArray(ty, exprs):
                temp_name = "__temp_%d" % len(self.code)
                arrty_name = self.generate_type(ty)
                elty_name = self.generate_type(ty.elty)
                c_length = max(1, len(exprs)) # Empty array not allowed in C89
                real_length = len(exprs) # Empty array not allowed in C89
                self.function_decls.append(f"    {elty_name} {temp_name}_data[{c_length}];")
                self.function_decls.append(f"    {arrty_name} {temp_name};")
                self.code.append(f"{self.indent()}{temp_name}.length = {real_length};")
                self.code.append(f"{self.indent()}{temp_name}.data = &{temp_name}_data;")
                for idx, x in enumerate(exprs):
                    cexpr = self.generate_expression(x)
                    self.code.append(f"{self.indent()}{temp_name}_data[{idx}] = {cexpr};")

                return temp_name
            case ir.MakeArrayFromPointer(ty, length, pointer):
                temp_name = "__temp_%d" % len(self.code)
                arrty_name = self.generate_type(ty)
                elty_name = self.generate_type(ty.elty)
                self.function_decls.append(f"    {arrty_name} {temp_name};")
                c_pointer = self.generate_expression(pointer)
                self.code.append(f"{self.indent()}{temp_name}.length = {length};")
                self.code.append(f"{self.indent()}{temp_name}.data = {c_pointer};")
                return temp_name
            case ir.MakeUnion(ty, expr):
                c_expr = self.generate_expression(expr)
                ty_name = self.generate_type(ty)
                tag = ty.types.index(expr.ty)
                return "(%s){ %s, { ._%s=%s }}" % (ty_name, tag, tag, c_expr)
            case ir.MakeOptional(ty, expr):
                c_expr = self.generate_expression(expr)
                ty_name = self.generate_type(ty)
                return "(%s){ .present={._has_value=1, ._value=%s} }" % (ty_name, c_expr)
            case ir.LoadTupleIndex(_ty, target, index):
                return f"({self.generate_expression(target)}).ch_{index}"
            case ir.LoadArrayIndex(_ty, target, index):
                fnname = self.generate_get_index_function(target.ty)
                return f"*{fnname}({self.generate_expression(target)}, {self.generate_expression(index)})"
            case ir.LoadSubMember(ty, target, member, ctor):
                return f"({self.generate_expression(target)}).ch_{ctor.name}.ch_{member}"
            case ir.LoadMember(ty, target, 'length') if type(target.ty) == ir.ArrayType:
                return f"({self.generate_expression(target)}).length"
            case ir.LoadMember(ty, target, member):
                match target.ty:
                    case ir.TypeDefinition():
                        # If we get here, we know it's a member of a type with just one constructor.
                        if member != '__index__':
                            assert len(target.ty.constructors) == 1, target.ty
                        return f"({self.generate_expression(target)}).ch_{target.ty.constructors[0].name}.ch_{member}"
                    case ir.TupleType():
                        return f"({self.generate_expression(target)}).ch_{member}"
                    case ir.CStructDefinition():
                        return f"({self.generate_expression(target)}).{member}"
                    case _:
                        assert False, target.ty
            case ir.LoadTagValue(ty, target):
                ctyname = self.generate_type(target.ty)
                index_offset = f"offsetof({ctyname}, ch_{target.ty.constructors[0].name}.ch___index__)"
                taglut = self.generate_tag_lut(target.ty)
                return f"type_tag(&{self.generate_expression(target)}, {taglut}, {index_offset})"
            case ir.LoadCommonMember(ty, target, member):
                ctyname = self.generate_type(target.ty)
                index_offset = f"offsetof({ctyname}, ch_{target.ty.constructors[0].name}.ch___index__)"
                return f"*({self.generate_type(ty)}*)member_ptr(&{self.generate_expression(target)}, {self.generate_common_member_lut(target.ty, member)}, {index_offset})"
            case ir.CastExpr(ty, src):
                return f"(({self.generate_type(ty)}){self.generate_expression(src)})"
            case ir.MakePointerFromArray(ty, target):
                return f"({self.generate_type(ty)})({self.generate_expression(target)}.data)"
            case ir.CallFunction(ty, fn, args):
                args = ", ".join(self.generate_expression(a) for a in args)
                return f"{self.func_name(fn)}({args})"
            case ir.CallFunctionPointer(ty, fn, args):
                args = ", ".join(self.generate_expression(a) for a in args)
                return f"{self.generate_expression(fn)}({args})"
            case ir.CallCFunction(ty, fn, args):
                self.includes.add(f'#include "{fn.filename}"')
                args = ", ".join(self.generate_expression(a) for a in args)
                return f"{fn.name}({args})"
            case ir.ArrayAppend(ty, array, value):
                temp_name = "__temp_%d" % len(self.code)
                self.function_decls.append(f"{self.indent()}{self.generate_type(value.ty)} {temp_name};")
                self.code.append(f"{self.indent()}{temp_name} = {self.generate_expression(value)};")
                return f"array_append(&{self.generate_expression(array)}, sizeof({self.generate_type(value.ty)}), &{temp_name})"
            case ir.ArrayPop(ty , array):
                elty = self.generate_type(ty)
                return f"(*({elty}*)array_pop(&{self.generate_expression(array)}, sizeof({elty})))"
            case _:
                raise ValueError(f"Unknown expression: {expr}")


def generate(ir_modules, machine_def):
    gen = FuncCodeGen(machine_def, ir_modules)
    for module in ir_modules.values():
        for d in module.functions:
            if type(d) == ir.FunctionDefinition:
                gen.declare_function(d)
    for module in ir_modules.values():
        for d in module.functions:
            if type(d) == ir.FunctionDefinition:
                gen.generate(d)
    return gen.get_code()