"""
Proof Checker - Extended Prover
Supports logical connectives, quantifiers, and rich arithmetic.
"""

import json
import sys
from z3 import (
    Real, RealVal, Int, IntVal, If, Solver, Not, And, Or, Implies, ForAll, Exists,
    sat, unsat, unknown
)


class ProofError(Exception):
    """Base exception for proof errors."""
    pass


class TermError(ProofError):
    """Error in term parsing."""
    pass


class FormulaError(ProofError):
    """Error in formula parsing."""
    pass


def term_to_z3(t, env, var_types=None):
    """Convert a term JSON object to a Z3 expression.
    
    Supported term types:
    - num: numeric literal
    - var: variable reference
    - bin: binary operation (+, -, *, /)
    - abs: absolute value
    - neg: unary negation
    - pow: exponentiation
    - sqrt: square root
    - min: minimum of arguments
    - max: maximum of arguments
    
    Args:
        t: Term JSON object
        env: Variable environment mapping names to Z3 expressions
        var_types: Optional dict mapping variable names to types ('Int' or 'Real')
    """
    if var_types is None:
        var_types = {}
        
    if not isinstance(t, dict):
        raise TermError(f"Term must be an object, got: {type(t).__name__}")
    
    ty = t.get("type")
    if ty is None:
        raise TermError(f"Term missing 'type' field: {t}")

    if ty == "num":
        value = t.get("value")
        if value is None:
            raise TermError("Numeric term missing 'value' field")
        return RealVal(value)

    if ty == "var":
        name = t.get("name")
        if name is None:
            raise TermError("Variable term missing 'name' field")
        if name not in env:
            # Create Int or Real based on var_types
            if var_types.get(name) == 'Int':
                env[name] = Int(name)
            else:
                env[name] = Real(name)
        return env[name]

    if ty == "bin":
        op = t.get("op")
        if op is None:
            raise TermError("Binary term missing 'op' field")
        if "lhs" not in t or "rhs" not in t:
            raise TermError("Binary term missing 'lhs' or 'rhs' field")
        
        a = term_to_z3(t["lhs"], env, var_types)
        b = term_to_z3(t["rhs"], env, var_types)
        
        if op == "+": return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/": return a / b
        raise TermError(f"Unknown binary operator: {op}")

    if ty == "abs":
        if "arg" not in t:
            raise TermError("Abs term missing 'arg' field")
        x = term_to_z3(t["arg"], env, var_types)
        return If(x >= 0, x, -x)

    if ty == "neg":
        if "arg" not in t:
            raise TermError("Neg term missing 'arg' field")
        x = term_to_z3(t["arg"], env, var_types)
        return -x

    if ty == "pow":
        if "base" not in t or "exp" not in t:
            raise TermError("Pow term missing 'base' or 'exp' field")
        base = term_to_z3(t["base"], env, var_types)
        exp = term_to_z3(t["exp"], env, var_types)
        return base ** exp

    if ty == "sqrt":
        if "arg" not in t:
            raise TermError("Sqrt term missing 'arg' field")
        x = term_to_z3(t["arg"], env, var_types)
        # sqrt(x) represented as x^0.5
        return x ** RealVal("0.5")

    if ty == "min":
        args = t.get("args", [])
        if len(args) < 2:
            raise TermError("Min requires at least 2 arguments")
        result = term_to_z3(args[0], env, var_types)
        for arg in args[1:]:
            other = term_to_z3(arg, env, var_types)
            result = If(result <= other, result, other)
        return result

    if ty == "max":
        args = t.get("args", [])
        if len(args) < 2:
            raise TermError("Max requires at least 2 arguments")
        result = term_to_z3(args[0], env, var_types)
        for arg in args[1:]:
            other = term_to_z3(arg, env, var_types)
            result = If(result >= other, result, other)
        return result

    raise TermError(f"Unknown term type: {ty}")


