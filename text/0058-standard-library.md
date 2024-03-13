# Cedar Standard Library

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2024-03-12

## Summary

Create a Cedar Standard Library of type declarations that are likely to be
useful to many Cedar users, and are distributed along with Cedar.

Allow users to "extend" the type declarations in the standard library by adding
more parent types and/or more attributes.

This RFC includes the concept/infrastructure for the Cedar Standard Library, and
also concretely proposes one type declaration to be included in it: `OIDC::User`.
Discussion of other type declarations to add to the Cedar Standard Library is
left out of scope for this RFC.

## Basic example

```
type User = __cedar::OIDC::User;
```
or
```
entity Group { myAttribute: String };
entity User extends __cedar::OIDC::User in [Group] { emailOptOut: Boolean };
```

## Motivation

Some data sources are common across many applications and useful to many Cedar
users.
The running (motivating) example for this RFC is identity providers (IdPs) which
comply with the OpenID Connect standard (OIDC).
The OIDC standard includes a list of attributes that exist on a user type; this
is naturally declared as a Cedar entity type.

By including declarations for types like this in a standard library, we
accomplish three goals:
1. Saving each Cedar user the effort of writing the declaration themselves.
  This facilitates code reuse in schemas, and makes it easier to get started
  with Cedar.
2. Ensuring the community's alignment on the "best" way to declare each type.
  For instance, should OIDC `updatedAt` be expressed as a `String`, as a `Long`
  (eg Unix timestamp), or as a record with multiple components?
  This allows Cedar to encourage best practices.
3. Facilitating code reuse for Cedar authorization calls, not just schemas.
  When everyone shares a common definition of `OIDC::User`, the community could
  conceivably converge on a reusable library function for, e.g., converting an
  OIDC token into Cedar entity data.
  This would further make it easier to get started with Cedar.
  (Note that this RFC does not propose Cedar writing or maintaining library
  functions like this, it only points out that the community could converge on
  library functions like this.
  This RFC only proposes a standard library for schema declarations.)

## Detailed design

The Cedar standard library declarations will all live in the namespace `__cedar`
(previously reserved as part of [RFC 24]; see also [RFC 52]).

Cedar standard library declarations will be automatically available for use in
every Cedar schema. Under the hood, this means they are automatically prepended
to every Cedar schema, much like a standard library or "prelude" in other
languages. For ease of maintainability, they should probably exist in the Cedar
repo as literal Cedar schema files, which are loaded and parsed either at Cedar
compile-time, or at application startup with `lazy_static`.

This RFC also includes the new keyword `extends`, allowing a schema to extend a
previously existing entity declaration by adding more parent types and/or more
attributes.
The syntax for this is (informally) as follows:
```
entity MyEntityType extends BaseEntityType; // allowed, functionally equivalent to `type MyEntityType = BaseEntityType;`

entity MyEntityType extends BaseEntityType in [MyGroupType]; // `MyEntityType` has all the attributes and parent types of `BaseEntityType`, and also can be a member of `MyGroupType`

entity MyEntityType extends BaseEntityType { emailOptOut: Boolean }; // `MyEntityType` has all the attributes and parent types of `BaseEntityType`, and also has an attribute `emailOptOut` of type `Boolean`

entity MyEntityType extends BaseEntityType in [MyGroupType] { emailOptOut: Boolean }; // combining the above examples
```

The base type may be an entity type, or may be a common type that aliases an
entity type.
As a consequence of this rule, chains of `extends` are allowed: you can write
`entity B extends A` and later `entity C extends B`.

To avoid cycles, the base type for `extends` must be a previously declared type
(as in, declared farther up in the schema file).
For this purpose, standard library declarations are considered to appear before
line 1 of the schema file.
If the base type is defined in a different schema file, that other schema file
must be loaded first (e.g., must appear earlier in the iterator in [`Schema::from_schema_fragments()`]).

## Drawbacks

