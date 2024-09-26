# User-defined Macros

## Related Issues and PRs

* [Semantic Versioning Issue](https://github.com/cedar-policy/cedar/issues/637)
* [RFC 58 - Standard Library](https://github.com/cedar-policy/rfcs/pull/58)

## Timeline

* Started: 2024-03-20

## Summary

This RFC proposes to support user-defined, function-like macros in Cedar.
Cedar macros provide a lightweight mechanism for users to create abstractions in their policies, aiding readability and reducing the chance for errors.
Cedar macros have restrictions to ensure termination and efficiency, maintain the feasibility of validation and analysis, and help ensure policies are readable.

### Basic Example

Looking at the linked issue [#637](https://github.com/cedar-policy/cedar/issues/637), *semantic versioning* (SemVer) is a perfect use-case for macros: it can be trivially encoded within Cedar’s existing expression language, but doing so would make policies hard to read.

```
// Permit access when the api is greater than 2.1
permit (principal, action == Action::"someAction", resource)
when {
    resource.apiVersion.major > 2 ||
    (resource.apiVersion.major == 2 && resource.apiVersion.minor >= 1)
};
```

Here is the same policy expressed using macros.

```
// A semver has three version components: major, minor, and patch
def semver(?major, ?minor, ?patch) 
  { major : ?major, minor : ?minor, patch : ?patch }
;

// Is the semver in the first parameter newer than (>) the second ?
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

Cedar currently lacks adequate mechanisms for users to build abstractions. The only existing mechanism is extension functions, which are limited for two reasons:

1. They are extremely heavyweight, requiring modifications to the Cedar evaluator. This means that users who want to stay on official versions of Cedar have no choice but to attempt to submit a PR and get it accepted into the mainline. This process does not scale.
    1. For data structures that are relatively standard (ex: SemVer, or OID Users as proposed in [RFC 58](https://github.com/cedar-policy/rfcs/blob/cdisselkoen/standard-library/text/0058-standard-library.md)), it’s hard for the Cedar maintainers to know what’s in-demand enough to be included, and how to balance that against avoiding bloat. There’s no way to naturally observe usage because the only way to “install” the extension pre-acceptance is to vend a modified version of Cedar.
    2. Users may have data structures that are totally bespoke to their systems. It makes no sense to include these in the standard Cedar distribution, yet users may still want some way to use them easily.
2. They are too powerful. Extensions are implemented via arbitrary Rust code, which is essential for encoding features that cannot be represented via Cedar expressions (such as IP Addresses), but opens the door for a wide range of bugs/design issues. It’s trivial to design an extension that is difficult to validate and/or logically encode for analysis. Problematically, extension functions can potentially exhibit non-determinism, non-termination, or non-linear performance; interact with the operating system; or violate memory safety. This raises the code review burden when considering an extension function's implementation.

In contrast, macros have none of these problems. Macros are written as simple abstractions over Cedar expressions, whose evaluation is always deterministic. As macros cannot call other macros, they are simple to understand and guaranteed to terminate. Since macros are compositions of Cedar expressions, it’s easy to validate and analyze them.

## Detailed Design

### Macro definitions

This RFC adds a new top level form to Cedar policy sets: the macro definition.
Structurally, a macro definition is written like this:
```
def name(?param1, ?param2) body ;
```
A macro definition has three elements:
1. A name, which is a valid, possibly namespaced, identifier.
2. A list of parameter variables, each of which is a non-namespaced identifier preceded by a `?`. (Declaring the same parameter variable twice is a syntax error.)
3. A body, which is a Cedar expression.
    1. The body may refer to the macro's parameter variables. (Use of an unbound parameter variable is a syntax error. Failure to reference one of the parameter variables is a warning.)
    2. The body may not refer to standard Cedar variables `principal`, `action`, `resource`, and `context`. (Doing so ensures macros are always functions of their parameters.)
    3. The body may not contain calls to other macros. (It may contain calls to builtin or extension functions/methods, such as `.contains()` and `ip("10.10.10.10")`, as usual.)

### Macro applications (a.k.a. macro calls)

A macro application has the same syntax as an extension function constructor application. In particular, an application is composed of two elements:

1. The macro name (potentially namespaced)
2. A comma-separated list of arguments, each of which is an arbitrary Cedar expression.

Here are some examples:

```
foo(1, 2, principal.name)
bar(1 + 1, resource.owner in principal)
baz(ip("1.2.3.4"))
```

A macro call $f(e_1, ..., e_n)$ evaluates to the macro's body but with occurrences of parameters $p_1, ..., p_n$ replaced by argument expressions $e_1, ..., e_n$, respectively. For example, considering or SemVer use-case, evaluating `semver(2,1,0)` produces the expression `{ major : 2, minor : 1, patch : 0 }`.

Importantly, macro calls are evaluated _lazily_, thus using a _call by name_ semantics: We do _not_ evaluate the argument expressions before substituting them in the macro body. To see the effect of this, consider the following:
```
def implies(?e1,?e1) {
   if ?e1 then ?e2 else true
}
permit(principal,action,resource) when {
  implies(principal has attr,
          resource has attr && principal.attr == resource.attr)
};
```
When evaluating the `when` clause, the call to `implies` evaluates to the following
```
  if principal has attr then
     resource has attr && principal.attr == resource.attr
  else true
```
Notice how the argument expression `principal has attr` has been substituted for parameter `?e1` whole-cloth, without evaluating it first (and likewise for the other parameter/argument). This means that if `principal` indeed has optional attribute `attr`, then evaluating sub-expression `principal.attr` in the `then` clause is safe. If we eagerly evaluated a macro call's argument expressions then `principal.attr` would be evaluted eagerly, producing an error if `principal has attr` turns out to be `false`.

### Errors

Macros do not exist at run-time -- they cannot be stored in entity attributes, requests, etc. As such, referencing a macro by its name, without calling it, is a syntax error.
Arguments for each of a macro's declared parameters, and no more, must be provided at the call, or it's a syntax error.
Other errors (such as type errors or overflow) are detected at runtime, or via validation.
Examples:
```
def foo(?a, ?b) ?a + ?b;

permit(principal,action,resource) when {
  foo + 1 // Parse error -- macro foo not in a call
};
permit(principal,action,resource) when {
    foo(1) // Parse error -- too few arguments to foo
};
permit(principal,action,resource) when {
    foo(1, "hello", principal) // Parse error -- too many arguments to foo
};
permit(principal,action,resource) when {
    foo(1, "hello") // Run-time (and validation) type error
};
permit(principal,action,resource) when {
    bar(1, "hello", principal) // Parse error -- no such macro bar
};
```

### Namespacing/scoping

All macros in a policy set are in scope for all policies, i.e., macro definitions do not need to lexically precede their use.
Macro parameter references in expressions are resolved via lexical scoping.
Macro name conflicts at the top level are a parse error.
Macro names may shadow extension functions (results in a warning).
We forbid defining macros with names `principal`, `action`, `resource`, or `context` (and, as mentioned, macro bodies cannot mention these variables either), to avoid conflicts and confusion with global variable names.

### Formal grammar
The grammar of Cedar expressions is unchanged, as we re-use the existing call form.
```
Macro ::= 'def' Path '(' Params? ')' Expr ';'
Params ::= ParamIdent (',' ParamIdent)? ','?
ParamIdent ::= '?' IDENT // These are equivalent to the production rule for template slots
```
Note the `Params` non-terminal allows trailing commas in parameter lists.

### Validation and Analysis

The validator typechecks macros at use-sites via inlining. In particular, when validating a policy, all macro calls are replaced as described in the evaluation semantics above, prior to validating the policy.

This approach means that macros that are defined but never used will not be validated. It also means that macros can be polymorphic. For example, one could write the following, where `eq` is used in the first instance with a pair of entities, and in the second instance with a pair of strings.
```
def eq(?a, ?b) ?a == ?b ;

permit(principal, action, resource)
when {
  eq(principal,resource.owner) ||
  eq(principal.org,"Admin")
};
```

Likewise, any static analysis tools would work via inlining.

### Templates
Macros use the same syntax for their parameter variables as do templates, since in both cases variables are "holes" that are filled in with a Cedar expression to make a full construct -- for templates, the construct is a policy, for macros it is an expression.

Templates can include calls to macros. For example:

```
def semver(?major, ?minor, ?patch) ... // same as initial example
def semverGT(?lhs, ?rhs) ... // same as initial example
permit (
  principal == ?principal,
  action == Action::"view",
  resource in ?resource)
when {
  semverGT(resource.apiVersion, semver(2,1,0))
};
```

When we link this template, we get a full policy, as usual.

A macro parameter can end up having the same name as a template variable, with the effect that it shadows it, which is expected with normal lexical scoping:

```
def isOwner(?principal,?resource) ?principal == ?resource.owner;

permit(principal,action,resource in ?resource)
when {
  isOwner(principal,resource)
};
```

Here, notice that the `isOwner` macro's reference to `?resource` is to its parameter, not to the template slot. (We'd recommend to users to choose different parameter names to avoid confusion.)

As already mentioned, you cannot refer to a parameter in a macro that it does not bind, which enforces hygiene. So the following is not allowed.

```
def isOwner() ?principal == ?resource.owner; 
// ERROR: cannot refer to unbound variables ?principal, ?resource
```


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
Extension functions provide more full-featured constructors through custom parsing and error handling, but Cedar macros provide no such facilities. This may make them harder to read, write, and understand.

For example, you could encode a decimal number as a `Long`, and then make Cedar macros to construct and compare decimals:
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
These macros basically implement the equivalent of Cedar `decimal` numbers. But the approach has at least two drawbacks.

First, if `i` and/or `f` are outside the allowed range, you will get a Cedar overflow exception at run-time. This exception is not as illuminating as the custom error emitted by the `decimal` extension function (whose message will be `"Too many digits"`).
Moreover, custom errors from constructor parameter validity checks can be emitted during validation when using extension functions, but not when using Cedar macros.

Second, there is no special parsing for Cedar macros. With Cedar's built-in `decimal`, you can write `decimal("123.12")` which more directly conveys the number being represented than does `mydecimal(123,1200)`. (Note that `mydecimal(123,12)` represents the number 123.0012, which may surprised some readers!).

Of course, these drawbacks do not necessarily speak against Cedar macros generally, but suggest that for suitably general use-cases (like decimal numbers!), an extension function might be warranted instead.

### Hidden performance costs
Macros allow users to write policies whose size after expansion is exponential in their pre-expansion size. Here is a pathological example.

```
def double (?x) { left: ?x, right: ?x }

permit(principal,action,resource) when {
    double(double(double(double({})))) has left
};
```

With 4 calls to double, we've created a parse tree (and a runtime value) of size $2^4$.

This is a fundamental issue: Macros provide readability through compactness, and in so doing they hide real costs. This is true of any programming language abstraction, and we see this tension play out in many contexts.

One mitigation is to expose the hidden costs, when needed. For example:
- A policy authoring tool could reveal the post-expansion policy size to users, compared to the pre-expansion size, and could warn users in pathological cases like the above.
- Services storing user-provided Cedar policies that wish to protect themselves can impose bounds based on the post-expansion policy size (shared wth users), rather than the concrete policy size.

Ultimately, this RFC takes the position that it is better to give the tool of macros to users to improve the readability and maintainability policies, than it is to withhold that tool for fear that they could misuse it. Without the tool of macros, users must "implement" their effects by cut-and-paste, which still blows up policy size while also making policies harder to read and maintain.

### Readability: Policies are no longer standalone
A policy can no longer be read by itself, it has to be read in the context of all macro definitions it uses.
Policies that use a large number of macros may be hard to read.

## Alternatives

### Allow Cedar variables to appear free in macros

This RFC requires that Cedar variables `principal`, `resource`, etc. not appear in a macro body. Allowing them to appear could make macros easier to read. For example, consider this policy:
```
def hasTagsForRole(?principal,?resource,?role,?tag)
  ?principal.taggedRoles has ?role &&
  ?principal.taggedRoles[?role] has ?tag &&
  ?resource.tags has ?tag &&
  ?principal.taggedRoles[?role][?tag].containsAll(?resource.tags[?tag])
;

permit(principal in Group:"Role-A", action, resource) when {
  hasTagsForRole(principal,resource,"Role-A","country") &&
  hasTagsForRole(principal,resource,"Role-A","job-family") &&
  hasTagsForRole(principal,resource,"Role-B","task")
}
```
In this scenario, a `principal` has a `taggedRoles` attribute to collect tags that are associated with that role, e.g., `principal["Role-A"]["country"]` is a set, if present, that contains the values of the `country` tag associated with `Role-A`. The policy authorizes access to a resource when the principal contains all the values the resource has for the tags `country`, `job-family`, and `task`, which are associated with `Role-A`.

This example is a good use-case for macros: Without them a policy author would need to cut-and-past the `hasTagsForRole` part, producing a policy that is much harder to read and maintain:
```
permit(principal in Group:"Role-A", action, resource) when {
  principal.taggedRoles has "Role-A" &&
  principal.taggedRoles["Role-A"] has "country" &&
  resource.tags has "country" &&
  principal.taggedRoles["Role-A"]["country"].containsAll(resource.tags["country"])
  &&
  principal.taggedRoles has "Role-A" &&
  principal.taggedRoles["Role-A"] has "job-family" &&
  resource.tags has "job-family" &&
  principal.taggedRoles["Role-A"]["job-family"].containsAll(resource.tags["job-family"])
  &&
  principal.taggedRoles has "Role-B" &&
  principal.taggedRoles["Role-B"] has "task" &&
  resource.tags has "task" &&
  principal.taggedRoles["Role-B"]["task"].containsAll(resource.tags["task"])
}
```
But it could potentially be even easier to read, and a little less error prone, if we allowed `principal` and `resource` to appear free in the macro definition:
```
def hasTagsForRole(?role,?tag)
  principal.taggedRoles has ?role &&
  principal.taggedRoles[?role] has ?tag &&
  resource.tags has ?tag &&
  principal.taggedRoles[?role][?tag].containsAll(resource.tags[?tag])
;

permit(principal in Group::"Role-A", action, resource) when {
  hasTagsForRole("Role-A","country") &&
  hasTagsForRole("Role-A","job-family") &&
  hasTagsForRole("Role-B","task")
}
```
This version makes it more clear that the macro is really only a function of `?role` and `?tag` -- the `principal` and `resource` part should always be the policy's `principal` and `resource`, so we should not be forced to abstract them but always rotely fill the same variables.

### Naming: Are these macros or are these functions?
The feature described in this RFC could also be referred to _functions_ with call-by-name semantics, since that is an accurate description of what they are. There are some good reasons to call them functions, instead of macros:

* Developers are probably more familiar with the concept of function than of macro. Many popular languages lack a macro facility (Javascript, Java, Python, Ruby, etc.), and the Cedar feature looks like normal functions. Calling them macros uses term that may seem unnecessary or unfamiliar.
* The macro facility proposed for Cedar is much more limited than macro facilities available in other languages, so the name may be misleading. For example, in C, C++, and Rust, macros can edit the syntax token stream, whereas this RFC's feature can only operate on fully parsed ASTs, and can only produce fully parsed ASTs. In addition, Cedar macros provide no way to pattern match/pull features out of the argument ASTs.
* Convoluted uses of macros, distressingly common in older C and C++ code, have given macros somewhat of a bad reputation, so using the term macro may (wrongly) signal that the proposed Cedar facility could be problematic in ways that it is not.

Despite these downsides, we feel that on balance the term macro is more helpful than harmful:
* Mainstream languages use call-by-value for function calls, rather than call-by-name, so using the term "function" may give the wrong impression. Most readers will inherently assume (having not actually read the docs) that when you write `f(1+2,principal.id like "foo")` you will evaluate `1+2` and then `principal.id like "foo"`, and then call the `f` with the results. They may not suspect call-by-name semantics or appreciate its potentially surprising and powerful effects, as described for the `implies` example above. Thus they may end up writing incorrect policies.
* Those familiar with macros (from C/C++ especially) will properly guess the call-by-name semantics because macro calls in existing languages are call-by-name. Those unfamiliar with macros will still be alerted, by the name, that calls may have different semantics than they expect.

### Type annotations
We could require/allow Cedar macros to have type annotations, taking type definitions from either the schema or allowing them to be inline. Here is our SemVer example with schema:
```
type SemVer = { major : Long, minor : Long, patch : Long };
```
and policy:
```
def semver(?major : Long, ?minor : Long, ?patch : Long) -> Semver 
  { major : ?major, minor : ?minor, patch : ?patch }
;
```

Using type annotations would allow macros to be typechecked independently of policies that use them, and would add checked documentation of intent.
Doing so may also make it easier to provide clear validation error messages.

But introducing type annotations for macros introduces several questions.

1. Do we allow `type` declarations allowed in policy sets, or just in schemas?
2. Are type annotations on macros enforced dynamically à la "contracts," or are they just ignored at runtime?
  1. If they are dynamically enforced, that implies access to the schema to unfold type definitions. It also may introduce redundant type checking.
3. Are type annotations required or optional?
4. Will we have types to support generics, i.e., polymorphism?
5. Will type annotations have support for parametric polymorphism/generics?

Leaving type annotations out of this RFC only precludes only one future design decision, which is making type annotations required.
It seems unlikely we would want to enforce such a requirement, as we have designed Cedar to be useful even when not using a schema and validation.
Adding _optional_ type annotations in the future is backwards compatible.

### Call-by-value macro calls
Macros calls could use call-by-value (CBV) instead of call-by-name semantics.
Doing so might match user expectations: Mainstream languages use call by value, extension functions in Cedar are call by value.

However, using CBV would lead to validation soundness issues if we continued to perform validation by inlining calls. In particular, consider the following.
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
But if we actually do CBV evaluation then this policy will fail because `1+"hello"` will fail. We believe we could solve this problem by validating the argument expressions of a function call individually, in addition to validating the entire policy after inlining. But that's extra work. There's also the same problem with analysis: Our logical encoding would have to do CBV to be consistent with the actual evaluator, rather than just inlining, or else we need to prove that eager-eval(e) = lazy-eval(e) for all validated e.

CBN also has the benefit that it's more powerful. The `implies` example introduced earlier won't work with CBV because the second expression to the call to `implies` will fail if `principal.attr` does not exist.

### Let macros call other macros
As long as cycles are forbidden and macros as arguments to other macros are disallowed, we could allow macros to call other macros while still ensuring termination and determinism.
However, doing so could make macros harder to read and adds some complexity to the implementation.
In-macro calls is always something we can add later.

## Unresolved Questions

We are not proposing how to _manage_ sets of macro definitions. It would be natural to want a standard library of macro definitions, and/or a way to import particular sets of macros from a third-party library. We leave the question of macro distribution and management (and standard libraries) for another RFC (e.g., [RFC 58](https://github.com/cedar-policy/rfcs/pull/58).