def formula_to_z3(f, env, var_types=None):
    """Convert a formula JSON object to a Z3 expression.
    
    Supported formula types:
    - rel: relational comparison (<, <=, =, !=, >, >=)
    - and: conjunction of formulas
    - or: disjunction of formulas
    - not: negation of a formula
    - implies: implication (lhs => rhs)
    - forall: universal quantifier
    - exists: existential quantifier
    """
    if var_types is None:
        var_types = {}
        
    if not isinstance(f, dict):
        raise FormulaError(f"Formula must be an object, got: {type(f).__name__}")
    
    ty = f.get("type")
    if ty is None:
        raise FormulaError(f"Formula missing 'type' field: {f}")

    if ty == "rel":
        op = f.get("op")
        if op is None:
            raise FormulaError("Relational formula missing 'op' field")
        if "lhs" not in f or "rhs" not in f:
            raise FormulaError("Relational formula missing 'lhs' or 'rhs' field")
        
        lhs = term_to_z3(f["lhs"], env, var_types)
        rhs = term_to_z3(f["rhs"], env, var_types)

        if op == "<":  return lhs < rhs
        if op == "<=": return lhs <= rhs
        if op == "=":  return lhs == rhs
        if op == "!=": return lhs != rhs
        if op == ">":  return lhs > rhs
        if op == ">=": return lhs >= rhs
        raise FormulaError(f"Unknown relational operator: {op}")

    if ty == "and":
        args = f.get("args", [])
        if len(args) == 0:
            return True  # Empty conjunction is true
        z3_args = [formula_to_z3(arg, env, var_types) for arg in args]
        return And(*z3_args)

    if ty == "or":
        args = f.get("args", [])
        if len(args) == 0:
            return False  # Empty disjunction is false
        z3_args = [formula_to_z3(arg, env, var_types) for arg in args]
        return Or(*z3_args)

    if ty == "not":
        if "arg" not in f:
            raise FormulaError("Not formula missing 'arg' field")
        inner = formula_to_z3(f["arg"], env, var_types)
        return Not(inner)

    if ty == "implies":
        if "lhs" not in f or "rhs" not in f:
            raise FormulaError("Implies formula missing 'lhs' or 'rhs' field")
        lhs = formula_to_z3(f["lhs"], env, var_types)
        rhs = formula_to_z3(f["rhs"], env, var_types)
        return Implies(lhs, rhs)

    if ty == "forall":
        var_names = f.get("vars", [])
        if not var_names:
            raise FormulaError("Forall formula missing 'vars' field")
        if "body" not in f:
            raise FormulaError("Forall formula missing 'body' field")
        
        # Create fresh variables for the quantifier
        quant_vars = []
        for name in var_names:
            if var_types.get(name) == 'Int':
                v = Int(name)
            else:
                v = Real(name)
            env[name] = v
            quant_vars.append(v)
        
        body = formula_to_z3(f["body"], env, var_types)
        return ForAll(quant_vars, body)

    if ty == "exists":
        var_names = f.get("vars", [])
        if not var_names:
            raise FormulaError("Exists formula missing 'vars' field")
        if "body" not in f:
            raise FormulaError("Exists formula missing 'body' field")
        
        # Create fresh variables for the quantifier
        quant_vars = []
        for name in var_names:
            if var_types.get(name) == 'Int':
                v = Int(name)
            else:
                v = Real(name)
            env[name] = v
            quant_vars.append(v)
        
        body = formula_to_z3(f["body"], env, var_types)
        return Exists(quant_vars, body)

    raise FormulaError(f"Unknown formula type: {ty}")


def format_counterexample(model, env):
    """Format a Z3 model as a human-readable counterexample."""
    lines = ["Counterexample found:"]
    for name, var in sorted(env.items()):
        value = model.eval(var, model_completion=True)
        lines.append(f"  {name} = {value}")
    return "\n".join(lines)


