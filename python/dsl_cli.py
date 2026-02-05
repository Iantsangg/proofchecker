#!/usr/bin/env python3
"""
Proof Checker - Command Line Interface

Usage:
    python dsl_cli.py <file.proof>       Verify a proof file
    python dsl_cli.py --repl             Interactive REPL mode
    python dsl_cli.py --json <file>      Parse and output JSON AST
"""

import sys
import argparse
import json
import readline  # For REPL history/editing

from parser import parse, parse_file, ParseError
from prover import prove, ProofError


def colorize(text: str, color: str) -> str:
    """Add ANSI color to text."""
    colors = {
        'green': '\033[92m',
        'red': '\033[91m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def print_result(result: dict, verbose: bool = True):
    """Pretty-print a proof result."""
    if result["ok"]:
        print(colorize("✓ Proof successful!", "green"))
    else:
        status = result.get("status", "unknown")
        if status == "disproven":
            print(colorize("✗ Proof failed - counterexample found:", "red"))
            if "model" in result:
                for var, val in result["model"].items():
                    print(f"    {var} = {val}")
        elif status == "unknown":
            print(colorize("? Proof inconclusive", "yellow"))
            if "message" in result:
                print(f"    {result['message']}")
        elif status == "error":
            print(colorize(f"Error: {result.get('error', 'Unknown error')}", "red"))
        else:
            print(colorize(f"Unexpected status: {status}", "yellow"))


def verify_file(filename: str, verbose: bool = True, json_output: bool = False):
    """Verify a proof file."""
    try:
        ast = parse_file(filename)
        
        if json_output:
            print(json.dumps(ast, indent=2))
            return True
        
        if verbose:
            print(colorize(f"Verifying: {filename}", "blue"))
            print(f"  Variables: {', '.join(ast['vars']) or '(none)'}")
            print(f"  Assumptions: {len(ast['assumptions'])}")
            print()
        
        result = prove(
            ast["assumptions"],
            ast["claim"],
            ast["vars"]
        )
        
        print_result(result, verbose)
        return result["ok"]
        
    except ParseError as e:
        print(colorize(f"Parse error: {e}", "red"))
        return False
    except FileNotFoundError:
        print(colorize(f"File not found: {filename}", "red"))
        return False
    except Exception as e:
        print(colorize(f"Error: {e}", "red"))
        return False


def repl():
    """Interactive REPL for proving statements."""
    print(colorize("Proof Checker REPL", "bold"))
    print("Enter proof statements. Type 'help' for commands, 'quit' to exit.")
    print()
    
    assumptions = []
    variables = set()
    
    def show_help():
        print("""
Commands:
    assume <formula>     Add an assumption
    prove <formula>      Prove a claim from current assumptions
    clear                Clear all assumptions
    list                 Show current assumptions
    help                 Show this help
    quit, exit           Exit the REPL

Examples:
    assume x > 0
    assume y > 0
    prove x + y > 0
        """)
    
    while True:
        try:
            line = input(colorize("proof> ", "blue")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if not line:
            continue
        
        if line in ('quit', 'exit'):
            print("Goodbye!")
            break
        
        if line == 'help':
            show_help()
            continue
        
        if line == 'clear':
            assumptions.clear()
            variables.clear()
            print("Assumptions cleared.")
            continue
        
        if line == 'list':
            if assumptions:
                print("Current assumptions:")
                for i, a in enumerate(assumptions, 1):
                    print(f"  {i}. {json.dumps(a)}")
            else:
                print("No assumptions.")
            continue
        
        # Parse as a statement
        try:
            ast = parse(line)
            
            # Collect new variables
            for v in ast.get("vars", []):
                variables.add(v)
            
            # Handle assumptions
            for a in ast.get("assumptions", []):
                assumptions.append(a)
                print(colorize("  Assumption added.", "blue"))
            
            # Handle proof
            if ast.get("claim"):
                result = prove(assumptions, ast["claim"], list(variables))
                print_result(result)
        
        except ParseError as e:
            print(colorize(f"Parse error: {e}", "red"))
        except Exception as e:
            print(colorize(f"Error: {e}", "red"))


def main():
    parser = argparse.ArgumentParser(
        description="Proof Checker CLI - Verify mathematical proofs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python dsl_cli.py proof.txt           Verify a proof file
    python dsl_cli.py --repl              Start interactive mode
    python dsl_cli.py --json proof.txt    Output JSON AST
        """
    )
    
    parser.add_argument('file', nargs='?', help='Proof file to verify')
    parser.add_argument('--repl', action='store_true', help='Start interactive REPL')
    parser.add_argument('--json', action='store_true', help='Output JSON AST instead of verifying')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode (less output)')
    
    args = parser.parse_args()
    
    if args.repl:
        repl()
    elif args.file:
        success = verify_file(args.file, verbose=not args.quiet, json_output=args.json)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
