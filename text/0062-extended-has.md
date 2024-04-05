# Extended `has` Operator

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2024-04-05

## Summary

This RFC proposes to extend the syntax of the `has` operator to check for the presence of all attributes in an access path.

## Basic example

Suppose that entites of type `User` have an optional `contactInfo` attribute of type `{email: String, address?: {street?: String, zip?: String, country: String}}`. To safely access the `zip` field of a user in a policy, we write a chain of `has` checks as follows:

```
permit(
  principal is User,
  action == Action::"star",
  resource == Movie::"Blockbuster"
) when {
  principal has contactInfo &&
  principal.contactInfo has address &&
  principal.contactInfo.address has zip &&
  principal.contactInfo.address.zip == "90210"
};
```

This RFC proposes to extend the syntax of the `has` operator so that this chain of checks can be written more succinctly as follows:

```
permit(
  principal is User,
  action == Action::"preview",
  resource == Movie::"Blockbuster"
) when {
  principal has contactInfo.address.zip &&
  principal.contactInfo.address.zip == "90210"
};
```

The expression `principal has contactInfo.address.zip` evaluates to true when all the attributes in the given access path are present.

## Motivation

Long chains of `has` checks are tedious to write and hard to read. The extended `has` operator replaces these chains with a single constraint that is easier to read and write.

## Detailed design

This RFC proposes to desugar the new `has` syntax into the corresponding chain of basic `has` checks in the CST -> AST and EST -> AST converter.  This requires extending the parser, CST, and EST to support the new syntax; and changing the CST -> AST and EST -> AST converters to implement the desugaring. It should be possible to share the core desugaring code between the two converters.

No other components need to change. In particular, validator, evaluator, and Lean models remain the same.

### Extending the syntax

We extend the grammar as follows:

```
Relation ::= ... | Add 'has' (IDENT['.' IDENT]* | STR) |  ...
```

Note that this extension works only for attribute names that are valid Cedar identifiers. It cannot be used with attribute names that are not valid Cedar identifiers. For example, we cannot write `principal has "contact info".address.zip`; this check has to be expressed as `principal has "contact info" && principal["contact info"] has address.zip`. Arbitrary attribute names can be supported in the future if there is demand for it.

### Desugaring the extended syntax

The following Lean code shows how to perform the desugaring given an expression, an attribute, and a list of attribute:

```
def desugarHasChainStep
  (acc : Expr × Expr)
  (attr : Attr) : Expr × Expr :=
  (Expr.getAttr acc.fst attr,
   Expr.and acc.snd (Expr.hasAttr acc.fst attr))

def desugarHasChain
  (x : Expr)
  (attr : Attr)
  (attrs : List Attr) : Expr :=
  (attrs.foldl
    desugarHasChainStep
      (Expr.getAttr x attr,
       Expr.hasAttr x attr)).snd
```

Here are some examples of desugared ASTs:

```
#eval desugarHasChain (Expr.var .principal) "contactInfo" []

Expr.hasAttr (Expr.var .principal) "contactInfo"

#eval desugarHasChain (Expr.var .principal) "contactInfo" ["address"]

Expr.and
  (Expr.hasAttr (Expr.var .principal) "contactInfo")
  (Expr.hasAttr
    (Expr.getAttr (Expr.var .principal) "contactInfo")
    "address")

#eval desugarHasChain (Expr.var .principal) "contactInfo" ["address", "zip"]

Expr.and
  (Expr.and
    (Expr.hasAttr (Expr.var .principal) "contactInfo")
    (Expr.hasAttr
      (Expr.getAttr (Expr.var .principal) "contactInfo")
      "address"))
  (Expr.hasAttr
    (Expr.getAttr
      (Expr.getAttr (Expr.var .principal) "contactInfo")
      "address")
    "zip")
```


## Drawbacks

1. This feature requires extending the grammar, CST, EST, CST -> AST, and CST -> EST converters. This extension will be a breaking change to the EST. We have to either modify the EST `hasAttr` node to include an additional List argument, or introduce a separate node to represent the extended syntax. Either change may break code that operates on the EST.

2. If we choose _not_ to modify the EST, and implement a CST -> EST conversion using the above algorithm, then the EST loses information.  It will no longer be possible to recover the original policy syntax from the EST.

## Alternatives

We considered several variants of the extended syntax that would support arbitrary attribute names. For example, `principal has contactInfo."primary address".zip` or `principal has ["contactInfo"]["primary address"]["zip"]`.

We decided that the alternatives were less intuitive and readable. If needed, we can support arbitrary attribute names in the future without causing any further breaking changes to the EST.