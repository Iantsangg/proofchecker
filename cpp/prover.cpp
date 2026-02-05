/*
 * Proof Checker - C++ Implementation
 *
 * A native C++ theorem prover using Z3 SMT solver.
 * Mirrors the Python implementation with JSON input/output.
 *
 * Build: mkdir build && cd build && cmake .. && make
 * Usage: ./prover < input.json
 */

#include <iostream>
#include <map>
#include <nlohmann/json.hpp>
#include <stdexcept>
#include <string>
#include <z3++.h>

using json = nlohmann::json;
using namespace z3;

class ProofError : public std::runtime_error {
public:
  explicit ProofError(const std::string &msg) : std::runtime_error(msg) {}
};

class TermError : public ProofError {
public:
  explicit TermError(const std::string &msg)
      : ProofError("Term error: " + msg) {}
};

class FormulaError : public ProofError {
public:
  explicit FormulaError(const std::string &msg)
      : ProofError("Formula error: " + msg) {}
};

// Use std::map with expr stored via optional wrapper
struct ExprWrapper {
  std::optional<expr> e;
  ExprWrapper() = default;
  ExprWrapper(expr ex) : e(std::move(ex)) {}
  operator expr() const { return *e; }
};

using Environment = std::map<std::string, ExprWrapper>;
using VarTypes = std::map<std::string, std::string>;

// Forward declarations
expr term_to_z3(const json &t, context &ctx, Environment &env,
                const VarTypes &var_types);
expr formula_to_z3(const json &f, context &ctx, Environment &env,
                   const VarTypes &var_types);

/**
 * Get or create a variable in the environment.
 * Uses var_types to determine whether to create Int or Real.
 */
expr get_var(const std::string &name, context &ctx, Environment &env,
             const VarTypes &var_types) {
  auto it = env.find(name);
  if (it != env.end()) {
    return it->second;
  }
  expr v = (var_types.count(name) && var_types.at(name) == "Int")
               ? ctx.int_const(name.c_str())
               : ctx.real_const(name.c_str());
  env[name] = ExprWrapper(v);
  return v;
}

/**
 * Convert a term JSON object to a Z3 expression.
 */
expr term_to_z3(const json &t, context &ctx, Environment &env,
                const VarTypes &var_types) {
  if (!t.is_object()) {
    throw TermError("Term must be an object");
  }

  if (!t.contains("type")) {
    throw TermError("Term missing 'type' field");
  }

  std::string ty = t["type"];

  if (ty == "num") {
    if (!t.contains("value")) {
      throw TermError("Numeric term missing 'value' field");
    }
    std::string val;
    if (t["value"].is_string()) {
      val = t["value"].get<std::string>();
    } else if (t["value"].is_number_integer()) {
      val = std::to_string(t["value"].get<int64_t>());
    } else {
      val = std::to_string(t["value"].get<double>());
    }
    return ctx.real_val(val.c_str());
  }

  if (ty == "var") {
    if (!t.contains("name")) {
      throw TermError("Variable term missing 'name' field");
    }
    return get_var(t["name"].get<std::string>(), ctx, env, var_types);
  }

  if (ty == "bin") {
    if (!t.contains("op") || !t.contains("lhs") || !t.contains("rhs")) {
      throw TermError("Binary term missing 'op', 'lhs', or 'rhs' field");
    }

    std::string op = t["op"];
    expr a = term_to_z3(t["lhs"], ctx, env, var_types);
    expr b = term_to_z3(t["rhs"], ctx, env, var_types);

    if (op == "+")
      return a + b;
    if (op == "-")
      return a - b;
    if (op == "*")
      return a * b;
    if (op == "/")
      return a / b;
    throw TermError("Unknown binary operator: " + op);
  }

  if (ty == "abs") {
    if (!t.contains("arg")) {
      throw TermError("Abs term missing 'arg' field");
    }
    expr x = term_to_z3(t["arg"], ctx, env, var_types);
    return ite(x >= 0, x, -x);
  }

  if (ty == "neg") {
    if (!t.contains("arg")) {
      throw TermError("Neg term missing 'arg' field");
    }
    expr x = term_to_z3(t["arg"], ctx, env, var_types);
    return -x;
  }

  if (ty == "pow") {
    if (!t.contains("base") || !t.contains("exp")) {
      throw TermError("Pow term missing 'base' or 'exp' field");
    }
    expr base = term_to_z3(t["base"], ctx, env, var_types);
    expr exp_val = term_to_z3(t["exp"], ctx, env, var_types);
    return pw(base, exp_val);
  }

  if (ty == "sqrt") {
    if (!t.contains("arg")) {
      throw TermError("Sqrt term missing 'arg' field");
    }
    expr x = term_to_z3(t["arg"], ctx, env, var_types);
    return pw(x, ctx.real_val("1/2"));
  }

  if (ty == "min") {
    if (!t.contains("args") || t["args"].size() < 2) {
      throw TermError("Min requires at least 2 arguments");
    }

    expr result = term_to_z3(t["args"][0], ctx, env, var_types);
    for (size_t i = 1; i < t["args"].size(); ++i) {
      expr other = term_to_z3(t["args"][i], ctx, env, var_types);
      result = ite(result <= other, result, other);
    }
    return result;
  }

  if (ty == "max") {
    if (!t.contains("args") || t["args"].size() < 2) {
      throw TermError("Max requires at least 2 arguments");
    }

    expr result = term_to_z3(t["args"][0], ctx, env, var_types);
    for (size_t i = 1; i < t["args"].size(); ++i) {
      expr other = term_to_z3(t["args"][i], ctx, env, var_types);
      result = ite(result >= other, result, other);
    }
    return result;
  }

  throw TermError("Unknown term type: " + ty);
}

