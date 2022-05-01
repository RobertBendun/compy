from dataclasses import dataclass, field
import argparse
import ast
import shlex
import subprocess
import sys
import textwrap
import os.path

silent_mode = False
compy_location = os.path.dirname(__file__)

def run_command(cmd, **kwargs):
    if not silent_mode:
        print("[CMD] %s" % " ".join(map(shlex.quote, cmd)), flush=True)
    return subprocess.run(cmd, **kwargs)

@dataclass
class Code_Generator:
    # Bodies of functions by their name
    bodies : dict[str, str] = field(default_factory=dict)

    # Function definition stack
    names : list[str] = field(default_factory=list)

    # Function arguments by their name
    args : dict[str, list[str]] = field(default_factory=dict)

    # Return type of function by their name
    return_types : dict[str, str] = field(default_factory=dict)

    def add_statement(self, statement: str):
        name = self.names[-1]
        if name not in self.bodies:
            self.bodies[name] = ""
        self.bodies[name] += f"  {statement};\n"

    def enter_function(self, name : str):
        self.names.append(name)

    def leave_function(self):
        self.names.pop()

    def in_function(self, name: str):
        class Function_Context:
            def __enter__(*_):
                self.names.append(name)

            def __exit__(*_):
                assert self.names.pop() == name

        return Function_Context()

    def save(self, filename : str):
        with open(filename, 'w') as f:
            f.write("#include <std.hh>\n")
            for name, body in self.bodies.items():
                if name in self.return_types:
                    return_type = self.return_types[name]
                else:
                    return_type = "void" if name == "compy_main" else "auto"

                if name in self.args:
                    args = ', '.join("auto " + arg for arg in self.args[name])
                else:
                    args = ""

                f.write("\n%s %s(%s)\n{\n%s}\n" % (return_type, name, args, body))


codegen = Code_Generator()

def cpp_str(s: str) -> str:
    return '"%s"_str' % (s,)

def cpp_int(i: int) -> str:
    return "%d" % (i,)

