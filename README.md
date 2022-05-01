# Python to C++ transpiler

Project intended for exploration of Python's `ast` module.

## How it works?

- Visit all Python AST nodes, as defined by `ast` module.
	- Each node is compiled to appropiate C++ code.
- It get's combined with [`std.hh`](./std.hh), which tries to reflect Pythons semantics.
- Compiled with gcc and run!