/**
 * Convert a formula JSON object to a Z3 expression.
 */
expr formula_to_z3(const json &f, context &ctx, Environment &env,
                   const VarTypes &var_types) {
  if (!f.is_object()) {
    throw FormulaError("Formula must be an object");
  }

  if (!f.contains("type")) {
    throw FormulaError("Formula missing 'type' field");
  }

  std::string ty = f["type"];

  if (ty == "rel") {
    if (!f.contains("op") || !f.contains("lhs") || !f.contains("rhs")) {
      throw FormulaError(
          "Relational formula missing 'op', 'lhs', or 'rhs' field");
    }

    std::string op = f["op"];
    expr lhs = term_to_z3(f["lhs"], ctx, env, var_types);
    expr rhs = term_to_z3(f["rhs"], ctx, env, var_types);

    if (op == "<")
      return lhs < rhs;
    if (op == "<=")
      return lhs <= rhs;
    if (op == "=")
      return lhs == rhs;
    if (op == "!=")
      return lhs != rhs;
    if (op == ">")
      return lhs > rhs;
    if (op == ">=")
      return lhs >= rhs;
    throw FormulaError("Unknown relational operator: " + op);
  }

  if (ty == "and") {
    if (!f.contains("args")) {
      throw FormulaError("And formula missing 'args' field");
    }

    if (f["args"].empty()) {
      return ctx.bool_val(true); // Empty conjunction is true
    }

    expr_vector args(ctx);
    for (const auto &arg : f["args"]) {
      args.push_back(formula_to_z3(arg, ctx, env, var_types));
    }
    return mk_and(args);
  }

  if (ty == "or") {
    if (!f.contains("args")) {
      throw FormulaError("Or formula missing 'args' field");
    }

    if (f["args"].empty()) {
      return ctx.bool_val(false); // Empty disjunction is false
    }

    expr_vector args(ctx);
    for (const auto &arg : f["args"]) {
      args.push_back(formula_to_z3(arg, ctx, env, var_types));
    }
    return mk_or(args);
  }

  if (ty == "not") {
    if (!f.contains("arg")) {
      throw FormulaError("Not formula missing 'arg' field");
    }
    return !formula_to_z3(f["arg"], ctx, env, var_types);
  }

  if (ty == "implies") {
    if (!f.contains("lhs") || !f.contains("rhs")) {
      throw FormulaError("Implies formula missing 'lhs' or 'rhs' field");
    }
    expr lhs = formula_to_z3(f["lhs"], ctx, env, var_types);
    expr rhs = formula_to_z3(f["rhs"], ctx, env, var_types);
    return implies(lhs, rhs);
  }

  if (ty == "forall") {
    if (!f.contains("vars") || !f.contains("body")) {
      throw FormulaError("Forall formula missing 'vars' or 'body' field");
    }

    expr_vector quant_vars(ctx);
    for (const auto &name_json : f["vars"]) {
      std::string name = name_json.get<std::string>();
      expr v = (var_types.count(name) && var_types.at(name) == "Int")
                   ? ctx.int_const(name.c_str())
                   : ctx.real_const(name.c_str());
      env[name] = ExprWrapper(v);
      quant_vars.push_back(v);
    }

    expr body = formula_to_z3(f["body"], ctx, env, var_types);
    return forall(quant_vars, body);
  }

  if (ty == "exists") {
    if (!f.contains("vars") || !f.contains("body")) {
      throw FormulaError("Exists formula missing 'vars' or 'body' field");
    }

    expr_vector quant_vars(ctx);
    for (const auto &name_json : f["vars"]) {
      std::string name = name_json.get<std::string>();
      expr v = (var_types.count(name) && var_types.at(name) == "Int")
                   ? ctx.int_const(name.c_str())
                   : ctx.real_const(name.c_str());
      env[name] = ExprWrapper(v);
      quant_vars.push_back(v);
    }

    expr body = formula_to_z3(f["body"], ctx, env, var_types);
    return exists(quant_vars, body);
  }

  throw FormulaError("Unknown formula type: " + ty);
}

