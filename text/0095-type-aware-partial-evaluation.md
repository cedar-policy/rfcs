# Simple Type-Aware Partial Evaluation

## Related issues and PRs

- Reference Issues: N/A
- Implementation PR(s):

## Timeline

- Started: 2025-01-30
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC proposes a simple _type-aware partial evaluator_ (TPE) for Cedar. Cedar’s current partial evaluator (CPE) is untyped and as a result, it can produce an ill-typed residual when applied to a well-typed policy and partial input. The lack of type awareness also prevents CPE from safely performing basic optimizations such as reducing `true && context.isPrivate` to `context.isPrivate`. TPE addresses these limitations with a simplified design that handles key use cases for partial evaluation such as [permission queries](#permissions-queries-with-tpe).

## Basic example

Consider the following Cedar policies:

```
// Users can view public documents.
permit (
  principal,
  action == Action::"View",
  resource
) when {
  resource.isPublic
};

// Users can view owned documents if they are mfa-authenticated.
permit (
  principal,
  action == Action::"View",
  resource
) when {
  context.hasMFA &&
  resource.owner == principal
};

// Users can delete owned documents if they are mfa-authenticated
// and on the company network.
permit (
  principal,
  action == Action::"Delete",
  resource
) when {
  context.hasMFA &&
  resource.owner == principal &&
  context.srcIP.isInRange(ip("1.1.1.0/24"))
};
```

These policies are well-typed with respect to the following schema:

```
entity User;

entity Document  = {
  "isPublic": Bool,
  "owner": User
};

action View appliesTo {
  principal: [User],
  resource: [Document],
  context: {
    "hasMFA": Bool,
  }
};

action Delete appliesTo {
  principal: [User],
  resource: [Document],
  context: {
    "hasMFA": Bool,
    "srcIP": ipaddr
  }
};
```

Suppose that we want to list all documents that Alice can view when she is MFA-authenticated.  This is an example of a permission query.

To answer the query, we invoke TPE with the above policies, schema, and the following partial input:

```
// Typed partial request, with an unknown resource of type Document.
// In this example syntax, we omit the `id` field of the `resource`
// paramater to indicate that it is unknown.
{
    "principal": { "type": "User", "id": "Alice" },
    "action":    { "type": "Action", "id": "View" },
    "resource":  { "type": "Document" },
    "context":   { "hasMFA": true }
}

// Entity data for Alice.
[
  {
    "uid": { "type": "User", "id": "Alice" },
    "attrs": { },
    "parents": [ ]
  }
]
```

TPE returns the following residuals:

```
permit (principal, action, resource)
when {
  resource.isPublic
};

permit (principal, action, resource)
when {
  resource.owner == User::"Alice"
};
```

The residuals correspond to the first and second policies, respectively, obtained by replacing the variables `principal` and `context` with their values and simplifying the resulting expressions.  The last policy (partially) evaluates to `false`, so it produces no residual---it has no effect.

The residuals say that Alice can view public resources and those she owns. If the entity data is stored in a relational database, we can retrive the relevant resources by translating the residuals to a SQL query.

## Motivation

Cedar currently provides an experimental partial evaluator, described in [this blog post](https://www.cedarpolicy.com/blog/partial-evaluation). The current partial evaluator (CPE) is untyped, which leads to two problems:
1. CPE can return ill-typed residuals.
2. CPE cannot safely simplify residuals.

To see how CPE can result in ill-typed and unsimplified residuals, consider the following policy and schema:

```
// Policy
permit(principal, action == Action::"PickUp", resource)
when {
  principal.address == resource.address
}

// Schema
type Address = {
   street: String,
   zip?: String,
};

entity User {
  address: Address
};

entity Package {
  address: Address
};

action PickUp appliesTo {
  principal: [User],
  resource: [Package],
  context: {}
};
```

The example policy is well-typed with respect to the schema.

Suppose that we want to partially evaluate the policy against a request where
* `principal` is `User::"Alice"` with the `address` of `{ "street": "Sesame Street"}`,
* `action` is `Action::"PickUp`, and
* `resource` is `unknown("pkg")`.

Given these inputs, CPE returns the following residual:

```
permit(principal, action, resource)
when {
  true &&
  { "street": "Sesame Street" } == unknown("pkg").address
};
```

This residual is ill-typed. Recall that the Cedar validator requires both sides of the `==` operator to have the same type. But in the residual condition, the left-hand side of `==` has type `{street: String}` while the right-hand side has type `Address`, which is defined to be `{street: String, zip?: String}`. Not preserving types limits the usefuless of CPE.  For example, residuals cannot be analyzed by downstream tools that expect well-typed policies, such as [entity slicing](https://github.com/cedar-policy/rfcs/pull/74) and [SMT-based verification](https://www.cedarpolicy.com/blog/whats-analyzable).

The residual is also not fully simplified, including the trivial constraint `true` that is the result of partially evaluating the scope constraint `action == Action::"PickUp"`. Ideally, `true && expr` should be simplified to just `expr`, but CPE cannot perform this simplification safely. The reason is that CPE lacks type information and cannot guarantee that `expr` will always evaluate to a boolean value. If `expr` could potentially evaluate to a non-boolean value, then simplifying `true && expr` to `expr` would change the error behavior of the original policy. To preserve the original policy's semantics, including potential type errors, CPE must conservatively leave expressions like `true && expr` unsimplified. This limitation leads to complex residuals that are harder to apply for solving use cases like permission queries.

TPE addresses these limitations by preserving type information during partial evaluation. When applied to our example, TPE produces the following _typed_ residual:

```
permit(principal, action, resource)
when {
  { "street": "Sesame Street" } : Address == resource.address
};
```

Here, we are using pseudo-syntax `expr : Type` to show the type annotations generated by TPE. With this explicit type annotation, the residual is well-typed. TPE also knows that equality expressions are boolean, so it can safely simplify away the `true` constraint obtained by evaluating the scope.

## Detailed design

TPE departs from CPE by exposing a much simpler interface for specifying unknowns. Instead of allowing named unknown values to appear anywhere in the request and entities, the TPE interface lets users mark specific parts of the request and entities as unknown while providing concrete values for the rest. This focused interface makes it straightforward to handle key use cases directly. Other more specialized applications of partial evaluation can still be realized on top of TPE through a layer of indirection, which can be automated in the future if needed. This section describes the TPE interface, shows how it supports common use cases natively and enables advanced scenarios indirectly, and discusses strategies for implementing the type-aware partial evaluator.

### TPE interface

The TPE interface aims to strike a balance between simplicity and flexibility for common partial evaluation use cases. It exposes two main concepts---partial requests and partial entities---to specify what parts of input should be treated as unknown. The interface is designed to handle permissions queries directly, while still enabling more advanced scenarios through an indirection layer.

#### Partial requests

TPE allows the value of the `principal`, `resource`, and `context` variables to be unknown; `action` must be specified concretely. Partial requests must declare the types of unknown `principal` and `resource` values, and these types must be consistent with the action's schema. The type of `context` doesn't need to be declared because it is uniquely determined by the schema.

In pseudocode, we describe typed partial requests as follows:

```
structure PartialRequest where
  principal : PartialEntityUID
  action : EntityUID                 -- Action is always known.
  resource : PartialEntityUID
  context : Option (Map Attr Value)  -- Unknown context is omitted.

structure PartialEntityUID where
  ty : EntityType                    -- Entity type is always known,
  id : Option String                 -- but entity id may not be.
```

In JSON, we describe a partial request as an object with the optional `context` field and required `principal`, `action`, and `resource` fields. If present, the `context` value is specified according to the [Cedar JSON format](https://docs.cedarpolicy.com/auth/entities-syntax.html#context). If absent, it's treated as unknown and its type is inferred from the `action` and schema. The `principal` and `resource` fields are [entity objects](https://docs.cedarpolicy.com/auth/entities-syntax.html#uid) that can omit the `id` field to specify that the entity is unknown.

For example, this partial request for our [basic schema](#basic-example) makes both the `context` and `resource` unknown:

```
{
  "principal": { "type": "User", "id": "Alice" },
  "action":    { "type": "Action", "id": "View" },
  "resource":  { "type": "Document" }
}
```

The key difference between this interface and CPE is that `context` must be either fully known or fully unknown. Partially specified `context` is not directly supported (though it can be expressed indirectly, as we'll see later). This design choice is consistent with classic partial evaluation, where input variables are either unknown or fully specified, and it simplifies implementation and formal modeling of TPE.

#### Partial entities

TPE specifies partial entities as a map from entity UIDs to partial entity data, consisting of unknown or fully specified attributes, ancestors, and tags. Unknown parts of the data are simply omitted, and their type is determined from the schema.

In pseudocode, we describe partial entities as follows:

```
abbrev PartialEntities := Map EntityUID PartialEntityData

structure PartialEntityData where
  attrs : Option (Map Attr Value)    -- Attributes fully known or fully unknown.
  ancestors : Option (Set EntityUID) -- Ancestors fully known or fully unknown.
  tags : Option (Map String Value)   -- Tags are fully known or fully unknown.
```

In JSON, we describe partial entities as a list of JSON objects whose known parts are specified using the [Cedar JSON format for entities](https://docs.cedarpolicy.com/auth/entities-syntax.html#entities).

For example, this partial entities list for our [basic schema](#basic-example) specifies the ancestors for the entity `Document::"Manual"` and leaves the attributes unknown:

```
[
  {
    "uid": { "type": "Document", "id": "Manual" },
    "parents": [ ]
  }
]
```

There are two key differences between the TPE and CPE interfaces for partial entities. First, TPE allows mixing known and unknown parts of entity data; for example, an entity can have known attributes but unknown ancestors. This is important for applications that implement role or relation-based access control using Cedar's hierarchy, where entities typically have a few simple attributes but potentially large ancestor sets. In such cases, TPE can attempt to authorize requests using just the attributes, avoiding the cost of loading the full ancestor set. Second, entity attributes must be either unknown or fully specified. TPE doesn't support partially known attributes, following the same design principle as with `context` data.

### Permissions queries with TPE

TPE provides native support for basic permission queries:
1. List all principals that can access a given resource.
2. List all resources that a given principal can access.
3. List all actions that a given principal can perform on a given resource.

We've already seen an [example](#basic-example) of the resource listing query (2), which leaves the `resource` variable unknown and fixes the values of all other variables.  The principal listing query (1) is handled analogously: we leave the `principal` unspecified and fix the values of the other variables.

In the action listing query, the `action` variable is unknown and other variables are fixed. We solve this query by iterating over all actions in the schema that apply to the given `principal` and `resource` type, and (partially) authorizing the policies against the resulting request to determine which actions are allowed.

Some applications generalize permission queries by leaving the `context` unspecified in addition to one of the other three variables.  In that case, the result of the query represents accesses that _may_ be allowed in _some_ context, rather than accesses that are definitely allowed in a specific context.

For example, consider partially evaluating our [basic example policies](#basic-example) against a request where both the `resource` and `context` are unknown:

```
{
  "principal": { "type": "User", "id": "Alice" },
  "action":    { "type": "Action", "id": "View" },
  "resource":  { "type": "Document" }
}
```

TPE returns the following residuals:

```
permit (principal, action, resource)
when {
  resource.isPublic
};

permit (principal, action, resource)
when {
  context.hasMFA &&
  resource.owner == User::"Alice"
};
```

The second residual now includes a `context` constraint and says that Alice can access resources she owns when she's authenticated.

Unlike our [previous example](#basic-example) where residuals could be translated directly to SQL, we need a different approach to compute the list of resources that Alice _may_ be able to access. The basic solution is to iterate over all resources, partially re-authorize the residuals with the data for each resource, and include resources where the result is either Allow or Undetermined (i.e., produces another residual). This full scan can be optimized by safely limiting the iteration to relevant subsets of resources---in this case, we can check resources owned by Alice or those marked as public.

### Advanced scenarios with TPE

While TPE doesn't directly support partially unknown attributes, we can achieve the same advanced functionality as CPE by representing unknown values as references to special entity types. This section demonstrates this pattern using contingent authorization as an example.

#### Contingent authorization with partially unknown `context` attributes

Consider again our [basic policies and schema](#basic-example). Suppose that we want to find out if Alice can delete a SuperSecret document she owns when she has been authenticated but her source IP address is unknown.

We can achieve this straightforwardly with CPE by evaluating the basic policies against a request where:
* The `principal` is `User::"Alice"` and Alice's data is fully specified.
* The `action` is `Action::"delete"`.
* The `resource` is `Document::"SuperSecret"` with the `owner` attribute set to `User::"Alice"`.
* The `context` is partially given so that `context.hasMFA` is true and `context.srcIP` is unknown.

Given these inputs, CPE returns the following residual:

```
permit (principal, action, resource)
when {
  true &&
  true &&
  true &&
  context.srcIP.isInRange(ip("1.1.1.0/24"))
};
```

The residual says that Alice can perform the delete action if her source IP address is in the given range. In contingent authorization, an application would examine this residual, take further steps to determine Alice's IP address, and re-authorize against the residual to reach a concrete authorization decision.

#### Contingent authorization with entity-based unknown values

We can reproduce this functionality with TPE by introducing a level of indirection for the values of attributes that may be unknown.

First, we introduce a new entity type to represent unknown IP addresses:

```
entity UnknownIP {
  value: ipaddr
};
```

Next, we change the type of `context` for the `Delete` action to use the new entity type for `srcIP`:

```
action Delete appliesTo {
  principal: [User],
  resource: [Document],
  context: {
    "hasMFA": Bool,
    "srcIP": UnknownIP
  }
};
```

Finally, we change the relevant polices to use the new `context` definition as follows:

```
permit (
  principal,
  action == Action::"Delete",
  resource
) when {
  context.hasMFA &&
  resource.owner == principal &&
  context.srcIP.value.isInRange(ip("1.1.1.0/24"))
};
```

Now, we call TPE with the following concrete request and partial entity store:

```
// Concrete request, where UnknownIP::"AliceIP" is a fresh entity UID.
{
    "principal": { "type": "User", "id": "Alice" },
    "action":    { "type": "Action", "id": "Delete" },
    "resource":  { "type": "Document", "id": "SuperSecret" },
    "context":   {
      "hasMFA": true,
      "srcIP": { "type": "UnknownIP", "id": "AliceIP" }
    }
}

// Entity data for Alice and SuperSecret document.
[
  {
    "uid": { "type": "User", "id": "Alice" },
    "attrs": { },
    "parents": [ ]
  },
  {
    "uid": { "type": "Document", "id": "SuperSecret" },
    "attrs": {
      "isPublic": false,
      "owner"   : { "type": "User", "id": "Alice" }
    },
    "parents": [ ]
  }
]
```

TPE returns the following residual that shows the value of Alice's source IP is needed to reach a decision:

```
permit (principal, action, resource)
when {
  UnknownIP:"AliceIP".value.isInRange(ip("1.1.1.0/24"))
};
```

This approach to contingent authorization generalizes to arbitrary types and attributes in the obvious way.

#### Future improvements

Using TPE for contingent authorization requires transforming policies and schema to insert placeholders. This transformation is mechanical and could be automated in the future. We could provide a layer that:
1. Accepts partial evaluation requests in the CPE style (with arbitrary unknowns).
2. Automatically transforms them into equivalent TPE problems.
3. Translates the TPE residuals back to residuals for the original policies.

### Implementing TPE

TPE can be implemented as a pass over the type-annotated AST produced by the Cedar typechecker. The implementation follows these steps:

1. Given a typed partial request and schema, construct the corresponding typing environment.
2. Run the typechecker on each policy to obtain the type-annotated AST.
3. Apply TPE to each of the ASTs.

The TPE algorithm itself implements classic partial evaluation (constant folding) with respect to the underlying typed concrete semantics. Because TPE operates on typed ASTs and inputs, it can:

* Safely perform optimizations like boolean simplification.
* Guarantee that residuals are well-typed.
* Preserve the semantics of the original policies.

## Drawbacks

There are four main drawbacks to this RFC:

* Building TPE will require significant engineering effort. The implementation of CPE is currently embedded in the concrete evaluator, so separating it out and building TPE from scratch will involve substantial implementation work, in addition to formal modeling and proofs.

* TPE works only on typed policies, removing the ability to use partial evaluation on untyped policies. This is a breaking change for users who currently rely on CPE for untyped policies.

* TPE exposes a different interface for specifying unknowns than CPE. This is another breaking change for existing CPE users.

* Porting typed policies from CPE to TPE may require [policy and schema transformations](#contingent-authorization-with-partially-unknown-context-attributes). While this can be mitigated by introducing an [automated transformation layer](#future-improvements), the initial migration could be disruptive for some users.

## Alternatives

We considered two alternatives to TPE, each adding different levels of type awareness to CPE:
1. A lightweight approach that adds partial type awareness to CPE's algorithm.
2. A comprehensive approach that adds full type awareness to both CPE's algorithm and interface.

### Adding partial type-awareness to CPE

A lightweight approach would modify CPE's algorithm to take advantage of operator-specific type information. For example, CPE could safely drop `true` from the expression `true && resource.owner == principal` by tracking that the equality operator always produces boolean results (or errors).

This approach would be easier to implement than TPE while enabling more optimizations than CPE. But like CPE, it could still return ill-typed residuals, and it would miss optimizations that require full type awareness. For example, `true && context.isPrivate` cannot be simplified without a schema because `context.isPrivate` might not be boolean.


### Adding full type-awareness to CPE

A more comprehensive approach is to build on CPE's existing interface for specifying unknowns, while adding full type awareness to the underlying algorithm. Like TPE, this approach would require policies and unknowns to be typed, so users would lose the ability to partially evaluate untyped policies.

The key advantage would be a smoother transition for current CPE users, especially those with advanced use cases not directly supported by TPE. The CPE-style interface would remain more flexible, allowing unknowns to be specified anywhere in the request and entity data.

However, this approach would require significantly more complex implementation, models, and proofs to support advanced functionality that most users may not need. If we do find that a CPE-style interface is needed in the future, we can implement it as a [transformation layer](#future-improvements) on top of TPE.

