# User-defined Function Macros

## Related Issues and PRs

* [Semantic Versioning Issue](https://github.com/cedar-policy/cedar/issues/637)
* [RFC 58 - Standard Library](https://github.com/cedar-policy/rfcs/pull/58)

## Timeline

* Started: 2024-03-20

## Summary

This RFC proposes to support user-defined function-like macros in Cedar.
We call these Cedar Function Macros (macros for short).
Cedar Function Macros provide a lightweight mechanism for users to create abstractions in their policies, aiding readability and reducing the chance for errors. 
Cedar Function Macros have restrictions to ensure termination and efficiency, maintain the feasibility of validation and analysis, and help ensure policies are readable.
An important implementation note is that Cedar policies may be implemented purely through desugaring.

### Basic Example

Looking at the linked issue, the *semantic versioning* (SemVer) use case is a perfect use-case for functions. SemVer can be trivially encoded within Cedar’s existing expression language.

```
// Permit access when the api is greater than 2.1
permit (principal, action == Action::"someAction", resource)
when {
    resource.apiVersion.major > 2 ||
    (resource.apiVersion.major == 2 && resource.apiVersion.minor >= 1)
};
```

Here it is instead represented with functions

```
def semver(?major, ?minor, ?patch) 
  { major : ?major, minor : ?minor, patch : ?patch }
;

// lhs > rhs ?
def semverGT(?lhs, ?rhs) 
  if ?lhs.major == ?rhs.major then 
    if ?lhs.minor == ?rhs.minor then
      ?lhs.patch > ?rhs.patch
    else
      ?lhs.minor > ?rhs.minor
  else
    ?lhs.major > ?rhs.major
;

// Permit access when the api is greater than 2.1
permit (principal, action == Action::"someAction", resource)
when {
     semverGT(resource.apiVersion, semver(2,1,0))
};
```

For simplicity, safety, and readability, Cedar macros cannot call other macros, and cannot take macros as arguments.

## Motivation

Cedar currently lacks mechanisms for users to build abstractions. The only existing mechanism is extension functions, which are insufficient for two reasons:

1. They are extremely heavyweight, requiring modifying the source of the Cedar evaluator. This means that users who want to stay on official versions of Cedar have no choice but to attempt to submit a PR and get it accepted into the mainline. This process does not scale.
    1. For data structures that are relatively standard (ex: SemVer, or OID Users as proposed in [RFC 58](https://github.com/cedar-policy/rfcs/blob/cdisselkoen/standard-library/text/0058-standard-library.md)), it’s hard to know what’s in-demand enough to be included, and how to balance that against avoiding bloat. There’s no way to naturally observe usage because the only way to “install” the extension pre-acceptance is to vend a modified version of Cedar.
    2. Users may have data structures that are totally bespoke to their systems. It makes no sense to include these in the standard Cedar distribution at all, yet users may still want some way to build abstractions. 
2. They are too powerful. Extensions are implemented via arbitrary Rust code, which is essential for encoding features that cannot be represented via Cedar expressions (such as IP Addresses), but opens the door for a wide range of bugs/design issues. It’s trivial to design an extension that is difficult to validate and/or logically encode for analysis. Problematically, extension functions can potentially exhibit non-determinism, non-termination, or non-linear performance; interact with the operating system; or violate memory safety. This raises the code review burden when considering an extension function's implementation.

In contrast, function macros written as simple abstractions over Cedar expressions, which themselves cannot call other Cedar functions, have none of these problems. They naturally inherit the properties of Cedar expressions. Cedar functions are guaranteed to terminate and be deterministic. Since they are compositions of Cedar expressions, it’s easy to validate and analyze them.

## Detailed Design

### Function Macro declarations

This RFC adds a new top level form to Cedar policysets: the function macro declaration.

A Cedar function macro declaration is composed of three elements:

1. A name, which is a valid (possibly namespaced) identifier.
2. A list of parameters, each of which is a non-namespaced identifier preceded by a `?`.
3. A body, which is a Cedar expression.
    1. The body may contain (non-namespaced) variables, drawn from the function's parameters.
    2. The body may not contain calls to other functions.
    3. The body may contain functions calls to builtin Cedar functions/methods or extensions calls. (ex: Things like `.contains()` and `ip("10.10.10.10")` are fine)
    4. Standard Cedar variables (`principal`, `action`, `resource`, and `context`) are *not* considered bound within the body (following the principle of macro hygiene). 


Structurally, a declaration is written like this:

```
def name(?param1, ?param2) body ;
```
Use of an unbound variable in the body is a syntax error.
A parameter list may not declare the same variable twice, and may not list any standard Cedar variables.
An unused variable is a syntax warning.
Function and variable names share the same namespace, with standard lexical scoping.
Inside of a function, any function application (see below) that does not resolve to an extension function or built-in operation is an error. In other words, Cedar functions are not permitted to call other Cedar functions.

### Function macro applications (a.k.a. function calls)

A function macro application has the same syntax as an extension function constructor application. In particular, a function application is composed of two elements:

1. The function name (potentially namespaced)
2. A comma separated list of arguments, which are arbitrary cedar expressions.

Here are some examples:

```
foo(1, 2, principal.name)
bar(1 + 1, resource.owner in principal)
baz(some_other_function(3))
```

Macro arguments are lazily evaluated (i.e., call-by-name), as opposed to extension functions today.
Call-by-name is required to support inlining correctly in the presence of errors.
(Without errors, call-by-name and call-by-value should be equivalent.)
Macros do not exist at run-time -- they cannot be stored in entity attributes, requests, etc. As such, referencing a function by its name, without calling it, is a syntax error.
Arguments for each of a macro's declared parameters, and no more, must be provided at the call, or it's a syntax error.
Other errors (such as type errors or overflow) are detected at runtime, or via validation.
Examples:
```
def foo(?a, ?b) ?a + ?b;

permit(principal,action,resource) when {
  foo + 1 // Parse error
};
permit(principal,action,resource) when {
    foo(1) // Parse error
};
permit(principal,action,resource) when {
    foo(1, 2) // No error
};
permit(principal,action,resource) when {
    foo(1, "hello") // Run time type error
};
permit(principal,action,resource) when {
    foo(1, "hello", principal) // Parse error
};
permit(principal,action,resource) when {
    bar(1, "hello", principal) // Parse error
};
```

### Namespacing/scoping

All macros in a policyset are in scope for all policies, i.e., function declarations do not need to lexically precede use.
Cedar policies and macro bodies are lexically scoped.
`principal`/`action`/`resource`/ `context` are considered to be more tightly bound then function names.
Macro name conflicts at the top level are a parse error.
Macro names may shadow extension functions (results in a warning).
We forbid defining functions with names `principal`, `action`, `resource`, or `context`, to avoid conflicts and confusion with global variable names.

### Formal semantics/Desugaring rules
This RFC does not add any evaluation rules to Cedar, as macros can be completely desugared.
Dusugaring proceeds from the innermost macro call to avoid hygiene issues.
If $f$ is the name of a declared macro, _def_($f$) is the body of the definition, and $p_1, ..., p_n$ is the list of parameters in the definition.
Let $e_1, ..., e_n$ be a list of Cedar expression that do not contain any Cedar Function calls:
$f(e_1, ..., e_n) \rightarrow$ _def_ $(f) [p_1 \mapsto e_1, ..., p_n \mapsto e_n]$
Where $e[x \mapsto e']$ means to substitute $e'$ for $x$ in $e$, as usual.

### Formal grammar
The grammar of Cedar expressions is unchanged, as we re-use the existing call form.
```
macro ::= 'def' Path '(' Params? ')' Expr ';'
Params ::= ParamIdent (',' ParamIdent)? ','?
ParamIdent ::= '?' IDENT // These are equivalent to the production rule for template slots
```
Note the `Params` non-terminal allows trailing commas in parameter lists.

### Validation and Analysis

The validator typechecks macros at use-sites via inlining.
This means that macros can be polymorphic. For example, one could write the following, where `eq` is used in the first instance with a pair of entities, and in the second instance with a pair of strings.
```
def eq(?a, ?b) ?a == ?b ;

permit(principal, action, resource)
when {
  eq(principal,resource.owner) ||
  eq(principal.org,"Admin")
};
```

Likewise, any static analysis tools would work via inlining.

## Drawbacks

### Redundancy
Cedar macros can only accomplish things that can already accomplished with Cedar expressions.
This means we are not expanding the expressive power of Cedar in any way. 
We are also adding more than one way to accomplish the same task.
Bringing back our SemVer example:
```
// Permit access when the api is greater than 2.1
permit (principal, action == Action::"someAction", resource)
when {
    resource.apiVersion.major > 2 ||
    (resource.apiVersion.major == 2 && resource.apiVersion.minor >= 1)
};
```
This policy does accomplish the user's goal of encoding the SemVer relationship.
The problem is readability. A reader of this policy has to work out that it is implementing the standard semantic version comparison operator, and not some bespoke versioning scheme. Another problem is maintainability. If you have multiple policies that reason about SemVers, you have to repeat the logic, inline, in each policy. This violates basic software engineering tenets (Don’t Repeat Yourself), allowing bugs to sneak in via typos or botched copy/paste.

### No custom parsing or error-handling
Extension functions provide more full-featured constructors through custom parsing and error handling, but Cedar functions provide no such facilities. This may make them harder to read, write, and understand.

For example, you could encode a decimal number as a `Long`, and then make Cedar functions to construct and compare decimals:
```
def mydecimal(?i,?f) 
  if ?f >= 0 && ?f <= 9999 then
    ?i * 10000 + ?f    // will overflow if i too big
  else
    18446744073709551615 + 1    // fraction f too big: induce overflow
;

def mydecimalLTE(?d,?e) {
  ?d <= ?e    // d and e are just Long numbers
}
```
These functions basically implement the equivalent of Cedar `decimal` numbers. But the approach has at least two drawbacks.

First, if `i` and/or `f` are outside the allowed range, you will get a Cedar overflow exception at run-time. This exception is not as illuminating as the custom error emitted by the `decimal` extension function (whose message will be `"Too many digits"`).
Moreover, custom errors from constructor parameter validity checks can be emitted during validation when using extension functions, but not when using Cedar functions.

Second, there is no special parsing for Cedar functions. With Cedar's built-in `decimal`, you can write `decimal("123.12")` which more directly conveys the number being represented than does `mydecimal(123,12)`.

Of course, these drawbacks do not necessarily speak against Cedar functions generally, but suggest that for suitably general use-cases (like decimal numbers!), an extension function might be warranted instead.

### Readability: Policies are no longer standalone
A policy can no longer be read by itself, it has to be read in the context of all function definitions it uses.
Policies that use a large number of functions may be hard to read.


## Alternatives

### Naming: Are these macros or are these functions?
The feature described in this RFC could be interpreted as either Macros or as Call-By-Name pure functions. 
They are equivalent in this context.
This raises the question of what we should call them.
The RFC opts for Macros, and this sections details the pros and cons of each.

Pros of calling them "Functions":

* Developers are probably more familiar with the concepts of functions than of macros. Many modern languages lack a macro facility (Javascript, Java, Python, Ruby), and the feature looks like normal function calls.
* Macros mean different things in different languages: C/C++/Rust macros allow you to edit the token stream, whereas this RFC's feature can only operate on fully parsed ASTs, and can only produce fully parsed ASTs. In addition, we provide no way to pattern match/pull features out of the argument asts.
* Macros may have a poor reputation as producing impossible to read code/error messages. Most languages with macros have the guidance to avoid them if possible.

Pros of calling them "Macros":
* While some mainstream languages lake a macro facility, all mainstream languages lack Call-By-Name functions. Most readers are used to CBV languages. So they inherently assume (having not actually read the docs) that for functions when you write f(1+2,principal.id like "foo") then you will evaluate 1+2 and then principal.id like "foo", and then call the function with the results. They will not imagine that inlining will happen, and that short-circuiting and whatnot can change the results. By calling them macros, we help point out this distinction.
* Regardless of the particular macro implementation (C/Rust/Whatever), users who are familiar with macros will understand that macros do not evaluate their arguments. For macros they know that when you write f(1+2,principal.id like "foo") you are substituting full expressions 1+2 and principal.id like "foo" into the body, you are not evaluating the them first.


### Type annotations
We could require/allow Cedar functions to have type annotations, taking type definitions from either the schema or allowing them to be inline.

Example:

Schema:
```
type SemVer = { major : Long, minor : Long, patch : Long };
```
Policy:
```
def semver(?major : Long, ?minor : Long, ?patch : Long) -> Semver 
  { major : ?major, minor : ?minor, patch : ?patch }
;
```

This would allow functions to typechecked in absence of a use-site, and allow for easier user specification of intent.
It would also probably result in clearer type checker error messages.

If we allowed `type` declarations in policy set files, it would just be one file:

```
type Semver = { major : Long, minor : Long, patch : Long };
def semver(?major : Long, ?minor : Long, ?patch : Long) -> Semver 
   major : ?major, minor : ?minor, patch : ?patch 
;
```

This introduces the following questions:

1. Do we allow `type` declarations allowed in policy sets, or just in schemas?
2. Are type annotations on functions enforced dynamically à la Contracts, or are they just ignored at runtime?
  1. If they are dynamically enforced, that implies access to the schema to unfold type definitions. It also may introduce redundant type checking.
3. Are type annotations required or optional?
4. Will we have types to support generics, i.e., polymorphism?
5. Will type annotations have support for parametric polymorphism/generics?


Leaving them out for this RFC only precludes only one future design decision, making type annotations required.
This decision feels unlikely, as we want Cedar to be useful without using a schema/the validator.
Adding _optional_ type annotations in the future is backwards compatible, but mandating type annotations will not be. 
It will at minimum require a syntax change to add the annotations, and
may be impossible due to the use of polymorphic functions.

### Call By Value
Functions could be call-by-value instead of call-by-name.
In general, this would follow principle of least surprise.
Extension functions are call-by-value, and few popular languages have call-by-name functions.

However, CBV without further changes would lead to validation soundness issues. In particular, consider the following.
```
function drop(a,b) { a };
permit(principal,action,resource)
when { drop(true,1+"hello") };
```
This policy will validate because once we've inlined the function we'd have
```
permit(principal,action,resource)
when { true };
```
But if we actually do CBV evaluation then this policy will fail because `1+"hello"` will fail. We could solve this problem by validating the argument expressions of a function call individually, in addition to validating the entire policy after inlining. But that's extra work. There's also the same problem with analysis: Our logical encoding would have to do CBV to be consistent with the actual evaluator, rather than just inlining, or else we need to prove that eager-eval(e) = lazy-eval(e) for all validated e.

CBN also has the benefit that it's more powerful. For example, you could not define `implies` as follows if we had CBV:
```
def implies(e1,e1) {
  !e1 || (e1 && e2)
}
permit(principal,action,resource) when {
  implies(principal has attr,
          resource has attr && principal.attr == resource.attr)
};
```
The above won't work with CBV because the second expression to the call to `implies` will fail if `principal.attr` does not exist.

### Let functions call other functions
As long as cycles are forbidden and functions as arguments are disallowed, we could allow functions to call other functions without sacrificing termination.
However, the potential complexity explosion is high, and it's backwards compatible to add this later.

### Naming
Should these really be called `function`s? They are essentially macros. Call them that?

## Unresolved Questions

1. Do any functions ship with Cedar? If so, which ones? Leaving that out of this RFC and proposing it's handled equivalently to [RFC 58](https://github.com/cedar-policy/rfcs/pull/58)
2. Can you import functions? Leaving that for a future RFC.