/**
 * Format a counterexample model.
 */
json format_model(const model &m, const Environment &env) {
  json model_out = json::object();
  for (const auto &[name, wrapper] : env) {
    expr var = wrapper;
    model_out[name] = m.eval(var, true).to_string();
  }
  return model_out;
}

/**
 * Main proof function.
 */
json prove(const json &req) {
  try {
    context ctx;
    Environment env;
    VarTypes var_types;

    // Parse variable types
    if (req.contains("var_types") && req["var_types"].is_object()) {
      for (auto &[name, type_val] : req["var_types"].items()) {
        var_types[name] = type_val.get<std::string>();
      }
    }

    // Initialize declared variables
    if (req.contains("vars")) {
      for (const auto &name_json : req["vars"]) {
        std::string n = name_json.get<std::string>();
        if (var_types.count(n) && var_types[n] == "Int") {
          env[n] = ExprWrapper(ctx.int_const(n.c_str()));
        } else {
          env[n] = ExprWrapper(ctx.real_const(n.c_str()));
        }
      }
    }

    solver s(ctx);

    // Add assumptions
    if (req.contains("assumptions")) {
      for (const auto &a : req["assumptions"]) {
        s.add(formula_to_z3(a, ctx, env, var_types));
      }
    }

    // Get the claim
    if (!req.contains("claim")) {
      return {{"ok", false},
              {"status", "error"},
              {"error", "Missing 'claim' field"}};
    }

    expr claim = formula_to_z3(req["claim"], ctx, env, var_types);

    // Prove: assumptions => claim
    // Check UNSAT of: assumptions AND (NOT claim)
    s.add(!claim);

    check_result result = s.check();

    if (result == unsat) {
      return {{"ok", true}, {"status", "proven"}};
    }

    if (result == sat) {
      model m = s.get_model();
      return {{"ok", false},
              {"status", "disproven"},
              {"model", format_model(m, env)}};
    }

    // result == unknown
    return {{"ok", false},
            {"status", "unknown"},
            {"message", "Z3 could not determine satisfiability"}};

  } catch (const ProofError &e) {
    return {{"ok", false}, {"status", "error"}, {"error", e.what()}};
  } catch (const z3::exception &e) {
    return {{"ok", false},
            {"status", "error"},
            {"error", std::string("Z3 error: ") + e.msg()}};
  } catch (const std::exception &e) {
    return {{"ok", false},
            {"status", "error"},
            {"error", std::string("Internal error: ") + e.what()}};
  }
}

int main() {
  try {
    json req;
    std::cin >> req;

    json result = prove(req);
    std::cout << result << std::endl;

    return result["ok"] ? 0 : 1;

  } catch (const json::parse_error &e) {
    json error = {{"ok", false},
                  {"status", "error"},
                  {"error", std::string("Invalid JSON: ") + e.what()}};
    std::cout << error << std::endl;
    return 1;
  }
}
