# Support to treat records as maps

## Related issues and PRs

- Reference Issues: [#305](https://github.com/cedar-policy/cedar/issues/305)
- Implementation PR(s): (leave this empty)

## Timeline

- Start Date: 2023-10-02
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

Cedar records are fundamentally static. They force a user to specifically enumerate all possible record attributes in the schema, and they require an attribute to be mentioned as a literal when used in a policy.

This RFC proposes to support a limited form of maps in Cedar, adding greater dynamism, by slightly extending current support for records. In the extension, not all attribute names need to be known in advance, and can be taken from run-time data. There are two changes:
- Add a new type `map<T>` which represents records that optionally have _any_ attribute, where if an attribute is present it will have type `T`.
- Extend the grammar so that `X has Y` allows `Y` to be a _member expression_ like `principal.foo.bar`, which will evaluate to the name of the attribute, rather than just an identifier or string literal. Likewise extend the grammar so that in `X.bar[Y]` we allow `Y` to be a member expression, not just a string literal.

## Motivating examples

#### Tags

As a first example, you can use maps to implement entity _tags_, which are basically a map (from string keys) to string values. In particular, suppose that `principal.tags` has type `map<String>`, then you can write `principal.tags has "priority" && principal.tags["priority"] == "green"`. Just writing `principal.tags["priority"] == "green"` without a preceding `has` check would result in a validation error.

`map`-based tags are useful when wanting to compare tags on different entities, e.g., 
```
when { resource.tags["project"] == principal.tags["project"] } 
```
or 
```
when { resource.tags["projects"].contains(principal.tags["project"])}
```
This would be difficult to do when trying to encode tags as sets. `map`-based tags are most valuable when you don't know the tag names when writing policies, else you could extend the schema to name the tags explicitly. See the [Workarounds](#workarounds) section below for discussion.

#### Timeboxes

A second example is the extension of [`TinyTodo`](https://github.com/cedar-policy/cedar-examples/tree/main/tinytodo) to include `TimeBox`es, which are fixed periods during which a principal is granted read-only access to a todo `List`. [Right now](https://github.com/cedar-policy/cedar-examples/blob/features/timebox/tinytodo/src/timebox.rs), this feature is implemented by generating a fresh policy whenever timed access is requested. This approach is unsatisfying because part of the application's authorization model thus lives in the application code, rather than in the policy file (i.e., the part that is generating the `TimeBox`-based policies). It also results in stale policies, since they remain in the store even after the timebox range has expired.

With `map` types, `TimeBox`es for individual `User`s can be maintained separately from the policies. Each `List` could have a `timeboxes` map from a `User`'s name to a time range that the `List` is readable.
```
permit(
    principal,
    action == Action::"GetList",
    resource in Application::"TinyTodo"
) when {
    resource.timeboxes has principal.name &&
    resource.timeboxes[principal.name].start >= context.now &&
    resource.timeboxes[principal.name].end < context.now
}
```
This approach adds just the above policy to the store at the outset, and it applies to all users and lists. The application manages timebox ranges -- adding and updating them in the relevant `List` entity -- the same as it was doing in the old approach.

## Detailed design

The addition of `map`-typed objects will result in extensions to the Cedar grammar and evaluator, the schema, and the validator.

### Grammar and evaluator

We change the [grammar for `has`](https://docs.cedarpolicy.com/policies/syntax-grammar.html#relation) so that the given attribute can be a [`Member`](https://docs.cedarpolicy.com/policies/syntax-grammar.html#member), rather than an `IDENT`:
```
Relation ::= ... | Add 'has' (Member | STR)
```
Here, if `Member` is just an identifier like `foo` then it is interpreted as an attribute name, as now. Otherwise it is treated as an expression that should be evaluated to a string, which is the name of the attribute.

For completeness here is the current `Member` grammar:
```
Member ::= Primary {Access}
Access ::= '.' IDENT ['(' [ExprList] ')'] | '[' STR ']'
Primary ::= LITERAL 
           | VAR 
           | Entity 
           | ExtFun '(' [ExprList] ')' 
           | '(' Expr ')' 
           | '[' [ExprList] ']' 
           | '{' [RecInits] '}'
```

We also change [attribute access](https://docs.cedarpolicy.com/policies/syntax-grammar.html#access) to allow `Member` to appear within brackets. The semantics is that we evaluate `Member` to a string, and then use that string to access the attribute.
```
Access ::= '.' IDENT ['(' [ExprList] ')'] | '[' STR ']' | '[' Member ']'
```
It may be that `Member` is a bit too expressive. We may consider limiting it to simpler expressions, e.g., `foo.bar.baz`, and not `User::"foo".bar.baz` or `{ foo: "bar" }.foo`. We will reconsider this point below.

### Entities

The JSON entity format does not change to support maps: We use the same format as with `Record` objects, where the values of all listed attributes should have the same type.

### Schema

We extend schemas to support a new type `map` which is parameterized by the type of its values. In the JSON format of Cedar schema, the type of a map to strings would be written
```
    "type": "Map",
    "element": {
        "type": "String"
    }
```
In the proposed [custom schema syntax](https://github.com/cedar-policy/rfcs/pull/24), we would add the type `map<T>` where `T` is any type (e.g., `map<String>` or `map<map<Long>>`), analogous to the existing type `set<T>`.

### Validation

We must extend the way the validator handles records, and then generalize that handling to support `map` types.

#### Capabilities

The validator must support the expanded form of `has` and attribute access via `[]` for records and entities. 

The validator tracks _capabilities_ while typechecking a policy, which represent the attribute-accessing expressions that are sure to succeed. If `principal` has type `User` and `User` has an optional `Boolean` attribute `sudo`, then the expression `principal.sudo` only validates if `principal.sudo` is present in the _current capability set_. Capabilities are added to that set by a preceding expression of the form `principal has sudo`, e.g., as in `principal has sudo && principal.sudo`.

The allowed form of a capability must be generalized to support dynamically contructed attribute names. This should be straightforward. When the validator seems something like `principal has resource.name` then this would generate the capability `principal[resource.name]` that would allow a follow-on expression `principal[resource.name]` to validate. 

In addition, it's now possible that an attribute-constructing expression could access a bogus attribute, so those expressions must be validated as well. E.g., when validating `principal has resource.name` or `principal[resource.name]`, the validator must confirm that `resource` indeed has a `name` attribute.

#### Expressions of `map` type

The validator can handle `map<T>` types similarly to how it handles records with optional attributes. 

Normally when the validator sees an expression _e_ `has` _f_, it will check that the type _T_ of _e_ is either a record or entity, and if so, it will check that _T_ has _f_ as an attribute. If not, the expression is given type `False`. If _f_ is unconditionally present, the expression is given type `True`. If _f_ is optional, the expression is given type `Boolean`.

This validation logic is extended so that that if _e_ has type `map<`_U_`>` for some type _U_, the expression _e_ `has` _f_ will be given type `Boolean`, and _e_`[`_f_`]` is added to the current capability set. Similarly, the expression _e_`[`_f_`]` will only validate if _e_`[`_f_`]` is in the current capability set. If it does validate, the expression is given type _U_ (the type parameter in the `map` type).

#### Subtyping

For permissive validation, which supports width subtyping, we can add a subtyping rule
```
{ f1*: T, ..., fn*: T } <: map<T>
```
Here, we write `*` to indicate the "optionality" of an attribute, where the optionality can be either `?`, meaning the attribute is optional, or the optionality can be non-present, meaning the attribute is required.

Thus, this rule says that any record whose attributes, whether optional or not, all have the same type `T` can be given a `map<T>` type.

But we must take care: This rule is only sound if the record type is not _open_ -- i.e., it must enumerate _all_ of the fields of the object it represents. Otherwise, this rule could be used as follows:
```
{ f1: Long, f2: String } <:   // by width subtyping
{ f1: Long }             <:   // by bogus application of above rule
map<Long>
```
Suppose `principal.tags` contains value `{ f1: 3, f2: "foo" }`. The derivation above would permit `principal.tags` to be given type `map<Long>`. As a result, the expression `principal.tags has f2 && principal.tags.f2 < 5` would validate, but then error when evaluated.

#### Literals

A literal such as `{ tag1: "foo", tag2: "bar" }` should be given type `{ tag1: String, tag2: String }`.

With permissive validation, there is no loss in flexibility. The literal above can be treated as having type `map<String>`, thanks to subtyping. Suppose that `principal.map` has type `map<String>` and `principal.rec` has type `{ tag1: String }`. Then we can permissively validate expressions such as 
```
if principal.isAdmin then principal.map else { tag1: "foo", tag2: "bar" }
```
(will have type `map<String>`), and 
```
if principal.isAdmin then principal.rec else { tag1: "foo", tag2: "bar" }
```
(will have type `{ tag1: String }`).

Strict validation does not support width subtyping. This means there is no way to create `map` literals in a policy, only record literals. For strictly valid policies, maps can only exist in entity or record attributes passed in to the Cedar evaluator. We might consider extending the language syntax to include casts, to allow constructing maps directly, e.g., `(map<String>){ tag1: "foo", tag2: "bar" }`.

## Alternatives

We could avoid adding maps entirely, and work around their absence. A simpler form of map is not worth adding, but a more general form might be.

### Workarounds

#### Records wtih optional attributes

A `map` is only needed when the keys are truly unknown statically. If the list of keys is known, one can also create a record type that enumerates every key as optional. In sum: Every time you create a policy that writes a map key as a literal, the validator will complain if that key is not in the schema. Just add the key to the schema, and the new policy will validate, along with the old ones. Changing the schema to constantly extend the list of valid keys may be tedious, however. If policies are being constructed on the fly, e.g., by a service's users, a schema update on each policy addition may not be feasible.

#### Sets of records as key-value pairs

The lack of a `map` type can sometimes be worked around using a `set` of records which contain key-value pairs. For example, to encode tags and you only care about whether a tag exists (and the value it maps to) then `set<{key:String, value:String}` is sufficient. With this type you can write
```
permit(...) 
when {
    resource.tags.contains(
        {"key": "color", "value": "green"})
}
when {
    resource.tags.containsAny([
        {"key": "size", "value": "small"},
        {"key": "size", "value": "large"},
    ])
};
```
But this approach is insufficient to model a policy that says "the `project` tag for `principal` is the same as the `project` tag for the `resource`", which we could write with maps as `project.tags["project"] == resource.tags["project"]`.

### Non-dynamic attributes

We considered adding a `map` type, but not generalizing the syntax for `has` and for attribute projection to allow member expressions; i.e., we would still require them to be string literals or identifiers. Doing so does not add any expressive power, as it means that you can use records and enumerate all of the possible keys as optional attributes. However, it might still be useful for applications that are creating policies on the fly as part of the business logic, in which case updating the schema may be impractical.

### Combined records/maps

One could implement `map` as part of a generalized record type. In particular, you could imagine a type such as `{ foo: Long, bar: User, *: String }`, which states there are two required attributes `foo` and `bar`, and that there are arbitrarily more additional attributes, all of whom (if present) have type `String`. Thus in the degenerate case what we have proposed as `map<T>` is equivalent in the above notation to `{ *: T }`.

This generalization would result in a more general subtyping rule, and an additional subtyping rule that would permit collapsing optional types into the additional attributes, e.g.,
```
{ foo?: String, bar: Long, *: String } <: { bar: Long, *: String }
```
It's a two-way door to not add this generalization now. If we add `map<T>` now and add the generalization later, then `map<T>` can remain as a synonym for type `{ *: T }`.

### Map literals

As mentioned above, strict validation provides no way to define a map literal in a policy. We could add casts to support this; they would also be useful for other values that can have multiple types, e.g., the empty set `[]`.

## Drawbacks and Unresolved questions

It may be that the utility of a `map` is sufficiently limited that it's not worth adding. Adding it now might complicate the addition of a better feature later. I'd be more comfortable if we know of more use-cases where this would help.

The main question I have is how the dynamic construction of attribute names would affect a logical encoding of policies for the purposes of analysis.

A related question is how dynamic to make attribute construction. In the proposal, we suggest using the `Member` non-terminal to express this, but we may need to simplify that.