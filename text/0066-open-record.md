# The default attribute type for open records

## Related issues and PRs

- Reference Issues: [#305](https://github.com/cedar-policy/cedar/issues/305)
- Supercedes [RFC 27](https://github.com/cedar-policy/rfcs/pull/27)
- Implementation PR(s): (leave this empty)

## Timeline

- Start Date: 2024-05-22
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

The Cedar validator requires a user to enumerate all possible record and entity attributes, both names and types, in the schema. This is limiting when you'd like to treat a record like a map, i.e., there are attributes whose names are not known in advance, but whose value types are.

This RFC proposes to extend the validator to support _open records_. An open record type extends a normal record type with a _default attribute type_. Policies can check for the presence of any attribute in an open record using `has`, and if present they can access it assuming its value has the default attribute type.

## Motivating example: Tags as Attribute-based Maps

As a key motivating example, you can use open records to implement _tags_, which are basically a map from `String` keys to values.

For example, suppose that `principal.tags` has type `{ } default String`, meaning it is a record with default attribute type `String`. Then you can write `principal.tags has "priority" && principal.tags["priority"] == "green"`. Just writing `principal.tags["priority"] == "green"` without a preceding `has` check would result in a validation error.

Compare this approach to another way of implementing tags, as sets of key-value pairs. For example, `principal.tags` could have type `Set<{ key:String, value:String }>` and a tag check would involve an expression like `principal.tags.contains({ key: "priority", value: "green" })`. Attribute-based tags are useful when you want to compare tags on different entities, as in 
`resource.tags["project"] == principal.tags["project"]` 
or 
`resource.tags["projects"].contains(principal.tags["project"])` (when tags have type `{ } default Set<String>`, so tags' values are sets of strings). Doing this is not possible when encoding tags as sets.

Compared to the status quo, open records allow you to implement attribute-based tags without changing the schema each time you add a tag. See the [Workarounds](#workarounds) section below for discussion.

## Detailed design

Supporting open records will requre extensions to the Cedar schema format and the validator. Neither the JSON format for entities nor the JSON or natural syntax for policies needs to change to support open record objects.

### Schema

We extend schemas to support a new _default attribute type_ on both records and entities. Here's the natural syntax extension:
```
Entity     := 'entity' Idents ['in' EntOrTyps] [['='] RecType] ';'
RecType    := '{' [AttrDecls] '}' ['default' Type]
AttrDecls  := Name ['?'] ':' Type [',' | ',' AttrDecls]
Type      := PRIMTYPE | Path | SetType | RecType
```
In essence: We simply extend the definition of record types (used for records and entities) with an optional, default attribute type. Here's a simple example:
```
entity User = {
    name: String,
} default Long;
```
This example shows that `User` has known attribute `name` of type `String`, and a default attribute type `Long`. The JSON syntax requires a new `default` attribute which contains a type. Here's the `User` example in JSON format:
```
"User" : {
    "shape" : {
        "type" : "Record",
        "attributes" : {
            "name" : {
                "type" : "String"
            }
        },
        "default": {
            "type" : "Long"
        }
    }
}
```
The grammar specifies the defaul attribute type _outside_ the syntax defining the record's named attributes to avoid confusion. In particular, since all legal strings are legal record attributes, having syntax inside the `{` `}` could lead to ambiguity. For example, we might like to write `{ *:String }` to indicate that the "default attribute" `*` has type `String`. But `*` is itself a legal attribute name, so we'd be able to write `{ "*": Long, *:String }` to define a record type with a concrete attribute `*` of type `Long` and a default attribute type of `String`. As another example, we might like to write the default type separately from the other attributes' definitions inside the braces. For example, we might like `{ level: Long | String }` to define a record with attribute `level` of type `Long`, and a default attribute type of `String`. But users might see such a type and think that `level` is a union type (which Cedar does not currently support, but could in the future) of type either `Long` or `String`. We could think of syntax within the braces that solves both problems, but adding the default type outside the attribute declarations avoids these and other sources of confusion, and also adds structural parity with the JSON version of the syntax (where `default` is separate from `attributes`). See [Alternatives](#alternatives) for other possible syntax.

### Validating policies

We extend the way the policy validator handles records to support the default attribute.

#### Capabilities

While typechecking a policy, the validator tracks _capabilities_, which represent the attribute-accessing expressions that are sure to succeed. If `principal` has type `User` and `User` has an optional `Boolean` attribute `sudo`, then the expression `principal.sudo` only validates if `principal.sudo` is present in the _current capability set_. Capabilities are added to that set by a preceding expression of the form `principal has sudo`, e.g., as in `principal has sudo && principal.sudo`.

Capability tracking must be generalized to support open records. Today, if you were to write expression `principal has barney` and `principal`'s type `User` has no `barney` attribute, the expression will be given type `False` since the validator knows `principal` can never have this attribute. But if `User` has default attribute type `String` and we see `principal has barney && principal.barney like "friend"`, then `principal has barney` should be given type `Bool` and `barney` should be added to the capability set. Then, when checking `principal.barney like "friend"` the validator will see `barney` in the capability set, and expression `principal.barney` should be given the default attribute type `String`.

#### Record expressions

A record literal is given _closed_ type, i.e., one without a default attribute type. For example, the literal `{ name: "jose", jobLevel : 7 }` has type `{ name: String, jobLevel: Long }`. The validator does this because it knows that the record has no additional attributes beyond those in the literal.

#### Permissive Validation: Subtyping

For permissive validation, we adjust the subtyping rules as follows. First, we add the following rule (1):
```
{ f1-: T1, ..., fn-: Tn } <: { f1-: T1, ..., fn-: Tn } default T
```
Here, we write `-` to indicate the "optionality" of an attribute, where the optionality can be either `?`, meaning the attribute is optional, or it can be non-present, meaning the attribute is required.

Thus, this rule says that any _closed_ record can be treated as if it were an open record, where the the default attribute type is arbitrary (here, written simply `T`). 

Second, we adjust the width subtyping rule to be the following:
```
{ f1-: T1, ..., fn-: Tn, g-:T } default T <: { f1-: T1, ..., fn-: Tn } default T
```
This rule says that we can subtype an open record type to another open record type with fewer attributes, where the dropped attributes have the same type as the default attribute type.

With these two rules, along with transitivity, reordering, etc., here are some example judgments we can prove:
```
{ f1: Long, f2: String } <: { f1: Long, f2: String } default Bool
{ f1: Long, f2: String } <: { f1: Long } default String
{ f1: String, f2: String } <: { } default String
{ f1: String, f2: String } default String <: { } default String
{ f1: String, f2: { f21: String, f22: Long } } default { f21: String } <: { f1: String } default { f21: String }
```
The last example above combines depth and width subtyping in order to drop field `f2`, whose type `{ f21: String, f22: Long }` is a subtype of `{ f21: String }`.

Here are some examples we _cannot_ prove:
```
{ f1: Long, f2: String } default String <: { f1: Long, f2: String }
{ f1: Long, f2: String } <: { f1: Long }
{ } default String <: { f1?: String } default String
```
The first example is not allowed because open records, which could have an arbitrary and unknown number of attributes, cannot be given closed type, in which all attributes are known. The second example is not allowed because the type `{ f1: Long }` is closed, and as a result the validator can assume it has no additional attributes. The last example is sound, but not allowed for simplicity; if this additional flexibility is needed we could add a subtyping rule (3)
```
{ f1-: T1, ..., fn-: Tn } default T <: { f1-: T1, ..., fn-: Tn, g?:T } default T
```

### Validating entities

Cedar's `is_authorized` can be asked to validate that entities in a request are consistent with a provided schema. Extending validation to work with open records is straightforward. The type rule is basically thus:
```
v1: T1 ... vn: Tn
u1: T  ... um: T
-------------------------------------------------------------------------------
{ f1: v1, ..., fn: vn, g1: u1, ... gm: um } : { f1: T1, ..., fn: Tn } default T
```
In particular, when asked to determine if a record is open with default attribute type `T`, the validator confirms that all of the required attributes `f1` ... `fn` are present with the right types, and all the remaining non-required attributes `g1` ... `gm` have values of the default attribute type `T`. Another way to put this is that a record `v` can be given _open_ record type `T` (which has some default attribute type) iff there exists a _closed_ type `T'` such that `v` has the type `T'` and `T'` is a subtype of `T`.

## Drawbacks

### Unintuitive strict validation behavior

Strict validation lacks subtyping, so adding open records could lead to some unintuitive validation behavior.

For example, suppose that entity `User` has a `tags` attribute whose type is `{ } default String`. Suppose our policy contains the following expression (call it E): `principal.tags == { foo: "hello", bar: "there" }`. Unfortunately, with strict validation expression E will be rejected. That's because strict validation requires both sides of `==` to have the same type, but the literal `{ foo: "hello", bar: "there" }` has type `{ foo: String, bar: String }` while `principal.tags` has the type `{ } default String`, which is not the same. (With subtyping, a common type between the two could be found.)

For a similar reason, we could not write something like the following:
```
(if (principal.ok) then
  principal.tags
else
  { foo: "hello", bar: "there" }) has foo && principal.foo == "hello"
```
This expression is rejected is because conditionals require both branches to have the same type.

That said, the use-case that motivates open records is supported, e.g., an expression like the following will validate, assuming both `principal.tags` and `resource.tags` have the same type (such as `{ } default String`):
```
principal.tags has "priority" && resource.tags has "priority" && principal.tags["priority"] == resource.tags["priority"]
```

Moreover, the validation incompleteness described here is already visible to some degree. For example, you cannot write `principal.identities == resource.owners` when the former has type `Set<User>` and the latter has type `Set<String>`, even though both could be the `[]` and thus the `==` expression could evaluate to `true`.

We could imagine a future extension in which we use _type inference_ to give literals different types depending on the context, e.g., to allow something like `principal.tags == { foo: "hello", bar: "there" }` by inferring the type of the latter to be `{ } default String` assuming the former's is. (We could do likewise to allow `principal.identities == []`, which is not currently allowed.)

### Implementation effort

The implementation effort for adding open records is non-trivial, as it will require changing the Rust code, the Lean models and proofs, and the differential test generators. It will also affect any component that leverages the schema and validator algorithms, such as schema-based parsing, and the policy analyzer. Quoting a [comment from an earlier version of this RFC](https://github.com/cedar-policy/rfcs/pull/66#discussion_r1613723900) about the latter:

"On the analysis side, implementing this proposal will require adding another theory to the encoding: theory of arrays with extensionality. This will not only slow down the analysis in practice, but it will also be technically challenging to integrate into the encoding. By technically challenging, I mean we have to figure out how to do bridge a fundamental mismatch between SMT arrays and open records, where the 'open' part is a finite map. Arrays are not finite maps---rather, they behave like uninterpreted functions over the entire domain (strings in our case)---and we will need to figure out how to convert the resulting infinite maps back into Cedar's finite maps in order to provide correct counterexamples and to preserve the completeness of the encoding."

That said, there are no required changes to the _evaluator_, _authorizer_, or _partial evaluator_, as this RFC only proposes to change Cedar types, not values.

## Alternatives

### Syntax

As discussed in the main body of the RFC, we cannot easily define an open record by specifying a "default attribute" with type `T` because all strings are legal attributes. Hence we must specify the default attribute type separately from the rest of the attributes in a clear and natural manner. The RFC proposes to write `{ ... } default T` with `T` as the default attribute type. We could instead pick some alternative, e.g.,

- `{ ... }(default = T)`
- `<default = T>{ ... }`
- `{ ... } else T`

### Dynamic attributes

Open records are no different from closed records in that accessing an attribute value requires writing the attribute as a literal. E.g., you must write `principal.tags["foo"]` and cannot write `principal.tags[resource.name]` since `resource.name` is not a literal. This restriction might be problematic when encoding tags as attributes if you want to specify a tag dynamically, e.g., by storing it a request `context`.

We could support _dynamic_ specifications of a record's attribute to solve this problem; i.e., we could allow expressions like `principal.tags[resource.name]`. Doing so presents some problems for an efficient logical encoding, for policy analysis, which is why dynamically specified attribute names are not supported today. If needed in the future, we could reconsider (with a new RFC).

### Maps

We are primarily proposing using open records to implement maps, where map keys are (string) attributes. We believe this makes sense becuase maps and records are extremely similar, and it would be unsatisfying to introduce new syntax just to support maps. Previously, [RFC 27](https://github.com/cedar-policy/rfcs/pull/27) proposed to create `map<T>` types as alternative types for records whose attributes all have the same type `T`, basically equivalent to `{} default T`. This RFC is more general while also being conceptually simpler, making more plain the relationship between maps and (closed) records.

### Workaround: Records wtih optional attributes

We could avoid adding open records and work around their absence.

In particular, to implement tags as attributes one could create a record type that enumerates every legal tag as an optional attribute. Then, every time you create a policy that writes a map key as a literal, the validator will complain if that key is not in the schema. So, add the key to the schema, and the new policy will validate along with the old ones.

However, changing the schema on the fly to extend the list of valid keys could be expensive. If policies are being constructed on the fly, e.g., by a service's users, a schema update to support a new tag used by a new policy would technically require re-validating existing policies, whereas with with open records we can leave the schema alone and avoid re-validation entirely.

### Workaround: Tags as sets of key/value pairs

As mentioned in the Motivating Example, you could also implement tags as sets of key/value pairs. One limitation of that encoding is that you cannot easily compare tag values from two different sets of tags. [RFC 21](https://github.com/cedar-policy/rfcs/pull/21) would solve that problem through the introduction of the `any?` and `all?` operators. However, RFC 21 was rejected due to problems with logically encoding it for policy analysis.
