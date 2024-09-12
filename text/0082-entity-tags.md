# Entity tags with dedicated syntax and semantics

## Related issues and PRs

* Reference Issues: [#305](https://github.com/cedar-policy/cedar/issues/305)
* Supersedes [RFC 68](https://github.com/cedar-policy/rfcs/pull/68)
* Implementation PR(s): (leave this empty)

## Timeline

* Started: 2024-09-11
* Accepted: TBD
* Landed: TBD
* Released: TBD

## Summary

This RFC proposes to extend the Cedar language, type system, and symbolic analysis to include full-featured *entity tags* for entity types. Tags are a mechanism used by cloud services to attach key-value pairs to resources. Cedar will allow them to be attached to any entities (not just resources).

For evaluation purposes, entity tags are accessed using the methods `expr1.hasTag(expr2)` and `expr1.getTag(expr2)`, where `expr1` evaluates to an entity and `expr2` to a string.  These are the only ways to access the tags on an entity.  The policy syntax, semantics, type system, and symbolic analysis are extended to support these two methods.  The schema syntax and the entity JSON format are extended to support defining entity tags and their types.

Entity tags strictly increase the expressiveness of Cedar because they allow *computed keys*, unlike records and entities. Specifically, tag keys need not be literals, so it is possible to write `resource.hasTag(context.tag)` and `resource.getTag(context.tag)`.

This proposal is backward-compatible in the sense that existing polices, schemas, entities, etc., do not need to change to accommodate the addition of tags to the language.

This RFC has gone through several revisions, with different revisions proposing alternative designs. The alternatives are discussed at the end of this document.

### Basic example

Here is a schema defining two entities, each of which contains entity tags.

```
entity User = {
  jobLevel: Long,
} tags Set<String>;
entity Document = {
  owner: User,
} tags Set<String>;
```

The `User` and `Document` entities each have entity tags, denoted by `tags Set<String>`, implementing tags whose values are sets of strings.  The declaration `tags Set<String>` indicates an unspecified number of optional tags that all have values of type `Set<String>`.  (Of course, any type could be written, for instance `Long`, not just `Set<String>`.) Note that the set of tag (keys) does not have to be defined in the schema, but the type of all tag values needs to be the same (here, `Set<String>`).  (You cannot have tag `foo` have value `2`, and tag `bar` have value `"spam"`.)  Note also that there is no way to name the key-value map representing tags; you cannot treat it as a Cedar record or even compare it for equality to the tag-map on a different entity; you can only compare the values of individual keys.

Here's a policy that conforms to this schema:

```
permit (
  principal is User,
  action == Action::"writeDoc",
  resource is Document)
when {
  document.owner == principal ||
    (principal.jobLevel > 6 &&
    resource.hasTag("write") &&
    principal.hasTag("write") &&
    resource.getTag("write").containsAny(principal.getTag("write")))
};
```

This policy states that for a `User` to carry out the *writeDoc* action on a `Document`, the user must own the document, or else the user's job level must be at least 6 and the document and the user must each have a `write` tag, where at least one of the user's write-tag's values must be present in the document's write-tag's values.


## Detailed design

To support entity tags, we need to extend the JSON format for entities, the JSON and natural syntax for schemas, the policy syntax, as well as the evaluator, validator, and symbolic compiler.


### Policy syntax and semantics

Tags support two binary operators, where `e` and `k` are Cedar expressions:


```
e.hasTag(k)
e.getTag(k)
```


The `hasTag` operator tests if the entity `e` has a tag with the key `k`.  This operator errors if `e` is not an entity, or `k` is not a string. It returns `false` if `e` doesn't have any tags at all to match the behavior of the `has` operator on entities and records. In other words, having no tags is equivalent to having an empty tags-map. The `getTag` operator retrieves the value for the key `k` from the tags for the entity `e`.  This operator errors under the same conditions as `hasTag` and additionally, if `e` has no tag with the key `k`.

At the code level, we will extend the Cedar CST, AST, and EST to include the new operators (either as separate nodes in the relevant trees or as two extra binary operators), and we'll extend the evaluator to implement the above semantics.


### JSON entity format

The JSON entity format is extended to support optionally specifying tags separately from entity attributes:


```
[
    {
        "uid": {},
        "parents": [],
        "attrs": {},
        "tags": {}
    },
    {
        ...
    }
]
```



### Schema

We extend schemas as follows to support the declaration of a tags. Here's the natural syntax:


```
Entity := 'entity' Idents ['in' EntOrTyps] [['='] EntityRecType] ['tags' Type] ';'
```


The new syntax simply extends the `Entity` production to enable optionally specifying the type of attached tags.

The JSON syntax for schemas specifies tags as a separate `tags` field that specifies the type of the tag values. Here's our introductory example schema in this format:

```
"entityTypes": {
    "User" : {
        "shape" : {
            "type" : "Record",
            "attributes" : {
                "jobLevel" : {
                    "type" : "Long"
                },
            }
        },
        "tags" : {
            "type" : "Set",
            "element": { "type": "String" }
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
            }
        },
        "tags" : {
          "type" : "Set",
          "element": { "type": "String" }
        }
    }
}
```



### Validating policies

We extend the way the policy validator to handle the `hasTag` and `getTag` operators analogously to how it handles the `has` and `.` operator on records and entities.


#### Capabilities

Background: While typechecking an expression involving records or entities with optional attributes, the validator tracks *capabilities*. These represent the attribute-accessing expressions that are sure to succeed. If `principal` has type `User` and `User` has an optional `Boolean` attribute `sudo`, then the expression `principal.sudo` only validates if `principal.sudo` is present in the *current capability set*. Capabilities are added to that set by a preceding expression of the form `principal has sudo`, e.g., as in `principal has sudo && principal.sudo`.

Capability tracking must be generalized to support tags. In particular, `tags T` should be treated as a record with optional attributes, and `hasTag` checks on its keys should update the capability set. For our introductory example, consider the following expression

```
  resource.hasTag("write") && // (1)
  principal.hasTag("write") &&  // (2)
  resource.getTag("write").containsAny(principal.getTag("write")) // (3)
```

After the subexpression (1), `resource.hasTag("write")` should be added to the current capability set. After subexpression (2), `principal.hasTag("write")` should be added to it. Finally, when validating subexpression (3), the expression `resource.getTag("write")` will be considered valid since `resource.hasTag("write")` is in the current capability set and it will be given type `Set<String>`, as the `tags` for `resource` has type `Set<String>`. The expression `principal.getTag("write")` is handled similarly. If either of the `hasTag` subexpressions (1) or (2) were omitted, subexpression (3) would not validate due to the missing capability set entries.

For entity types with no `tags` declaration in the schema, the validator gives `hasTag` the type `False` (to support short-circuiting), and rejects `getTag`.


### Validating and parsing entities

The Cedar authorizer's `is_authorized` function can be asked to validate that entities in a request are consistent with a provided schema. Extending validation to work with tags is straightforward. We check that every value in the `tags` map for an entity `e` has type `T` given that type of `e` is declared to have `tags T`.  If the type `e` doesn't have `tags` in the schema, then specifying a `tags` field is an error.

Similarly, schema-based parsing considers schemas when parsing in entities, and it can confirm when parsing that the contents of `tags` attribute in the JSON have the appropriate shape, and if the type `T` has different behavior under schema-based parsing (for instance, if it is an extension type), then schema-based parsing can interpret the `tags` appropriately.


### Symbolic compilation

Tags as defined here have an efficient logical representation as *uninterpreted binary functions*.  In particular, for each declaration `entity E ... tags T`, we introduce an uninterpreted function `f_E` of type `E -> String -> Option T`.  With this representation, we can straightforwardly translate the `hasTag` and `getTag` operations as applications of the function `f_E`, where the absence of a key is denoted by binding it to the value `(none T)`.


## Drawbacks

Entity types are permitted to have a single `tags` declaration `tags T`, which eliminates the possibility of attaching multiple tags-maps to a single entity (unlike [RFC 68](https://github.com/cedar-policy/rfcs/pull/68)).  This RFC also does not support tags containing other tags-maps, comparing tags-maps with `==`, and the like (as discussed above).

The use-cases that we are aware of do not suffer due to these limitations. If you wanted tags-maps to contain other tags-maps, or you wanted to store tags-maps in the `context` record, or you wanted to attach multiple tags-maps to a single entity, you can create specific entity types with those tags. For example:

```
entity User {
  roles: Set<String>,
  accessLevels: IntTags
} tags StringTags;
entity StringTags {
} tags String;
entity IntTags {
} tags Long;
```

In effect, the `User`'s tags is equivalent to `tags (tags String)`, but we have added a level of indirection by expressing the inner `(tags String)` value as an entity with `tags String`. Similarly, the `User`'s `accessLevels` attribute is equivalent to `(tags Long)`. So, we can express policies such as:


```
permit(principal is User, action, resource is Document)
when {
  principal.roles.contains(context.role) &&
  principal.accessLevels.hasTag(context.role) &&
  principal.accessLevels.getTag(context.role) > 3
};

permit(principal is User, action, resource is Document)
when {
  principal.hasTag("clearance") &&
  principal.getTag("clearance").hasTag("level") &&
  principal.getTag("clearance").getTag("level") == "top secret"
};
```

### Implementation effort

The implementation effort for adding tags is non-trivial, as it will require changing the Rust code, the Lean models and proofs, and the differential test generators. It will affect most components of Cedar, including the policy parser, CST→AST conversion, CST→EST conversion, (schema-based) entity parser, (partial) evaluator, validator, and the symbolic compiler.

While they affect most components of Cedar, these changes are relatively localized and straightforward, as outlined above.


## Alternatives and workarounds

This feature has gone through several revisions and iterations.  We compare this proposal to its predecessor, [RFC 68](https://github.com/cedar-policy/rfcs/pull/68), which discusses other alternatives and workarounds in detail.

RFC 68 proposes to add embedded attribute maps (EA-maps) to Cedar as a second-class, validation-time construct that behaves like a record with limited capabilities. Specifically, an entity attribute can have an EA-map type, but EA-maps cannot occur anywhere else (e.g., it is not possible to have a set of EA-maps).  EA-maps are treated as special second-class values during validation. But they are indistinguishable from records during evaluation.

In RFC 68, the validator enforces the second-class status of EA-map records by rejecting (some) expressions that attempt to treat EA-maps as first class values.  For example, the validator would reject `principal.authTags == resource.authTags`, where the `authTags` attribute of `principal` and `resource` is an EA-map of type `{ ? : Set<String> }`.  It would also reject `(if principal.isAdmin then principal.authTags else principal.authTags).write`.  However, it would accept `(if true then principal.authTags else resource.authTags).write` due to how capabilities work in Cedar's type system.  This behavior is confusing in that EA-maps don't appear to consistently act as second class values, and understanding when they do requires understanding the subtleties of how the Cedar type system works.

In RFC 68, the dynamic semantics is unaware of EA-maps. That is, the concept of EA-maps doesn't exist at evaluation time; they are just records. This leads to lower implementation burden (e.g., evaluator doesn't need to change), but it widens the gap between the dynamic and static (type-aware) semantics of Cedar. Specifically, EA-maps are first-class values during evaluation but not during validation.

EA-maps, as proposed in RFC 68, do not add any new expressiveness to Cedar.  Since EA-maps are just records at evaluation time, computed keys (such as `resource.getKey(context.tag)`) are disallowed. Adding computed keys (Alternative A in RFC 68) requires roughly the same implementation effort as implementing this proposal. But a downside of adding computed keys to RFC 68 is that doing so would further widen the gap between the dynamic and static semantics, since computed keys would be rejected by the validator but *not* the evaluator on records that aren't EA-maps.

Finally, after [modeling RFC 68 in Lean](https://github.com/cedar-policy/cedar-spec/pull/418), we found ourselves in an engineering corner, where the type-based enforcement of second-class status of EA-maps makes it difficult to prove a key property of the validator (every policy that is accepted by the validator is also accepted by the symbolic compiler), and also to model and reason about EA-maps in every component that depends on Cedar types.

The core issue is that RFC 68 does not distinguish, at the syntax and semantics level, between records and EA-maps.  This distinction must be enforced at the type level. In particular, we need to introduce a first-class EA-map type, which must then be treated as second-class in specific expressions during type checking and in proofs. The special-casing must be done for `==`, `if ... then ... else`, `hasAttr`, `getAttr`, `contains`, `containsAll`, `containsAny`, `set`, and `record` expressions.

This special-casing will have to be repeated in every component that gives a static (type-aware) semantics to Cedar---such as the symbolic compiler and, potentially, a type-aware partial evaluator. It will also need to be propagated into specifications and proofs of type-aware components. This is expected to increase the overall implementation and proof burden by thousands of lines of Lean code compared to this proposal. (In the symbolic compiler, the burden is further magnified because the special-casing of EA-map types has to be propagated into the underlying Term language too.)

This proposal avoids the issues of RFC 68 by introducing dedicated syntactic and semantic constructs for working with tags.  It is impossible, at the syntax level, to write a Cedar expression that evaluates to a (first-class) tags-map value. Rather, the contents of a tags-map are accessed by applying the `hasTag` and `getTag` operators to the entity that has the tags. These two operators are explicit in the AST, and they can be handled locally in the Lean model and proofs, without changing the handling of any other operator. This proposal also reflects tags in both the static and dynamic semantics, keeping their treatment consistent between the two.

Compared to RFC 68, this proposal represents a more substantial addition to the language, and it requires a significantly larger up-front implementation effort.  The tradeoff is that investing in the implementation now means that we won't have to consistently pay an implementation and proof penalty for every new type-aware component we add to Cedar.  And adopting the bigger language change now lets us keep the dynamic and static semantics consistent, freeing users from having to reason about the subtleties of Cedar's type system.
