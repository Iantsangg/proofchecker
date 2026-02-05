import pytest
from prover import prove

# Helper to create basic term/formula structures
def var(name):
    return {"type": "var", "name": name}

def num(val):
    return {"type": "num", "value": val}

def binary(op, lhs, rhs):
    return {"type": "bin", "op": op, "lhs": lhs, "rhs": rhs}

def rel(op, lhs, rhs):
    return {"type": "rel", "op": op, "lhs": lhs, "rhs": rhs}

def logical_not(arg):
    return {"type": "not", "arg": arg}

class TestProver:
    def test_simple_arithmetic(self):
        # Prove: x > 0 => x + 1 > 1
        assumptions = [rel(">", var("x"), num(0))]
        claim = rel(">", binary("+", var("x"), num(1)), num(1))
        
        result = prove(assumptions, claim, ["x"])
        assert result["ok"] is True
        assert result["status"] == "proven"

    def test_arithmetic_counterexample(self):
        # Disprove: x > 0 => x > 5
        assumptions = [rel(">", var("x"), num(0))]
        claim = rel(">", var("x"), num(5))
        
        result = prove(assumptions, claim, ["x"])
        assert result["ok"] is False
        assert result["status"] == "disproven"
        assert "model" in result
        # Check that the counterexample is valid (x <= 5 and x > 0)
        # Note: Model values are strings, need strict checking depending on Z3 output
        
    def test_absolute_value(self):
        # Prove: |x| >= 0
        claim = rel(">=", {"type": "abs", "arg": var("x")}, num(0))
        result = prove([], claim, ["x"])
        assert result["ok"] is True

    def test_quantifiers(self):
        # Prove: forall x. x + 0 = x
        body = rel("=", binary("+", var("x"), num(0)), var("x"))
        claim = {"type": "forall", "vars": ["x"], "body": body}
        
        result = prove([], claim, [])
        assert result["ok"] is True

    def test_unsat_assumptions(self):
        # Assumptions: x > 0 and x < 0 (contradiction)
        # Any claim should technically follow from False, but let's see how our prover handles it
        assumptions = [
            rel(">", var("x"), num(0)),
            rel("<", var("x"), num(0))
        ]
        claim = rel("=", var("x"), num(100))
        
        result = prove(assumptions, claim, ["x"])
        assert result["ok"] is True  # Ex falso quodlibet

    def test_invalid_input(self):
        # Missing claim
        result = prove([], {})
        assert result["ok"] is False
        assert result["status"] == "error"
