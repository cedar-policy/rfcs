# Type-Aware Partial Evaluation

## Related issues and PRs

- Reference Issues: N/A
- Implementation PR(s):

## Timeline

- Started: 2024-09-16
- Accepted: TBD
- Landed: TBD
- Released: TBD

## Summary

Make the partial evaluator type-aware by letting it operate on strongly-typed expressions.

## Basic example

Consider the following Cedar policy and schema,
```
// Schema
type Rec = { X: Long, Y?: Long };
entity E1 {
    attr: Rec
};
entity E2 {
    attr: String,
};
action A appliesTo {
    principal: [E1, E2],
    resource: E1,
};
// Policy
permit(principal is E1, action == Action::"A", resource) when {
  principal.attr == resource.attr
};
```
Given a partial request where `principal` is an `unknown` annotated with type `E1` whereas `resource` refers to an entity `E1::""` with `attr` being `{ X: Some(1), Y: None }`, partial evaluation produces a *well-typed* residual expression `unknown("principal").attr == { X: Some(1), Y: None }`. Both sides of the expression have type `Rec`. Note that `principal is E1` is reduced to `true` since the type of `principal` is `E1`.

## Motivation

Lack of type awareness has restricted PE's usability in two ways. First, PE cannot further evaluate residuals without type information. For instance, PE is not able to reduce `true && unknown("B")` to `unknown("B")` even if the latter's type is a Boolean (e.g., specified in a schema). As a result, customers have to manually simplify the residual policies produced by PE, which is an error-prone process.

Second, PE does not preserve the property where well-typed policies should be partially evaluated to well-typed residuals. PE currently evaluates the above example to an ill-typed expression unknown`("principal").attr == { X: 1}` since the LHS is of type `{X: Long, Y?: String}` whereas that of RHS is just `{X: Long}`. This property is particularly important to the analyzer because otherwise it will fail to symbolically compile the residual due to this type error.

## Detailed design

There are two components of this RFC: strongly-typed residuals and semantics of type-aware PE.

### Strongly-typed residuals

We revise the existing residual language such that it's strongly-typed. The proposed residual type system only permits homogeneous sets. That is, type-aware PE will throw a type error when it encounters heterogeneous sets. Such type system also captures optional attributes of entities/records.

Modifications to the residual language include:
* Unknowns will be annotated with types
* We can express optional attribute values of records

### Semantics of type-aware PE

Type-aware PE has similar reduction semantics as the default PE except that it throws a type error should it happen and further reduce certain well-typed expressions like `true && unknown("b", Bool)`.

## Drawbacks

It limits the set of policies that can be partially evaluated.

## Alternatives

An alternative approach to implement type-aware PE is to require input policies to pass strict validation, which assigns expressions with types.

## Unresolved questions

* Residual types
* Extended residual language
* Type annotations to certain residual expressions like `unknown`s