1. Cedar commits to maintaining all of the definitions in the Cedar standard
library, which is a (hopefully small) maintenance burden. We can weigh this
burden against the utility for each individual type declaration proposed for the
Cedar standard library. This RFC only proposes the idea of the standard library,
and a single definition `OIDC::User`.
2. If a single declaration for `OIDC::User` (or other type) can't be agreed upon
by the community, it may be difficult for Cedar to decide which definition
should be in the standard library. Cedar may have to come up with best practices
or tenets for resolving such disputes. We also could theoretically end up with a
situation where part of the community uses the standard definition and another
part uses a competing definition, which may or may not be better than how things
would develop organically without this RFC.
3. Users may incorrectly assume that `extends` has some kind of impact at
runtime -- for instance that concrete values of `MyEntityType` inherit attribute
values from a concrete value of `BaseEntityType` somehow.
Hopefully we can address this with clear documentation.
There's also nothing preventing us from providing API helpers that allow
extending concrete `Entity` objects of a base type corresponding with a schema
`extends` declaration (although this is not proposed in this RFC).
4. Users may incorrectly assume that `extends` provides subtyping, while this
RFC does not propose that it provides subtyping.
For instance, users may assume that an action with principal type
`BaseEntityType` could also be used with principal type `MyEntityType` which
`extends` `BaseEntityType`; but this is not the case in the current proposal.
It's also possible that the keyword being named `extends` in particular might
make this problem worse due to existing associations with object-oriented
inheritance; see Alternative H.

This is not a breaking change for any existing Cedar users.
All existing valid Cedar schemas remain valid.

## Alternatives

### Alternative A: Distribute standard library as ordinary schema files

Instead of having the declarations of types like `OIDC::User` implicitly
available as part of Cedar, Cedar could just distribute ordinary schema files
with these declarations (in the `cedar-policy/cedar` repo or elsewhere).
Users would have to provide this schema file in addition to the rest of their
schema. (Note that Cedar already supports schemas spread over multiple files.)

Users could still use this RFC's `extends` mechanism to extend the standard
declarations, but they would probably be tempted to just modify the distributed
schema files directly instead.

### Alternative B: Only allow extending the standard-library entity declarations

As written, this RFC allows `extends` with any entity declarations, for
consistency and least-surprise.
We could instead only allow `extends` to be used with specifically the
standard-library types.
This would still leave the door open to going back to the current proposal in
the future, without a breaking change.

However, I don't see any good reason to restrict `extends` at this time.
Allowing `extends` to work with all types might facilitate third-party
ecosystems of standard declarations (distributed as schema files, a la
Alternative A) which folks could use instead of or in addition to the Cedar
standard library.
Some folks might also find it locally useful within their own schemas.

### Alternative C: Explicit declaration to use/import the standard library

This RFC doesn't currently propose require any kind of `use` or `import`
statement in order to have access to the Cedar standard library.
Rather, the Cedar standard library is always implicitly available in the
`__cedar` namespace.
An alternate design would require an explicit `use` or `import` statement
in order to make these declarations available / active.
One reason to do this would be in anticipation of a possible future where
we allow `use` or `import` with libraries other than the standard library
(and other than libraries provided as ordinary schema files, a la Alternative
A), or if we are afraid of the performance cost of implicitly including the
standard library in every schema.

However, I don't see a good reason to require an explicit `use` or `import`
statement for the standard library.
Even if a future RFC introduces a `use` or `import` statement, as envisioned
above, I think it would still be reasonable to have the standard library
available automatically, without such a statement.

### Alternative D: Explicit mechanism to use/open a namespace

This RFC doesn't currently propose any (new) mechanism to use/open a namespace.
One might think it would be desirable to have something like
`use __cedar::OIDC::User;` or `open __cedar::OIDC::User;` to allow referring to
the standard library type `__cedar::OIDC::User` as just `User` in the schema.
But we already do have such a mechanism, common types: users can write
```
type User = __cedar::OIDC::User;
```
and then refer to the OIDC User type as just `User` in their schema.
This is arguably more explicit and clearer, and also avoids introducing a
redundant mechanism for something that is already possible using existing
syntax.

