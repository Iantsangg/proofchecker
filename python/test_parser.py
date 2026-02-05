import pytest
from parser import parse, ParseError

class TestParser:
    def test_simple_parse(self):
        text = "prove x > 0"
        ast = parse(text)
        assert ast["claim"]["type"] == "rel"
        assert ast["claim"]["op"] == ">"
        
    def test_assumptions_and_claim(self):
        text = """
        assume x > 0
        assume y < 10
        prove x + y < 20
        """
        ast = parse(text)
        assert len(ast["assumptions"]) == 2
        assert ast["claim"] is not None
        assert "x" in ast["vars"]
        assert "y" in ast["vars"]

    def test_operator_precedence(self):
        # x + y * z should be x + (y * z)
        text = "prove x + y * z > 0"
        ast = parse(text)
        lhs = ast["claim"]["lhs"]
        assert lhs["type"] == "bin"
        assert lhs["op"] == "+"
        assert lhs["rhs"]["type"] == "bin"
        assert lhs["rhs"]["op"] == "*"

    def test_parentheses(self):
        # (x + y) * z
        text = "prove (x + y) * z > 0"
        ast = parse(text)
        lhs = ast["claim"]["lhs"]
        assert lhs["type"] == "bin"
        assert lhs["op"] == "*"
        assert lhs["lhs"]["type"] == "bin"
        assert lhs["lhs"]["op"] == "+"

    def test_quantifiers(self):
        text = "prove forall x. x >= 0"
        ast = parse(text)
        claim = ast["claim"]
        assert claim["type"] == "forall"
        assert "x" in claim["vars"]
        assert claim["body"]["type"] == "rel"

    def test_syntax_error(self):
        with pytest.raises(ParseError):
            parse("prove x >") # Incomplete

    def test_unknown_token(self):
        with pytest.raises(ParseError):
            parse("prove x @ 0")