def prove(assumptions, claim, declared_vars=None, var_types=None, steps=None):
    """Attempt to prove that assumptions imply the claim.
    
    Args:
        assumptions: List of assumption formulas
        claim: The claim to prove
        declared_vars: Optional list of declared variable names
        var_types: Optional dict mapping variable names to types ('Int' or 'Real')
        steps: Optional list of intermediate proof steps to verify
    
    Returns a dict with:
    - ok: True if proven, False if counterexample found
    - model: counterexample variable assignments (if ok=False)
    - error: error message (if parsing failed)
    - status: "proven", "disproven", "unknown", or "error"
    - step_results: results for each intermediate step (if steps provided)
    """
    try:
        if var_types is None:
            var_types = {}
        if steps is None:
            steps = []
            
        env = {}
        if declared_vars:
            for name in declared_vars:
                if var_types.get(name) == 'Int':
                    env[name] = Int(name)
                else:
                    env[name] = Real(name)

        # Verify intermediate steps first
        step_results = []
        current_assumptions = list(assumptions)
        
        for i, step in enumerate(steps):
            # Handle cases step type
            if step.get("type") == "cases":
                cases = step.get("cases", [])
                case_results = []
                all_cases_ok = True
                
                # Collect all case conditions for exhaustiveness check
                conditions = []
                
                for case_idx, case in enumerate(cases):
                    condition = case.get("condition")
                    conditions.append(condition)
                    case_steps = case.get("steps", [])
                    
                    # For each case, assume the condition and verify steps
                    case_assumptions = current_assumptions + [condition]
                    for cs in case_steps:
                        cs_formula = cs.get("formula")
                        if cs_formula:
                            # Check if this step is provable under the case assumption
                            s = Solver()
                            for a in case_assumptions:
                                s.add(formula_to_z3(a, env.copy(), var_types))
                            s.add(Not(formula_to_z3(cs_formula, env.copy(), var_types)))
                            if s.check() == unsat:
                                case_assumptions.append(cs_formula)
                    
                    case_results.append({"case": case_idx + 1, "ok": True})
                
                # Check if cases are exhaustive: disjunction of conditions should be tautology
                # (given current assumptions)
                if conditions:
                    s = Solver()
                    for a in current_assumptions:
                        s.add(formula_to_z3(a, env.copy(), var_types))
                    
                    # Negate (cond1 OR cond2 OR ...) 
                    cond_z3 = [formula_to_z3(c, env.copy(), var_types) for c in conditions]
                    s.add(Not(Or(*cond_z3)))
                    
                    exhaustive = s.check() == unsat
                    if not exhaustive:
                        all_cases_ok = False
                        step_results.append({
                            "step": i + 1,
                            "type": "cases",
                            "ok": False,
                            "status": "non-exhaustive",
                            "message": "Cases may not cover all possibilities"
                        })
                    else:
                        step_results.append({
                            "step": i + 1,
                            "type": "cases",
                            "ok": True,
                            "status": "proven",
                            "case_results": case_results
                        })
                continue
            
            step_formula = step.get("formula")
            if step_formula is None:
                step_results.append({"step": i + 1, "ok": False, "error": "Step missing formula"})
                continue
            
            s = Solver()
            for a in current_assumptions:
                s.add(formula_to_z3(a, env.copy(), var_types))
            
            step_z3 = formula_to_z3(step_formula, env.copy(), var_types)
            s.add(Not(step_z3))
            
            result = s.check()
            
            if result == unsat:
                step_results.append({"step": i + 1, "ok": True, "status": "proven"})
                # Add the proven step as an assumption for subsequent steps
                current_assumptions.append(step_formula)
            elif result == sat:
                m = s.model()
                model_out = {name: str(m.eval(v, model_completion=True)) for name, v in env.items()}
                step_results.append({
                    "step": i + 1, 
                    "ok": False, 
                    "status": "disproven",
                    "model": model_out
                })
                # Don't add unproven steps to assumptions
            else:
                step_results.append({"step": i + 1, "ok": False, "status": "unknown"})

        # Now prove the final claim
        s = Solver()
        
        # Add all original assumptions plus proven steps
        for a in current_assumptions:
            s.add(formula_to_z3(a, env, var_types))

        # Convert the claim
        claim_z3 = formula_to_z3(claim, env, var_types)

        # Prove: assumptions => claim
        # Check UNSAT of: assumptions AND (NOT claim)
        s.add(Not(claim_z3))

        result = s.check()
        
        if result == unsat:
            response = {"ok": True, "status": "proven"}
            if step_results:
                response["step_results"] = step_results
            return response
        
        if result == sat:
            m = s.model()
            model_out = {
                name: str(m.eval(v, model_completion=True)) 
                for name, v in env.items()
            }
            response = {
                "ok": False, 
                "status": "disproven",
                "model": model_out,
                "message": format_counterexample(m, env)
            }
            if step_results:
                response["step_results"] = step_results
            return response
        
        # result == unknown
        response = {
            "ok": False,
            "status": "unknown",
            "message": "Z3 could not determine satisfiability (timeout or incomplete theory)"
        }
        if step_results:
            response["step_results"] = step_results
        return response

    except (TermError, FormulaError) as e:
        return {
            "ok": False,
            "status": "error",
            "error": str(e)
        }
    except Exception as e:
        return {
            "ok": False,
            "status": "error",
            "error": f"Internal error: {e}"
        }


def main():
    """Main entry point - reads JSON from stdin, outputs JSON to stdout."""
    try:
        req = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        json.dump({"ok": False, "status": "error", "error": f"Invalid JSON: {e}"}, sys.stdout)
        return

    declared_vars = req.get("vars", [])
    var_types = req.get("var_types", {})
    assumptions = req.get("assumptions", [])
    steps = req.get("steps", [])
    claim = req.get("claim")
    
    if claim is None:
        json.dump({"ok": False, "status": "error", "error": "Missing 'claim' field"}, sys.stdout)
        return

    result = prove(assumptions, claim, declared_vars, var_types, steps)
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()

