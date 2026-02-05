#!/usr/bin/env python3
import sys
import os
import json

# Add the python directory to the start of sys.path
python_dir = os.path.join(os.path.dirname(__file__), "python")
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)

from parser import parse, ParseError

def main():
    print("Proof Checker Parser REPL")
    print("Type a DSL statement (e.g., 'let x = 5', 'assume x > 0') or 'exit' to quit.")
    print("-" * 50)

    while True:
        try:
            line = input("parser> ").strip()
            if not line:
                continue
            if line.lower() in ("exit", "quit"):
                break
            
            # The parser expects a full proof structure (list of statements)
            # We can try to parse the single line as a snippet
            ast = parse(line)
            print(json.dumps(ast, indent=2))
            
        except ParseError as e:
            print(f"Parse Error: {e}")
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
