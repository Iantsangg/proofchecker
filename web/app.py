#!/usr/bin/env python3
"""
Web Playground API for Proof Checker
Simple Flask server that provides proof checking via REST API.
"""

import os
import sys

# Add the python directory to path for parser/prover imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(project_root, "python")
if python_dir not in sys.path:
    sys.path.insert(0, python_dir)

from flask import Flask, request, jsonify, send_from_directory
from parser import Lexer, Parser, ParseError
from prover import prove

app = Flask(__name__, static_folder='.')


@app.route('/')
def index():
    """Serve the main playground HTML page."""
    return send_from_directory('.', 'index.html')


@app.route('/api/check', methods=['POST'])
def check_proof():
    """
    Check a proof and return the result.
    
    Request body: { "code": "assume x > 0\nprove x > 0" }
    
    Response: {
        "ok": true/false,
        "status": "proven" | "disproven" | "unknown" | "error",
        "message": "...",
        "model": { "x": "1.5" },  // if disproven
        "step_results": [...]  // intermediate step results
    }
    """
    try:
        data = request.get_json()
        if not data or 'code' not in data:
            return jsonify({
                'ok': False,
                'status': 'error',
                'message': 'Missing "code" in request body'
            }), 400
        
        code = data['code']
        
        # Parse the proof code
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, base_path=os.path.join(project_root, 'examples'))
        ast = parser.parse()
        
        # Check for parse errors
        if ast.get('errors'):
            return jsonify({
                'ok': False,
                'status': 'error',
                'message': 'Parse errors:\n' + '\n'.join(ast['errors'])
            })
        
        # Extract proof components from AST
        assumptions = ast.get('assumptions', [])
        claim = ast.get('claim')
        declared_vars = ast.get('declared_vars', [])
        var_types = ast.get('var_types', {})
        steps = ast.get('steps', [])
        
        if not claim:
            return jsonify({
                'ok': False,
                'status': 'error',
                'message': 'No claim (prove statement) found in the proof'
            })
        
        # Run the prover
        result = prove(
            assumptions=assumptions,
            claim=claim,
            declared_vars=declared_vars,
            var_types=var_types,
            steps=steps
        )
        
        # Format the response
        response = {
            'ok': result.get('ok', False),
            'status': result.get('status', 'unknown'),
        }
        
        if result.get('ok'):
            response['message'] = 'The claim follows logically from the assumptions.'
        elif result.get('status') == 'disproven':
            response['message'] = 'A counterexample was found.'
            response['model'] = result.get('model', {})
        elif result.get('status') == 'unknown':
            response['message'] = result.get('message', 'Z3 could not determine satisfiability.')
        else:
            response['message'] = result.get('error', 'Unknown error')
        
        if result.get('step_results'):
            response['step_results'] = result['step_results']
        
        return jsonify(response)
    
    except ParseError as e:
        return jsonify({
            'ok': False,
            'status': 'error',
            'message': f'Parse error: {str(e)}'
        })
    except Exception as e:
        return jsonify({
            'ok': False,
            'status': 'error',
            'message': f'Internal error: {str(e)}'
        }), 500


@app.route('/api/examples', methods=['GET'])
def get_examples():
    """Return a list of example proofs."""
    examples = [
        {
            'name': 'Basic Proof',
            'code': '''# A simple proof that x + y > 0 if both are positive
assume x > 0
assume y > 0
prove x + y > 0'''
        },
        {
            'name': 'Inequality Chaining',
            'code': '''# Chained comparisons work naturally
assume 0 < a <= b < c
prove a < c'''
        },
        {
            'name': 'Proof by Cases',
            'code': '''# Prove x² > 0 for nonzero x using case analysis
assume x != 0

cases:
    case x > 0:
        have x * x > 0
    case x < 0:
        have x * x > 0

prove x * x > 0'''
        },
        {
            'name': 'Integer Types',
            'code': '''# Integer reasoning
let n: Int
assume n > 0
prove n >= 1'''
        },
        {
            'name': 'Absolute Value',
            'code': '''# Absolute value is non-negative
prove abs(x) >= 0'''
        },
        {
            'name': 'Disproven Example',
            'code': '''# This will be disproven with a counterexample
assume x > 0
prove x > 10'''
        },
        {
            'name': 'AM-GM Inequality',
            'code': '''# Arithmetic mean >= Geometric mean
assume a >= 0
assume b >= 0
prove (a + b) / 2 >= sqrt(a * b)'''
        }
    ]
    return jsonify(examples)


if __name__ == '__main__':
    print("🧮 Proof Checker Playground")
    print("   Open http://localhost:5050 in your browser")
    print()
    app.run(host='0.0.0.0', port=5050, debug=True)
