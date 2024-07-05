# Entity tags

## Related issues and PRs

- Reference Issues: [#305](https://github.com/cedar-policy/cedar/issues/305)
- Supercedes [RFC 66](https://github.com/cedar-policy/rfcs/pull/66)
- Implementation PR(s): (leave this empty)

## Timeline

- Start Date: 2024-05-29
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

This RFC proposes to extend the Cedar type system with the ability to attach _tags_ to entities. Entity tags are a set of key/value pairs with an interface similar to records: keys are like record attributes and values are like attribute values. But unlike records, keys need not be enumerated in advance, as is required with record attributes, and all tag values must have the same type.

The main body of this RFC proposes that tag keys must be _literals_ when used to look up a tag's value, just like record attributes, but Alternative A generalizes this proposal to allow keys to be dynamically computed. Alternative A thus adds expressive power but also implementation cost.

### Basic example

Here is a schema defining two entities, each of which contains entity tags.
```
entity User = {
  jobLevel: Long,
  authTags: { ?: Set<String> },
};
entity Document = {
  owner: User,
  policyTags: { ?: Set<String> },
};
```
The `User` and `Document` entities each have an attribute of type `{ ?: Set<String> }`, identifying tags whose values are sets of strings. The syntax for this type evokes a record, per the curly braces, but without named attributes; by providing just a `?` followed by a colon and a type, we indicate an unspecified number of optional attributes that have values of that type (here, `Set<String>`).

Here's a policy that conforms to this schema:
```
permit (
  principal is User,
  action == Action::"writeDoc",
  resource is Document) 
when {
  document.owner == principal ||
    (principal.jobLevel > 6 &&
    resource.policyTags has "write" && 
    principal.authTags has "write" && 
    resource.policyTags["write"].containsAny(principal.authTags["write"]))
};
```
This policy states that for a `User` to carry out the _writeDoc_ action on a `Document`, the user must own the document, or else the user's job level must be at least 6 and the document and the user must each have a `write` tag in their attached tags, where at least one of the user's write-tag's values must be present in the document's write-tag's values.

## Detailed design

Neither the Cedar evaluator/authorizer, the JSON format for entities, nor the JSON or natural syntax for policies needs to change to support entity tags. This is because tags are represented as records and support the same operations. Only the Cedar schema format, the validator, and the schema-based entity parser need to change to account for a new `{ ?: T }` type.

### Schema

Tags have type `{ ?: T }`, where `T` is the type of tag values. Only entity attributes can be given type `{ ?: T }`, and `T` cannot directly mention another tags type.

We extend schemas as follows to support the new tags type. Here's the natural syntax:
```
Entity           := 'entity' Idents ['in' EntOrTyps] [['='] EntityRecType] ';'
EntityRecType    := '{' [EntityAttrDecls] '}'
EntityAttrDecls  := Name ['?'] ':' [Type | TagsType] [',' | ',' EntityAttrDecls]
TagsType         := '{' '?' ':' Type '}'
Type             := PRIMTYPE | Path | SetType | RecType
```
In essence: We alter the definition of entity types to include attributes with type `{ ?: T }`, where `T` is any type not mentioning another tags type. Not shown here are the productions for `RecType` and `AttrDecls`, which apply to records rather than entities. These productions are unchanged---normal records may not include attributes with `{ ?: T }` types.

The JSON syntax for schemas specifies tags as records with a `default` element, rather than an `attributes` element. Doing so leverages the analogy that tags are like records in which all attributes are optional, with the same type. Here's our introductory example schema in this format:
```
"entityTypes": {
    "User" : {
        "shape" : {
            "type" : "Record",
            "attributes" : {
                "jobLevel" : {
                    "type" : "Long"
                },
                "authTags" : {
                    "type" : "Record",
                    "default": {
                        "type" : "Set",
                        "element": "String"
                    }
                }
            }
        }
    },
    "Document" : {
        "shape" : {
            "type" : "Record",
            "attributes" : {
                "owner" : {
                    "type" : "Entity",
                    "name" : "User"
                },
                "policyTags" : {
                    "type" : "Record",
                    "default": {
                        "type" : "Set",
                        "element": "String"
                    }
                }
            }
        }
    }
}
```
Legal schemas only allow records with `default` to appear as direct entity attributes, and likewise restricts the `type` associated with `default` to not include `default`-containing record types. Records with a `default` element cannot also have an `attributes` element (and so cannot have named attributes).

### Policies, entities, and evaluation

Tags support all of the same operations as records. Suppose that `E` is an expression of type `{ ?: T }`. Then expression `E has F` will check whether `E` has tag key `F`, evaluating to `true` if so and `false` otherwise. Expression `E.F` or `E["F"]` will retrieve the value associated with key `F` if `F` is present, signaling an error if it is not.

As a result, within the evaluator we can represent tags as records, so the evaluator code does not need to change. In particular, tags with keys `F1` ... `Fn` and associated values `V1` .. `Vn` are internally represented as records `{ F1: V1, ..., Fn: Vn }`. Similarly, tags are represented as records in the JSON entity format. For example, here is entity representing `User::"Alice"` which conforms to our example schema:
```
    {
        "uid": { "type": "User", "id": "alice" },
        "attrs": {
            "jobLevel": 5,
            "authTags": {
                "write": ["blue", "red"],
                "read": ["blue", "red", "green"]
            }
        },
        "parents": []
    }
```
Note that there is no way to represent a tags _literal_. That is, you cannot write something like `{ write: ["blue", "red"]}` in a policy, like you might for a record literal. This is because tags are always attached to entities, and entities themselves have no literal syntax.

### Validating policies

We extend the way the policy validator handles optional record attributes in order to support entity tags.

#### Capabilities

Background: While typechecking an expression involving records or entities with optional attributes, the validator tracks _capabilities_. These represent the attribute-accessing expressions that are sure to succeed. If `principal` has type `User` and `User` has an optional `Boolean` attribute `sudo`, then the expression `principal.sudo` only validates if `principal.sudo` is present in the _current capability set_. Capabilities are added to that set by a preceding expression of the form `principal has sudo`, e.g., as in `principal has sudo && principal.sudo`.

Capability tracking must be generalized to support tags. In particular, an entity attribute of type `{ ?: T }` should be treated as a record with optional attributes, and `has` checks on its keys should update the capability set. For our introductory example, consider the following expression
```
  resource.policyTags has "write" && // (1)
  principal.authTags has "write" &&  // (2)
  resource.policyTags["write"].containsAny(principal.authTags["write"]) // (3)
```
After the subexpression (1), `resource.policyTags.write` should be added to the current capability set. After subexpression (2), `principal.authTags.write` should be added to it. Finally, when validating subexpression (3), the expression `resource.policyTags["write"]` will be considered valid since `resource.policyTags.write` is in the current capability set and it will be given type `Set<String>`, as `resource.policyTags` has type `{ ?: Set<String> }`. The expression `principal.authTags["write"]` is handled similarly. If either of the `has` subexpressions (1) or (2) were omitted, subexpression (3) would not validate due to the missing capability set entries.

#### Limited operations

Tags' second-class status means that tags can only be used as part of checking expressions `E has F` and projection expressions `E.F` or `E[F]`, where `E` has type `{ ?: T }`. The validator should disallow these expressions with type `{ ?: T }` in other contexts; e.g., the following should be disallowed:
```
resource.policyTags == principal.authTags
[resource.policyTags, principal.authTags]
(if true then principal.authTags else principal.authTags).write
```
(Note that the last case is disallowed because `principal.authTags` is not _directly_ part of a `.` sub-expression -- it is returned from the `if` first.)

### Validating and parsing entities

The Cedar authorizer's `is_authorized` function can be asked to validate that entities in a request are consistent with a provided schema. Extending validation to work with tags is straightforward. The type rule is basically thus:
```
v1: T ... vn: T
---------------------------------
{ f1: v1, ..., fn: vn } : { ?: T }
```
In particular, when asked to determine if a record has type `{ ?: T }`, we confirm that all values in the record have type `T`. By the nature of restrictions on schemas, the validator will only ever consider `{ ?: T }` types associated with entity attributes.

Similarly, schema-based parsing considers schemas when parsing in entities, and it can confirm when parsing that attributes labeled as `Record` in the JSON but defined as `{ ?: T }` in the schema have the appropriate shape.

### Permissive Validation

Permissive validation supports subtyping, which we extend so as to allow tag types to be treated co-variantly:
```
{ ?: T } <: { ?: U }    iff T <: U
```
We might consider adding rules that permit subtyping between records and tags, but doing so introduces some complications with width subtyping. We could choose to grant tags first-class status under permissive validation. For example, we could allow tags values to appear anywhere, e.g., in `Set`s or records, and we could allow equality between tags values. We choose not to do these things for now.

## Drawbacks

### Non-dynamic keys

Tags keys must be written in policies as literals. For example, you cannot write the following policy expression (using our example schema from above):
```
principal.authTags has context.key && 
principal.authTags[context.key] == context.value
```
Supporting such _dynamic keys_ is more work, but doable. With them, `{ ?: T }` tags would be strictly more powerful than existing tag encodings/workarounds. We sketch the needed implementation work in Alternative A, below, and a comparison to workarounds further below.

### Second-class status

Only entity attributes are permitted to have type `{ ?: T }`, which eliminates the possibility of `{ ?: T }` literals and tags directly containing other tags. We also forbid using `==` and operations other than `has` and projection on `{ ?: T }`-typed expressions.

These restrictions are present for two reasons. First, second-class status ensures tags are efficiently _analyzable_. Allowing first-class tags values would require supporting equality between tags values (directly or indirectly). Supporting equality would require a policy analysis to model tags as arrays imbued with the extensionality axioms, which are known to be expensive. Second, second-class status means that we cannot introduce tags literals, which means we do not need to introduce new syntax for tags, which would be essentially the same as record literal syntax, leading to possible user confusion. Nor do we need to consider how we might treat record literals as equivalent to `{ ?: T }` values.

The use-cases that we are aware of do not suffer due to these limitations. Typically, you want to attach tags to principals and resources. If you wanted tags to contain other tags, or you wanted to store tags in the `context` record, you can create specific entity types containing only those tags. For example:
```
entity User {
    roles: Set<String>,
    roleTags: { ?: StringTags },
};
entity StringTags {
    tags: { ?: String }
};
```
In effect, the `User`'s `roleTags` is equivalent to `{ ?: { ?: String } }`, but we have added a level of indirection by expressing the inner `{ ?: String }` value as an entity with a `{ ?: String }` attribute.

### Implementation effort

The implementation effort for adding tags is non-trivial, as it will require changing the Rust code, the Lean models and proofs, and the differential test generators. It will also affect any component that leverages the schema and validator algorithms, such as schema-based parsing, and the policy analyzer.

That said, these changes are relatively straightforward:
- The validator changes are a straightforward extension to the handling of records with optional attributes. The extension to subtyping for permissive validation is also simple.
- Changes to entity validation and schema-based parsing are fairly localized: They must consider the new tags type when validating/parsing JSON `Record`-labeled entities.
- The policy analyzer can model `{ ?: T }` attributes as uninterpreted functions because it never needs to consider equality between `{ ?: T }` values. Equality between entities is _nominal_ -- we just consider the entity UID, not the contents of an entity's mapped-to attribute record (the only place that tags can exist).
- There are _no_ changes to the evaluator or partial evaluator: From an evaluation perspective, `{ ?: T }` attributes are just attributes containing records whose attributes all have values of type `T`.

## Alternatives

### Alternative A: Tags with dynamic keys

Supporting dynamic keys (see "Drawbacks: Non-dynamic keys" above), requires a few extensions to the main proposal: to the policy grammar, evaluator (and partial evaluator), validator, and analysis.

#### Policy grammar and evaluator

We change the [grammar for `has`](https://docs.cedarpolicy.com/policies/syntax-grammar.html#relation) so that the given attribute can be a [`Member`](https://docs.cedarpolicy.com/policies/syntax-grammar.html#member), rather than an `IDENT`:
```
Relation ::= ... | Add 'has' (Member | STR)
```
Here, if `Member` is just an identifier like `foo` then it is interpreted as a key name. Otherwise it is treated as an expression that should be evaluated to a string, which is the name of the key.

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
It may be that `Member` is a bit too expressive. If so, we may consider making key-computing expressions simpler, e.g., `foo.bar.baz`, and not `User::"foo".bar.baz` or `{ foo: "bar" }.foo`.

We can allow this extended syntax and evaluation semantics to apply to normal record and entity attributes as well. The validator will prevent it, however, so it will only be possible for non-validated policies.

#### Validator

The validator must change to further extend capability tracking from what we've described above to include dynamically contructed attribute names. This should be straightforward. When the validator sees something like `principal.tags has resource.name` then this would generate the capability `principal.tags[resource.name]` that would allow a follow-on expression `principal.tags[resource.name]` to validate. 

In addition, it's now possible that an attribute-constructing expression could access a bogus attribute, so those expressions must be validated as well. E.g., when validating `principal.tags has resource.name` or `principal.tags[resource.name]`, the validator must confirm that `resource` indeed has a `name` attribute.

Because expressions like `principal has context.name` are now grammatically legal, the validator must be updated to consider them fully. In partcular, the validator should only allow `F` to be an expression when writing `E has F` or `E[F]` if `E` has type `{ ?: T }`---it will not be allowed when `E` has a normal record or entity type.

#### Analysis

The policy analyzer's logical encoding must be generalized to account for keys being specified as expressions rather than as literals. Because we are encoding tags as uninterpreted functions, this presents no problem: it doesn't matter whether the key given to the function is a literal string or an expression that evaluates (is equivalent) to a string. That said, counterexample generation could be a little more involved.

#### Summary

There is a tradeoff here. Alternative A is more work to implement than the RFC as given, but not significantly more. And it carries a significant benefit: It enables this notion of tags to be strictly more expressive than both of the workarounds given below, which are modeling tags as optional attributes, and modeling tags as sets of key-value pairs. Anything you can do with either of those workarounds you can do with Alternative A. As a result, policy writers will be encouraged to always use tags directly, which will be easier to manage for policy readers.

### Alternative B: Open records

Previously, [RFC 66](https://github.com/cedar-policy/rfcs/pull/66) proposed _open records_ as a generalization of records suitable for encoding tags. Open records are first-class values, however, and so they add far more complication to the implementation effort. See that RFC for further discussion.

### Alternative C: Maps

Another prior RFC, [RFC 27](https://github.com/cedar-policy/rfcs/pull/27), proposed to create `map<T>` types as alternative types for records whose attributes all have the same type `T`, and whose attributes can be dynamically constructed (like dynamic keys for Alternative A, above). That RFC's `map<T>` type is quite similar to this RFC's `{ ?: T }` type except that maps are not second-class, and support dynamic keys. Supporting maps would lead to even greater implementation challenges than open records, per discussion on both of those prior RFCs.

### Alternative D: Different syntax

Rather than give entity tags the type `{ ?: T }`, we could give them the type `Tags<T>` instead. The drawback is that this type may more strongly suggest that tags can be first class, though they are not. It also fails to evoke the analogy with records, i.e., that tags are a set of key/value pairs, with values all having the same type.

To avoid potential confusion we could give tags type `{ T }` instead of `{ ?: T }`. The latter syntax could be confusing because `{ "?": T }` is already a legal type for a record with a required attribute `"?"` (thus allowing expressions like `context["?"] == resource.foo`). It might be surprising to users that surrounding `?` in quotes would change the meaning of the type, since types like `{ "name": Long }` and `{ name: Long }` are equivalent. Using syntax `{ T }` would eliminate the potential for a confused interpretation. Nevertheless, the potential for it already exists. Types `{ isPrivate?: Bool }` and `{ "isPrivate?": Bool }` are not the same: The former indicates an optional attribute `isPrivate` whereas the latter indicates a required attribute `"isPrivate?"`. Given this, we prefer syntax `{ ?: T }` since it more directly evokes that entity tags are a kind of record with all-optional attributes, and is no more confusing than the status quo.

Finally, we could give tags the type `Map<K,V>` but require `K` to always have type `String`. Doing so evokes that tags are a kind of map, but may be disappointing to users in that `K` cannot be anything other than `String`, and `Map` values are not first-class.

### Workaround: Records with optional attributes

We could avoid adding tags entirely and work around their absence.

A direct workaround is to implement tags as a record type that enumerates every legal tag as an optional attribute. Then, every time you create a policy that mentions a tag key as a literal, the validator will complain if that key is not in the schema. So, add the key to the schema, and the new policy will validate along with the old ones.

The drawback of this approach is that hanging the schema on the fly to extend the list of valid keys could be expensive. If policies are being constructed on the fly, e.g., by a service's users, a schema update to support a new tag used by a new policy would technically require re-validating existing policies, whereas with tags `{ ?: T }` we can leave the schema alone and avoid re-validation entirely.

Schemas are also simpler with `{ ?: T }` types, rather than a long list of optional attributes, and better communicate intent.

### Workaround: Tags as sets of key/value pairs

Another way to implement tags is as sets of key-value pairs. For example, `principal.tags` could have type `Set<{ key:String, value:String }>` and a tag check would involve an expression like `principal.tags.contains({ key: "priority", value: "green" })`.

This approach has the benefit that keys can be dynamic. E.g., you can write
```
principal.tags.contains(context.tagvalue)
```
where `context.tagvalue` can be dynamically determined. However, with this encoding of tags you cannot write expressions such as `resource.tags["project"] == principal.tags["project"]`
or 
`resource.tags["projects"].contains(principal.tags["project"])`. We find this to be a strong limitation, as customers often want to exprss policies that relate the tags of principals to those of resources. Note that [RFC 21](https://github.com/cedar-policy/rfcs/pull/21) would lift this limitation through the introduction of the `any?` and `all?` operators, but it was rejected due to problems with logically encoding these operators during policy analysis.
