#!/usr/bin/env python3
import json
import subprocess
import sys
import os

# Add the python directory to the start of sys.path to avoid conflict with built-in 'parser'
python_dir = os.path.join(os.path.dirname(__file__), "python")
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)
from parser import parse_file, ParseError

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 check_proof.py <file.proof>")
        sys.exit(1)

    proof_file = sys.argv[1]
    cpp_prover_bin = os.path.join(os.path.dirname(__file__), "cpp", "build", "prover")

    if not os.path.exists(cpp_prover_bin):
        print(f"Error: C++ prover binary not found at {cpp_prover_bin}")
        print("Please build it first: cd cpp && mkdir build && cd build && cmake .. && make")
        sys.exit(1)

    try:
        # 1. Parse the proof file to JSON
        ast = parse_file(proof_file)
        
        # 2. Run the C++ prover and pipe the AST to it
        process = subprocess.Popen(
            [cpp_prover_bin],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=json.dumps(ast))
        
        if process.returncode != 0 and not stdout:
            print(f"C++ Prover error (exit code {process.returncode}):")
            print(stderr)
            sys.exit(1)

        # 3. Parse and display the result
        result = json.loads(stdout)
        
        print(f"File: {proof_file}")
        print("-" * 40)
        
        # Display step results if present
        step_results = result.get("step_results", [])
        if step_results:
            print("Proof Steps:")
            for step in step_results:
                step_num = step.get("step", "?")
                if step.get("ok"):
                    print(f"  Step {step_num}: ✓ Proven")
                else:
                    step_status = step.get("status", "error")
                    if step_status == "disproven":
                        print(f"  Step {step_num}: ✗ Disproven")
                    elif step_status == "unknown":
                        print(f"  Step {step_num}: ? Unknown")
                    else:
                        print(f"  Step {step_num}: ✗ Error: {step.get('error', 'Unknown')}")
            print()
        
        if result.get("ok"):
            print("STATUS: PROVEN")
            print("The claim follows logically from the assumptions.")
        else:
            status = result.get("status", "error")
            if status == "disproven":
                print("STATUS: DISPROVEN")
                print("A counterexample was found:")
                model = result.get("model", {})
                for var, val in model.items():
                    print(f"  {var} = {val}")
            elif status == "unknown":
                print("STATUS: UNKNOWN")
                print("Z3 could not determine satisfiability.")
                if "message" in result:
                    print(f"Message: {result['message']}")
            else:
                print("STATUS: ERROR")
                print(f"Error: {result.get('error', 'Unknown error')}")

    except ParseError as e:
        print(f"Parse Error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: File '{proof_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
