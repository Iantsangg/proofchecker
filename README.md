# Proof Checker

[![Python Tests](https://github.com/Iantsangg/proofchecker/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Iantsangg/proofchecker/actions/workflows/python-tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An automated theorem prover for real arithmetic using **Z3 SMT solver**. Features a human-readable DSL, interactive REPL, and both Python and C++ implementations.

## ✨ Features

- 🧮 **SMT-based proving** — Uses Z3 to verify mathematical claims
- 📝 **Human-readable DSL** — Write proofs in natural mathematical syntax
- 🗣️ **Natural English** — Use `suppose`, `given`, `therefore` instead of formal keywords
- 🔢 **Set membership** — Write `let x in R`, `let n in Z`, `let k in N`
- 🔗 **Inequality chaining** — Write `0 < x <= y < z` naturally
- 📦 **Theorem imports** — Build reusable proof libraries
- 🔀 **Proof by cases** — Split proofs into exhaustive cases
- 📊 **Integer/Real types** — Type annotations for precise reasoning
- 🔄 **Interactive REPL** — Build proofs step-by-step
- ⚡ **Dual implementation** — Python for ease, C++ for performance

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/Iantsangg/proofchecker.git
cd proofchecker
python -m venv .venv && source .venv/bin/activate
pip install z3-solver pytest

# Run your first proof
python check_proof.py examples/example.proof
```

**Output:**
```
File: examples/example.proof
----------------------------------------
STATUS: PROVEN
The claim follows logically from the assumptions.
```

### 🌐 Web Playground

Try proofs interactively in your browser:

```bash
cd proofchecker
source .venv/bin/activate
pip install flask  # if not installed
cd web && python app.py
```

Then open **http://localhost:5050** — write proofs and see instant verification!

## 📖 Examples

### Basic Proof
```
# example.proof
assume x > 0
assume y > 0
prove x + y > 0
```

### Inequality Chaining
```
# chained.proof
assume 0 < a <= b < c
prove a < c
```

### Proof by Cases
```
# cases.proof
assume x != 0

cases:
    case x > 0:
        have x * x > 0
    case x < 0:
        have x * x > 0

prove x * x > 0
```

### Using Imports
```
# my_proof.proof
import "../stdlib/arithmetic.proof"

assume a > 0
assume b > 0
apply positive_sum
prove a + b > 0
```

### Integer Types
```
# integers.proof
let n: Int
assume n > 0
prove n >= 1
```

### Natural English Syntax
```
# You can write proofs in natural English!
suppose x > 0
given y > 0
then x + y > x
therefore x + y > 0
```

### Set Membership
```
# Declare variables with set membership
let x in R          # x is a real number
let n in Z          # n is an integer
let k in N          # k is a natural number (adds k >= 0)
let p in Z+         # p is a positive integer (adds p > 0)

prove k >= 0        # Automatically true from k in N
```

## 📚 Standard Library

Import common theorems from `stdlib/arithmetic.proof`:

| Theorem | Statement |
|---------|-----------|
| `positive_sum` | a > 0 ∧ b > 0 → a + b > 0 |
| `nonneg_sum` | a ≥ 0 ∧ b ≥ 0 → a + b ≥ 0 |
| `square_nonneg` | x² ≥ 0 |
| `positive_product` | a > 0 ∧ b > 0 → a·b > 0 |
| `lt_trans` | a < b ∧ b < c → a < c |
| `le_trans` | a ≤ b ∧ b ≤ c → a ≤ c |

## 🛠️ DSL Reference

```
# Statements (with English aliases)
assume <formula>          # (or: suppose, given, assuming, if)
prove <formula>           # (or: show, therefore, thus, hence, conclude)
have <formula>            # (or: then, so, know, note, observe)
let x                     # Declare variable (Real)
let n: Int                # Declare integer
let x in R/Z/N/Q          # Set membership (R=reals, Z=integers, N=naturals)
let x in R+/Z+/N+         # Positive variants (adds x > 0)
import "path.proof"       # Import theorems
theorem name: ... prove   # (or: lemma)
apply theorem_name        # (or: use, using, by)

# Formulas
x > 0, x >= 0, x = 0      # Comparisons
x != 0                    # Not equal
0 < x <= y                # Chained comparisons
A and B, A or B           # Logical operators (and: also "but")
not A, A implies B        # Negation, implication
forall x. P(x)            # Universal (or: all, every, each)
exists x. P(x)            # Existential (or: some, any)

# Expressions
x + y, x - y, x * y       # Arithmetic
x ^ 2, sqrt(x), abs(x)    # Power, sqrt, abs
|x|                       # Absolute value (alt)
min(x, y), max(x, y)      # Min/max
```

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  .proof     │────▶│   Parser    │────▶│  JSON AST   │
│   file      │     │   (Python)  │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌─────────────┐     ┌──────▼──────┐
                    │   Result    │◀────│   Prover    │
                    │proven/false │     │ (Python/C++)│
                    └─────────────┘     └──────┬──────┘
                                               │
                                        ┌──────▼──────┐
                                        │ Z3 SMT      │
                                        │ Solver      │
                                        └─────────────┘
```

| Component | File | Description |
|-----------|------|-------------|
| Parser | `python/parser.py` | Lexer + recursive descent parser |
| Prover | `python/prover.py` | Z3 integration, proof checking |
| C++ Prover | `cpp/prover.cpp` | Native C++ implementation |
| CLI | `check_proof.py` | Main entry point |

## 🧪 Testing

```bash
# Run unit tests
cd python && python -m pytest -v

# Test all examples
for f in examples/*.proof; do python check_proof.py "$f"; done
```

## 📁 Project Structure

```
proofchecker/
├── python/
│   ├── parser.py      # DSL parser
│   ├── prover.py      # Z3 prover
│   └── test_*.py      # Unit tests
├── cpp/
│   └── prover.cpp     # C++ prover
├── stdlib/
│   └── arithmetic.proof   # Standard library
├── examples/          # Example proofs
└── check_proof.py     # Main CLI
```

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.