class Visitor(ast.NodeVisitor):
    def generic_visit(self, node: ast.AST):
        classname = node.__class__.__name__
        print(f"Unsuported AST node. Implement relevant visit_{classname}() method", file=sys.stderr)
        print(ast.dump(node, indent=2), file=sys.stderr, flush=True)
        exit(1)

    def add_statement(self, stmt):
        if stmt is not None:
            codegen.add_statement(stmt)

    def block(self, statements):
        for statement in statements:
            self.add_statement(self.visit(statement))


    def visit_Module(self, module: ast.Module):
        codegen.enter_function('compy_main')
        with codegen.in_function("compy_main"):
            self.block(module.body)

    def visit_FunctionDef(self, fun: ast.FunctionDef):
        assert not fun.decorator_list,   "Decorators are not supported yet"
        assert not fun.args.posonlyargs, "Arguments are not supported yet"
        assert not fun.args.kwonlyargs,  "Arguments are not supported yet"
        assert not fun.args.kw_defaults, "Arguments are not supported yet"
        assert not fun.args.defaults,    "Arguments are not supported yet"

        if fun.returns:
            assert isinstance(fun.returns, ast.Name), "Only type names are supported now"
            codegen.return_types[fun.name] = fun.returns.id

        codegen.args[fun.name] = [a.arg for a in fun.args.args]
        with codegen.in_function(fun.name):
            for statement in fun.body:
                self.add_statement(self.visit(statement))

    def visit_Assign(self, assign: ast.Assign):
        assert len(assign.targets) == 1, "Multiple targets are not supported yet"

        return "%s = %s" % (
            self.visit(assign.targets[0]),
            self.visit(assign.value))

    def visit_AnnAssign(self, assign: ast.AnnAssign):
        return "%s %s = %s" % (
                assign.annotation.id,
                assign.target.id,
                self.visit(assign.value)
        )

    def visit_AugAssign(self, assign: ast.AugAssign):
        if   isinstance(assign.op, ast.Add):  op ="+"
        elif isinstance(assign.op, ast.Mult): op = "*"
        else:
            assert False, "Unsuported operation: " + ast.dump(assign.op)

        return "%s %s= %s" % (self.visit(assign.target), op, self.visit(assign.value))

    def visit_While(self, w: ast.While):
        self.add_statement("while (%s) {" % (self.visit(w.test), ))
        self.block(w.body)
        self.add_statement("}")

    def visit_For(self, f: ast.For):
        self.add_statement("for (auto %s : %s) {" % (self.visit(f.target), self.visit(f.iter),))
        self.block(f.body)
        self.add_statement("}")

    def visit_Return(self, ret: ast.Return):
        return "return " + self.visit(ret.value)

    def visit_Expr(self, expr: ast.Expr):
        return self.visit(expr.value)

    def visit_Subscript(self, expr: ast.Subscript):
        return "%s[%s]" % (self.visit(expr.value), self.visit(expr.slice))

    def visit_IfExp(self, expr: ast.IfExp):
        return "(%s) ? (%s) : (%s)" % tuple(self.visit(x) for x in (expr.test, expr.body, expr.orelse))

    def visit_Compare(self, expr: ast.Compare):
        assert len(expr.comparators) == 1, "Only one comparator is supported now"
        assert len(expr.ops) == 1, "Only one operation is supported now"
        lhs, op, rhs = expr.left, expr.ops[0], expr.comparators[0]

        if isinstance(op, ast.Lt):    o = "<"
        elif isinstance(op, ast.LtE): o = "<="
        else: assert False, "unknown comparison operator: " + ast.dump(op, indent=2)

        return "(%s) %s (%s)" % (self.visit(lhs), o, self.visit(rhs))

    def visit_BinOp(self, expr: ast.BinOp):
        lhs, op, rhs = expr.left, expr.op, expr.right

        # TODO Resolve precedense. A good idea is to implement precedense
        # visitor that based on current op will calculate if operators in
        # subtree have higher precedense
        if   isinstance(op, ast.Add):  o = "+"
        elif isinstance(op, ast.Sub):  o = "-"
        elif isinstance(op, ast.Mult): o = "*"
        else: assert False, "unknown operator: " + ast.dump(op, indent=2)

        return "(%s) %s (%s)" % (self.visit(lhs), o, self.visit(rhs))

    def visit_Call(self, call: ast.Call) -> str:
        func = self.visit(call.func)
        args = [self.visit(arg) for arg in call.args]

        if call.keywords:
            kw = "python::Keyword_Arguments{}"
            for keyword in call.keywords:
                kw += '.append("%s", %s)' % (keyword.arg, self.visit(keyword.value))
            args.insert(0, kw)

        return "%s(%s)" % (func, ', '.join(args))

    def visit_Name(self, name: ast.Name) -> str:
        return name.id

    def visit_Attribute(self, attr: ast.Attribute) -> str:
        return "(%s).%s" % (self.visit(attr.value), attr.attr)

    def visit_List(self, l: ast.List):
        return "list::init(%s)" % (', '.join(self.visit(element) for element in l.elts),)

    def visit_Constant(self, const: ast.Constant) -> str:
        val = const.value
        if val is None:           return "::python::None"
        if isinstance(val, bool): return "true" if val else "false"
        if isinstance(val, str):  return cpp_str(const.value)
        if isinstance(val, int):  return cpp_int(val)
        assert False, "constant not implemented yet: " + type(val)

def compile_program(source: str, filename: str):
    tree = ast.parse(source, filename, type_comments=True)
    Visitor().visit(tree)

def compiler_main(args: argparse.Namespace):
    source_file = args.source[0]
    try:
        with open(source_file) as f:
            source_code = f.read()
    except FileNotFoundError as e:
        print("compy: error: Source file '%s' has not been found" % (e.filename,), file=sys.stderr)
        os._exit(1)

    compile_program(source_code, source_file)

    codegen.save(f"{source_file}.cc")
    run_command(["g++", "-std=c++20", "-Wall", "-Wextra", f"{source_file}.cc", "-o", f"{source_file}.out", f"-I{compy_location}"])

    compiler_result = run_command([f"./{source_file}.out"], capture_output=args.test)

    if args.test:
        interpreter_result = run_command(["python", f"./{source_file}"], capture_output=True)

        if compiler_result.stdout != interpreter_result.stdout:
            print("=== FAILED: Different standard output =====")
            print("=== COMPILER ==============================")
            print(compiler_result.stdout)
            print("=== INTERPRETER ===========================")
            print(interpreter_result.stdout)
            print()

        if compiler_result.stderr != interpreter_result.stderr:
            print("=== FAILED: Different standard error output")
            print("=== COMPILER ==============================")
            print(compiler_result.stderr)
            print("=== INTERPRETER ===========================")
            print(interpreter_result.stderr)
            print()

        print("=== SUCCESS ===================================")

def main():
    global silent_mode

    p = argparse.ArgumentParser(prog='compy', description="Python to C++ compiler")
    p.add_argument("source", nargs=1, type=str, help="Python file to compile")
    p.add_argument("--test", action="store_true")
    p.add_argument("--silent", action="store_true")

    args = p.parse_args()
    silent_mode = args.test or args.silent

    compiler_main(args)


if __name__ == '__main__':
    main()