This is an optional added feature; nothing in this RFC prevents us from
introducing a mechanism like this in the future.

### Alternative E: Implicitly search the `__cedar` namespace

Currently, when a user writes a type `A`, the schema parser searches the current
active namespace for a declaration `A`, then if not found, it searches the empty
namespace for a declaration `A`.
We could add a third step to this chain, that if `A` is not found in the empty
namespace either, we could search the `__cedar` namespace for a declaration `A`.
The end result of this would be that you could write `OIDC::User` instead of
`__cedar::OIDC::User`, in any schema that didn't itself define an `OIDC`
namespace.
The `__cedar` prefix would only be necessary for disambiguation, which matches
how it is used in [RFC 24].

This is an optional added feature; nothing in this RFC prevents us from
introducing this search behavior in the future.

TODO: does today's resolution algorithm do the above for namespaces `A`, or only
for types `A`?
My reading of [RFC 24] is that it only does this for unqualified types `A`;
when the user writes `A::B::C`, and suppose the active namespace is `NS`, that
only refers to the type `A::B::C`, and not `NS::A::B::C` (even if `NS::A::B::C`
exists).
If my reading is correct, we also would want to extend this search behavior to
namespaces, so that in the above case, in addition to looking for `A::B::C` and
`NS::A::B::C` (probably in that order, for backwards compatibility), we would
then look for `__cedar::A::B::C` if neither of the first two were found.

### Alternative F: Envisioning multiple inheritance

This RFC doesn't currently propose to allow multiple inheritance (one type
extending multiple different types at once).
Multiple inheritance would be straightforward in simple cases (just take the union
of all attributes and parent types), but tricky in some edge cases (what happens
if two base types declare the same attribute but with different types?).

Multiple inheritance is an optional added feature; nothing in this RFC prevents
us from introducing it in the future.
However, in anticipation of a possible multiple-inheritance feature, we could
require brackets around the `extends` list, like so:
```
entity MyEntityType extends [BaseEntityType] in ...
```
This would allow us to easily support multiple base entity types in the future,
syntactically.

However, even if we take this RFC as-is today, it would be perfectly reasonable
to introduce multiple inheritance in the future and keep this RFC's syntax valid
for single inheritance.
The brackets would be optional for single inheritance and required for multiple
inheritance.

### Alternative G: Other ways to handle inheritance cycles

This RFC proposes that we avoid inheritance cycles by requiring that the base
type for `extends` must be a previously declared type (as in, declared farther
up in the schema file).
This would be the first schema feature for which the order of declarations in
the schema file matters (as well as the order of schema files in
[`Schema::from_schema_fragments()`]).
An alternate design would be to simply disallow cycles, without introducing an
order restriction.
That is, if there is an inheritance cycle, the schema is illegal, but if there
is not, the schema is allowed.

This is strictly more permissive than the RFC's main proposal, so nothing
prevents us from moving from the RFC's main proposal to this alternative in the
future.

I'm unclear which of these rules is easier to implement in practice, or which
results in clearer errors for users.

### Alternative H: Bikeshedding the `extends` syntax

This RFC proposes that `extends` must appear before `in` and attributes:
```
entity MyEntityType extends A in [B];
```
We could instead require `extends` to appear _after_ `in` but before attributes:
```
entity MyEntityType in [B] extends A;
```
Or we could allow both.

We could also consider some keyword other than `extends`, such as:
* `expands`
* `copies`
* `elaborates`
* `augments`

or some syntax other than a keyword, such as:
```
entity MyEntityType:A in [B];
```

[RFC 24]: https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md
[RFC 52]: https://github.com/cedar-policy/rfcs/pull/52
[`Schema::from_schema_fragments()`]: https://docs.rs/cedar-policy/latest/cedar_policy/struct.Schema.html#method.from_schema_fragments
