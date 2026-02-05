"""
Proof Checker - Human-Readable DSL Parser

Parses a simple proof language into JSON AST for the prover.

Syntax:
    # Comments start with #
    assume <formula>     (or: suppose, given, assuming, if)
    prove <formula>      (or: show, then, therefore, thus, hence, conclude)
    have <formula>       (or: so, know, note, observe, since)
    let x                (or: where, define, set)
    let n: Int           Type annotation
    let x in R           Set membership (R, Z, N, Q)
    let x in Z+          Positive variant (adds x > 0)
    theorem name: ...    (or: lemma)
    apply theorem_name   (or: use, using, by)
    cases: / case:       (or: when, whenever)
    import "file.proof"

Formula syntax:
    x > 0
    x + y <= z
    x > 0 and y > 0      (or: but)
    x > 0 or x < 0
    not x = 0
    x > 0 implies y > 0  (or: iff)
    forall x. P(x)       (or: all, every, each)
    exists x. P(x)       (or: some, any)

Term syntax:
    42, 3.14           # Numbers
    x, epsilon         # Variables
    x + y, x - y       # Addition, subtraction
    x * y, x / y       # Multiplication, division
    x ^ 2              # Exponentiation
    -x                 # Negation
    abs(x), |x|        # Absolute value
    sqrt(x)            # Square root
    min(x, y)          # Minimum
    max(x, y)          # Maximum
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple


class ParseError(Exception):
    """Error during parsing with location information."""
    def __init__(self, message: str, line: int = None, col: int = None):
        self.line = line
        self.col = col
        if line is not None:
            loc = f"line {line}"
            if col is not None:
                loc += f", col {col}"
            message = f"{loc}: {message}"
        super().__init__(message)


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int


class Lexer:
    """Tokenizer for the proof DSL."""

    KEYWORDS = {
        'assume', 'prove', 'let', 'have', 'assert',
        'and', 'or', 'not', 'implies',
        'forall', 'exists',
        'true', 'false',
        'theorem', 'apply', 'Int', 'Real',
        'import', 'cases', 'case',
        # English aliases
        'suppose', 'given', 'assuming', 'if',       # -> assume
        'show', 'therefore', 'thus', 'hence', 'conclude', 'qed',  # -> prove
        'then', 'so', 'know', 'note', 'observe', 'since', 'get',  # -> have
        'where', 'define', 'set',                   # -> let
        'when', 'whenever',                         # -> case
        'use', 'using', 'by',                       # -> apply
        'lemma',                                    # -> theorem
        'all', 'every', 'each',                     # -> forall
        'some', 'any',                              # -> exists
        'but',                                      # -> and
        'iff',                                      # -> implies (bidirectional later)
        # Set membership
        'in',                                       # -> IN (set membership)
    }

    # Number sets for "x in R", "x in Z", etc.
    NUMBER_SETS = {'R', 'Z', 'N', 'Q', 'Reals', 'Integers', 'Naturals'}

    # Map aliases to canonical token types
    KEYWORD_ALIASES = {
        # assume aliases (for stating hypotheses)
        'suppose': 'ASSUME', 'given': 'ASSUME', 'assuming': 'ASSUME', 'if': 'ASSUME',
        # prove aliases (for the final claim)
        'show': 'PROVE', 'therefore': 'PROVE', 'thus': 'PROVE',
        'hence': 'PROVE', 'conclude': 'PROVE', 'qed': 'PROVE',
        # have aliases (for intermediate steps)
        'then': 'HAVE', 'so': 'HAVE', 'know': 'HAVE',
        'note': 'HAVE', 'observe': 'HAVE', 'since': 'HAVE', 'get': 'HAVE',
        # let aliases
        'where': 'LET', 'define': 'LET', 'set': 'LET',
        # case aliases
        'when': 'CASE', 'whenever': 'CASE',
        # apply aliases
        'use': 'APPLY', 'using': 'APPLY', 'by': 'APPLY',
        # theorem aliases
        'lemma': 'THEOREM',
        # forall aliases
        'all': 'FORALL', 'every': 'FORALL', 'each': 'FORALL',
        # exists aliases
        'some': 'EXISTS', 'any': 'EXISTS',
        # and aliases
        'but': 'AND',
        # implies aliases
        'iff': 'IMPLIES',
    }

    # Map set names to canonical form
    SET_ALIASES = {
        'R': 'R', 'Reals': 'R', 'reals': 'R',
        'Z': 'Z', 'Integers': 'Z', 'integers': 'Z', 'Int': 'Z',
        'N': 'N', 'Naturals': 'N', 'naturals': 'N', 'Nat': 'N',
        'Q': 'Q', 'Rationals': 'Q', 'rationals': 'Q',
    }
    
    FUNCTIONS = {'abs', 'sqrt', 'min', 'max'}
    
    TOKEN_PATTERNS = [
        ('WHITESPACE', r'[ \t]+'),
        ('NEWLINE', r'\n'),
        ('COMMENT', r'#[^\n]*'),
        ('STRING', r'"[^"]*"'),  # String literals for imports
        ('NUMBER', r'\d+\.?\d*'),
        ('IDENT', r'[a-zA-Z_][a-zA-Z0-9_]*'),
        ('LE', r'<='),
        ('GE', r'>='),
        ('NE', r'!='),
        ('IMPLIES_OP', r'=>'),
        ('EQ', r'='),
        ('LT', r'<'),
        ('GT', r'>'),
        ('PLUS', r'\+'),
        ('MINUS', r'-'),
        ('STAR', r'\*'),
        ('SLASH', r'/'),
        ('CARET', r'\^'),
        ('LPAREN', r'\('),
        ('RPAREN', r'\)'),
        ('COMMA', r','),
        ('COLON', r':'),
        ('DOT', r'\.'),
        ('PIPE', r'\|'),
    ]
    
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.pattern = '|'.join(f'(?P<{name}>{pat})' for name, pat in self.TOKEN_PATTERNS)
        self.regex = re.compile(self.pattern)
    
    def tokenize(self) -> List[Token]:
        tokens = []
        
        while self.pos < len(self.source):
            match = self.regex.match(self.source, self.pos)
            
            if not match:
                raise ParseError(f"Unexpected character: {self.source[self.pos]!r}", self.line, self.col)
            
            token_type = match.lastgroup
            token_value = match.group()
            
            if token_type == 'NEWLINE':
                tokens.append(Token('NEWLINE', '\n', self.line, self.col))
                self.line += 1
                self.col = 1
            elif token_type == 'WHITESPACE' or token_type == 'COMMENT':
                pass  # Skip whitespace and comments
            elif token_type == 'IDENT':
                # Check if it's a keyword or function
                lower_value = token_value.lower()
                if token_value in self.KEYWORDS or lower_value in self.KEYWORDS:
                    # Check if it's an alias that maps to a different token type
                    if lower_value in self.KEYWORD_ALIASES:
                        tokens.append(Token(self.KEYWORD_ALIASES[lower_value], token_value, self.line, self.col))
                    elif lower_value == 'in':
                        tokens.append(Token('IN', token_value, self.line, self.col))
                    else:
                        tokens.append(Token(token_value.upper(), token_value, self.line, self.col))
                elif token_value in self.FUNCTIONS:
                    tokens.append(Token('FUNC', token_value, self.line, self.col))
                elif token_value in self.SET_ALIASES:
                    tokens.append(Token('SET', self.SET_ALIASES[token_value], self.line, self.col))
                else:
                    tokens.append(Token('IDENT', token_value, self.line, self.col))
            else:
                tokens.append(Token(token_type, token_value, self.line, self.col))
            
            self.col += len(token_value)
            self.pos = match.end()
        
        tokens.append(Token('EOF', '', self.line, self.col))
        return tokens


class Parser:
    """Recursive descent parser for the proof DSL."""
    
    def __init__(self, tokens: List[Token], base_path: str = None):
        self.tokens = tokens
        self.pos = 0
        self.assumptions = []
        self.steps = []  # Intermediate proof steps (have/assert)
        self.claim = None
        self.variables = set()
        self.var_types = {}  # Variable name -> type ('Int' or 'Real')
        self.theorems = {}  # Theorem name -> {assumptions, conclusion}
        self.current_theorem = None  # For parsing theorem blocks
        self.base_path = base_path or "."  # Base path for relative imports
        self.imported_files = set()  # Track imported files to prevent cycles
        self.errors = []  # Collect errors for recovery mode
    
    def current(self) -> Token:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else self.tokens[-1]
    
    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]
    
    def advance(self) -> Token:
        tok = self.current()
        self.pos += 1
        return tok
    
    def expect(self, token_type: str) -> Token:
        tok = self.current()
        if tok.type != token_type:
            raise ParseError(f"Expected {token_type}, got {tok.type} ({tok.value!r})", tok.line, tok.col)
        return self.advance()
    
    def match(self, *token_types: str) -> bool:
        return self.current().type in token_types
    
    def skip_newlines(self):
        while self.match('NEWLINE'):
            self.advance()
    
    def parse(self) -> Dict[str, Any]:
        """Parse the entire proof file with error recovery."""
        self.skip_newlines()
        
        while not self.match('EOF'):
            try:
                self.parse_statement()
            except ParseError as e:
                # Collect error and try to recover
                self.errors.append(str(e))
                # Skip to next line to recover
                self.recover_to_next_statement()
            self.skip_newlines()
        
        # Report all collected errors
        if self.errors:
            error_msg = f"Found {len(self.errors)} error(s):\n" + "\n".join(f"  - {e}" for e in self.errors)
            raise ParseError(error_msg)
        
        if self.claim is None:
            raise ParseError("No 'prove' statement found")
        
        result = {
            "vars": list(self.variables),
            "var_types": self.var_types,
            "assumptions": self.assumptions,
            "steps": self.steps,
            "claim": self.claim
        }
        
        if self.theorems:
            result["theorems"] = self.theorems
            
        return result
    
    def recover_to_next_statement(self):
        """Skip tokens until we find the start of a new statement."""
        statement_starters = {'ASSUME', 'PROVE', 'HAVE', 'ASSERT', 'LET', 'THEOREM', 'APPLY', 'IMPORT', 'CASES', 'EOF'}
        while not self.match('EOF'):
            if self.match('NEWLINE'):
                self.advance()
                # Check if next token starts a statement
                if self.current().type in statement_starters:
                    return
            else:
                self.advance()
    
    def parse_statement(self):
        """Parse a single statement."""
        tok = self.current()
        
        if tok.type == 'ASSUME':
            self.advance()
            formula = self.parse_formula()
            self.assumptions.append(formula)
        elif tok.type == 'PROVE':
            self.advance()
            self.claim = self.parse_formula()
        elif tok.type in ('HAVE', 'ASSERT'):
            # Intermediate proof step
            self.advance()
            formula = self.parse_formula()
            self.steps.append({"formula": formula})
        elif tok.type == 'LET':
            self.advance()
            name = self.expect('IDENT').value
            var_type = 'Real'  # Default type
            constraint = None  # Optional constraint (e.g., >= 0 for naturals)

            # Check for type annotation: let x: Int
            if self.match('COLON'):
                self.advance()
                type_tok = self.current()
                if type_tok.type in ('INT', 'REAL'):
                    self.advance()
                    var_type = 'Int' if type_tok.type == 'INT' else 'Real'
                else:
                    raise ParseError(f"Expected 'Int' or 'Real', got {type_tok.type}", type_tok.line, type_tok.col)

            # Check for set membership: let x in R, let x in Z, let x in N
            if self.match('IN'):
                self.advance()
                if self.match('SET'):
                    set_name = self.advance().value
                    # Check for positive variant: R+, Z+, N+
                    is_positive = False
                    if self.match('PLUS'):
                        self.advance()
                        is_positive = True

                    # Map set to type and constraint
                    if set_name == 'R':
                        var_type = 'Real'
                        if is_positive:
                            constraint = ('>', 0)
                    elif set_name == 'Z':
                        var_type = 'Int'
                        if is_positive:
                            constraint = ('>', 0)
                    elif set_name == 'N':
                        var_type = 'Int'
                        constraint = ('>=', 0)  # Natural numbers are non-negative integers
                        if is_positive:
                            constraint = ('>', 0)  # Positive naturals (exclude 0)
                    elif set_name == 'Q':
                        var_type = 'Real'  # Z3 doesn't have rationals, use Real
                        if is_positive:
                            constraint = ('>', 0)
                else:
                    raise ParseError(f"Expected set name (R, Z, N, Q), got {self.current().type}", self.current().line, self.current().col)

            # Optional initialization: let x = 5 (consume but ignore value for now)
            if self.match('EQ'):
                self.advance()
                self.parse_expr()  # Consume the expression

            self.variables.add(name)
            self.var_types[name] = var_type

            # Add constraint as assumption if needed
            if constraint:
                op, val = constraint
                self.assumptions.append({
                    "type": "rel",
                    "op": op,
                    "lhs": {"type": "var", "name": name},
                    "rhs": {"type": "num", "value": str(val)}
                })
        elif tok.type == 'THEOREM':
            self.parse_theorem()
        elif tok.type == 'APPLY':
            self.advance()
            theorem_name = self.expect('IDENT').value
            if theorem_name not in self.theorems:
                raise ParseError(f"Unknown theorem: {theorem_name}", tok.line, tok.col)
            # Add the theorem's implication as an assumption
            theorem = self.theorems[theorem_name]
            # Create: (all assumptions) => conclusion
            if theorem["assumptions"]:
                impl = {
                    "type": "implies",
                    "lhs": {"type": "and", "args": theorem["assumptions"]} if len(theorem["assumptions"]) > 1 else theorem["assumptions"][0],
                    "rhs": theorem["conclusion"]
                }
                self.assumptions.append(impl)
            else:
                # No assumptions, just add the conclusion
                self.assumptions.append(theorem["conclusion"])
        elif tok.type == 'IMPORT':
            self.parse_import()
        elif tok.type == 'CASES':
            self.parse_cases()
        else:
            raise ParseError(f"Expected statement keyword (assume/suppose, prove/show, have/so, let/define, theorem/lemma, apply/use, import, or cases), got {tok.type}", tok.line, tok.col)
    
    def parse_theorem(self):
        """Parse a theorem definition."""
        self.advance()  # consume 'theorem'
        name_tok = self.expect('IDENT')
        theorem_name = name_tok.value
        self.expect('COLON')
        self.skip_newlines()
        
        # Save current state
        old_assumptions = self.assumptions
        old_claim = self.claim
        
        # Parse theorem body
        self.assumptions = []
        self.claim = None
        
        # Parse statements until we hit a 'prove'
        while not self.match('EOF') and self.claim is None:
            self.parse_statement()
            self.skip_newlines()
        
        if self.claim is None:
            raise ParseError(f"Theorem '{theorem_name}' has no 'prove' statement", name_tok.line, name_tok.col)
        
        # Store the theorem
        self.theorems[theorem_name] = {
            "assumptions": self.assumptions,
            "conclusion": self.claim
        }
        
        # Restore state
        self.assumptions = old_assumptions
        self.claim = old_claim
    
    def parse_import(self):
        """Parse an import statement and merge imported theorems."""
        import os
        
        self.advance()  # consume 'import'
        
        # Get the file path string
        path_tok = self.expect('STRING')
        import_path = path_tok.value[1:-1]  # Remove quotes
        
        # Resolve relative path from base_path
        if not os.path.isabs(import_path):
            import_path = os.path.join(self.base_path, import_path)
        import_path = os.path.normpath(import_path)
        
        # Check for import cycles
        if import_path in self.imported_files:
            return  # Already imported
        
        self.imported_files.add(import_path)
        
        # Load and parse the imported file
        if not os.path.exists(import_path):
            raise ParseError(f"Import file not found: {import_path}", path_tok.line, path_tok.col)
        
        try:
            with open(import_path, 'r') as f:
                source = f.read()
            
            # Parse imported file
            lexer = Lexer(source)
            tokens = lexer.tokenize()
            import_parser = Parser(tokens, os.path.dirname(import_path))
            import_parser.imported_files = self.imported_files  # Share import tracking
            
            # Parse as a library (no claim required)
            import_parser.skip_newlines()
            while not import_parser.match('EOF'):
                import_parser.parse_statement()
                import_parser.skip_newlines()
            
            # Merge imported theorems
            self.theorems.update(import_parser.theorems)
            
        except Exception as e:
            raise ParseError(f"Error importing {import_path}: {e}", path_tok.line, path_tok.col)
    
    def parse_cases(self):
        """Parse a cases block for proof by cases.
        
        Syntax:
            cases:
                case x > 0:
                    have x * x > 0
                case x < 0:
                    have x * x > 0
                case x = 0:
                    have x * x = 0
        """
        self.advance()  # consume 'cases'
        self.expect('COLON')
        self.skip_newlines()
        
        cases = []
        
        while self.match('CASE'):
            self.advance()  # consume 'case'
            condition = self.parse_formula()
            self.expect('COLON')
            self.skip_newlines()
            
            # Parse statements within this case until we hit another case or end
            case_steps = []
            while not self.match('CASE', 'EOF', 'PROVE', 'ASSUME', 'LET', 'THEOREM', 'IMPORT', 'CASES'):
                if self.match('HAVE', 'ASSERT'):
                    self.advance()
                    formula = self.parse_formula()
                    case_steps.append({"formula": formula})
                    self.skip_newlines()
                elif self.match('NEWLINE'):
                    self.advance()
                else:
                    break
            
            cases.append({
                "condition": condition,
                "steps": case_steps
            })
        
        if not cases:
            raise ParseError("cases block requires at least one 'case'", self.current().line, self.current().col)
        
        # Store cases as a special step type
        self.steps.append({
            "type": "cases",
            "cases": cases
        })
    
    def parse_formula(self) -> Dict[str, Any]:
        """Parse a formula (handles implies at lowest precedence)."""
        return self.parse_implies()
    
    def parse_implies(self) -> Dict[str, Any]:
        """Parse implication (right-associative)."""
        left = self.parse_or()
        
        if self.match('IMPLIES', 'IMPLIES_OP'):
            self.advance()
            right = self.parse_implies()  # Right-associative
            return {"type": "implies", "lhs": left, "rhs": right}
        
        return left
    
    def parse_or(self) -> Dict[str, Any]:
        """Parse disjunction."""
        left = self.parse_and()
        
        args = [left]
        while self.match('OR'):
            self.advance()
            args.append(self.parse_and())
        
        if len(args) == 1:
            return args[0]
        return {"type": "or", "args": args}
    
    def parse_and(self) -> Dict[str, Any]:
        """Parse conjunction."""
        left = self.parse_not()
        
        args = [left]
        while self.match('AND'):
            self.advance()
            args.append(self.parse_not())
        
        if len(args) == 1:
            return args[0]
        return {"type": "and", "args": args}
    
    def parse_not(self) -> Dict[str, Any]:
        """Parse negation."""
        if self.match('NOT'):
            self.advance()
            arg = self.parse_not()
            return {"type": "not", "arg": arg}
        
        return self.parse_quantifier()
    
    def parse_quantifier(self) -> Dict[str, Any]:
        """Parse quantifiers (forall, exists)."""
        if self.match('FORALL', 'EXISTS'):
            quant_type = self.advance().type.lower()
            
            # Parse variable list
            var_names = []
            var_names.append(self.expect('IDENT').value)
            while self.match('COMMA'):
                self.advance()
                var_names.append(self.expect('IDENT').value)
            
            self.expect('DOT')
            
            # Add quantified variables to scope
            for name in var_names:
                self.variables.add(name)
            
            body = self.parse_formula()
            return {"type": quant_type, "vars": var_names, "body": body}
        
        return self.parse_relation()
    
    def parse_relation(self) -> Dict[str, Any]:
        """Parse relational expression, including chained comparisons.
        
        Examples:
            x < y         -> {type: "rel", op: "<", lhs: x, rhs: y}
            0 < x <= y    -> {type: "and", args: [{rel: 0 < x}, {rel: x <= y}]}
        """
        left = self.parse_expr()
        
        op_map = {'LT': '<', 'LE': '<=', 'EQ': '=', 'NE': '!=', 'GT': '>', 'GE': '>='}
        
        if not self.match('LT', 'LE', 'EQ', 'NE', 'GT', 'GE'):
            # No relation, just return the expression
            return left
        
        # Build up chain of comparisons
        comparisons = []
        current_left = left
        
        while self.match('LT', 'LE', 'EQ', 'NE', 'GT', 'GE'):
            tok = self.advance()
            op = op_map[tok.type]
            right = self.parse_expr()
            
            comparisons.append({
                "type": "rel",
                "op": op,
                "lhs": current_left,
                "rhs": right
            })
            
            # The right side becomes the left side for the next comparison
            current_left = right
        
        # If single comparison, return it directly
        if len(comparisons) == 1:
            return comparisons[0]
        
        # Multiple comparisons: combine with AND
        return {"type": "and", "args": comparisons}
    
    def parse_expr(self) -> Dict[str, Any]:
        """Parse additive expression."""
        left = self.parse_term()
        
        while self.match('PLUS', 'MINUS'):
            op = '+' if self.advance().type == 'PLUS' else '-'
            right = self.parse_term()
            left = {"type": "bin", "op": op, "lhs": left, "rhs": right}
        
        return left
    
    def parse_term(self) -> Dict[str, Any]:
        """Parse multiplicative expression."""
        left = self.parse_power()
        
        while self.match('STAR', 'SLASH'):
            op = '*' if self.advance().type == 'STAR' else '/'
            right = self.parse_power()
            left = {"type": "bin", "op": op, "lhs": left, "rhs": right}
        
        return left
    
    def parse_power(self) -> Dict[str, Any]:
        """Parse exponentiation (right-associative)."""
        base = self.parse_unary()
        
        if self.match('CARET'):
            self.advance()
            exp = self.parse_power()  # Right-associative
            return {"type": "pow", "base": base, "exp": exp}
        
        return base
    
    def parse_unary(self) -> Dict[str, Any]:
        """Parse unary operators."""
        if self.match('MINUS'):
            self.advance()
            arg = self.parse_unary()
            return {"type": "neg", "arg": arg}
        
        return self.parse_atom()
    
    def parse_atom(self) -> Dict[str, Any]:
        """Parse atomic expression."""
        tok = self.current()
        
        if tok.type == 'NUMBER':
            self.advance()
            return {"type": "num", "value": tok.value}
        
        if tok.type == 'IDENT':
            self.advance()
            self.variables.add(tok.value)
            return {"type": "var", "name": tok.value}
        
        if tok.type == 'FUNC':
            func_name = self.advance().value
            self.expect('LPAREN')
            args = [self.parse_expr()]
            while self.match('COMMA'):
                self.advance()
                args.append(self.parse_expr())
            self.expect('RPAREN')
            
            if func_name == 'abs':
                if len(args) != 1:
                    raise ParseError(f"abs() takes 1 argument, got {len(args)}", tok.line, tok.col)
                return {"type": "abs", "arg": args[0]}
            elif func_name == 'sqrt':
                if len(args) != 1:
                    raise ParseError(f"sqrt() takes 1 argument, got {len(args)}", tok.line, tok.col)
                return {"type": "sqrt", "arg": args[0]}
            elif func_name == 'min':
                if len(args) < 2:
                    raise ParseError(f"min() requires at least 2 arguments", tok.line, tok.col)
                return {"type": "min", "args": args}
            elif func_name == 'max':
                if len(args) < 2:
                    raise ParseError(f"max() requires at least 2 arguments", tok.line, tok.col)
                return {"type": "max", "args": args}
            else:
                raise ParseError(f"Unknown function: {func_name}", tok.line, tok.col)
        
        if tok.type == 'LPAREN':
            self.advance()
            expr = self.parse_formula()  # Allow full formulas in parens
            self.expect('RPAREN')
            return expr
        
        if tok.type == 'PIPE':
            self.advance()  # consume opening |
            arg = self.parse_expr()
            self.expect('PIPE')  # consume closing |
            return {"type": "abs", "arg": arg}
        
        if tok.type == 'TRUE':
            self.advance()
            return {"type": "and", "args": []}  # Empty AND = true
        
        if tok.type == 'FALSE':
            self.advance()
            return {"type": "or", "args": []}  # Empty OR = false
        
        raise ParseError(f"Unexpected token: {tok.type} ({tok.value!r})", tok.line, tok.col)


def parse(source: str, base_path: str = None) -> Dict[str, Any]:
    """Parse proof DSL source into JSON AST."""
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens, base_path)
    return parser.parse()


def parse_file(filename: str) -> Dict[str, Any]:
    """Parse a proof file into JSON AST."""
    import os
    with open(filename, 'r') as f:
        source = f.read()
    return parse(source, os.path.dirname(os.path.abspath(filename)))


if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python parser.py <file.proof>")
        sys.exit(1)
    
    try:
        ast = parse_file(sys.argv[1])
        print(json.dumps(ast, indent=2))
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)
