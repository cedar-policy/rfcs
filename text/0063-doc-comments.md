# Policy and Schema Doc Comments

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2024-04-12

## Summary

Cedar should support documentation comments (doc comments) on both policy and schema elements.

Doc comments are a refinement to our current comments, distinguished by a third `/` and restricted in where they can appear.
These comments are designed specifically to support rendering documentation as HTML pages (or similar), but this RFC does not propose what the final rendered form should be.

## Basic example

A policy can be documented by placing a doc comment, indicated by `///` following the style of Rust, immediately before the policy and on scope conditions.

```cedar
/// Allow users to create list and see the lists they own.
@id("policy0")
permit (
    principal,
    /// The `GetLists` action only returns the lists owned by that users, so this
    /// policy does not allow users to see lists created by others.
    action in [Action::"CreateList", Action::"GetLists"],
    resource == Application::"TinyTodo"
);
```

Doc comments may also be placed immediately prior schema elements to document the purpose of entity types and actions and before each attribute for an entity type or action context.

```cedarschema
/// This entity defines our central user type
entity User { 
    /// The location where this user works. E.g., ABC17 or XYZ77.
    location : String,
    /// A numeric level describing this users job.
    jobLevel : Long,
}
```

## Motivation

Even though the syntax of Cedar policies is designed to be easy to read and understand, policies will still require some amount of documentation. 
Cedar naturally supports comments so policy authors can leave remarks in their code, but these comments do not exist in our policy JSON format or in our internal AST.
Automated generation of documentation from comments is a common capability found in almost all modern programming languages, so we should update Cedar to include automatically processable comments that support this use case.

This RFC is largely motived by [this comment on RFC 48](https://github.com/cedar-policy/rfcs/pull/48#issuecomment-1937735924).
It also addresses the request in [Cedar issue 660](https://github.com/cedar-policy/cedar/issues/660) for comments in the JSON policy format. 

## Detailed design

Doc comments are designed to be very similar to annotations, and could reasonably be implemented as syntactic sugar for a special annotation annotation key.
The primary difference is that, in order to fully satisfy the documentation use case, doc comments need to appear in more positions than are supported for annotations.
We may choose to extend annotation to be supported in all positions proposed for doc comments, but this is not a necessary extensions to accept this RFC.

Doc comments will be defined by this grammar.

```
DocCommentLine ::= '///' [^\r\n]* [\r\n]
DocComment ::= {DocCommentLine}
```

### Policies

Documentation for the policy as whole appears before the policy effect.
It may be anywhere in relation to the annotations on that policy.
Documentation for individual policy scope clauses must appear immediately before that clause.

The policy grammar is now:

```
Policy ::= (Annotation|DocComment)} Effect '(' Scope ')' {Conditions} ';'
Scope ::= [DocComment] Principal ',' [DocComment] Action ',' [DocComment] Resource
```

### Schema

Documentation for a declaration in a schema appears immediately before the `entity`, `action`, `type`, or `namespace` keyword at the start of the declaration.
The fields of the attributes in a record type can also be documented with the comment appearing directly before the attribute name.
A record type might be written for an entities attributes, actions context, or common type definition, or it might be nested inside of some other type.
Doc comments are supported in all of these locations.

The schema grammar is now:

```
Namespace := ([DocComment] 'namespace' Path '{' {Decl} '}') | Decl
Decl := [DocComment] (Entity | Action | TypeDecl)
AttrDecls := [DocComment] Name ['?'] ':' Type [',' | ',' AttrDecls]
```

### Improperly placed comments

Comments starting with the `///` that are not in a legal positions for doc comments are an error.
The definition of comments is accordingly updated to

```
COMMENT ::= '//' ([^/\r\n] [^\r\n]*)? [\r\n]
```

This makes the RFC a breaking change for any users who wrote comments in this style, but I believe that is preferable to silently ignoring what a user intended to be a doc comment.
For an initial and backwards compatible change, improperly place doc comments could be allowed with a warning.
We can then make this an error in a future major version of the Cedar, or never make it an error if the break is not acceptable.

### Alternative doc comment syntax

Choosing to use Rust style doc comments feels natural after developing Cedar in Rust, but we should consider alternative syntax options.
Some options include using block style doc comments (`/** .. */`), using another common comment character for doc comments (e.g., `#`), and picking a different third character following hte usual two slashes (e.g., `//@` to emphasize the connection with annotations).

### JSON Formats

Doc comments will be represented in the policy and schema JSON formats by adding a `doc` property to relevant nodes.

In a policy:

```json
{
    "doc": "Allow users to create list and see the lists they own.",
    "effect": "permit",
    "principal": {
        "op": "All"
    },
    "action": {
        "doc": "The `GetLists` action only returns the lists owned by that users, so this policy does not allow users to see lists created by others",
        "op": "in",
        "entities": [
            { "type": "Action", "id": "CreateList" },
            { "type": "Action", "id": "GetList" }
        ]
    },
    "resource": {
        "op": "==",
        "entity": { "type": "Application", "id": "TinyTodo" }
    }
}
```

and in a schema:

```json
{
    "entityTypes": {
        "User": {
            "doc": "This entity defines our central user type",
            "shape": {
                "type": "Record",
                "attributes": {
                    "location": { 
                        "doc": "The location where this user works. E.g., ABC17 or XYZ77.",
                        "type": "String"
                    },
                    "jobLevel": {
                        "doc": "A numeric level describing this users job.",
                        "type": "Long"
                    },
                }
            }
        }   
    }
}
```

## Drawbacks

1. This is a significant change to the parsers for policies and schema, both in their human readable and JSON formats.
   There is always a possibility of mistakes when making changes to our parsers, especially given that they are not modeled and differentially tested.
2. This will eventually be a breaking change to the policy format.
   Although, as noted above, we don't need to make this change immediately, and we could even opt to never make the change.
3. We are likely to find that users want to add doc comments in a position we didn't anticipate. We will be able to introduce doc comments in more positions in the future without a breaking change, so argument over where else we should support doc comments should ideally not delay acceptance of this RFC if we are confident that the currently proposed positions should be supported.
4. It partially duplicates the functionality of annotations, particularly given that we can use multi-line strings as annotation values.

## Alternatives

### Regular comments are good enough

Our position would be that documentation should be written in standard Cedar comments. 
If someone wants to attach a particular meaning to and write documentation tools around comments starting with `///`, they are free to do so, but we do not explicitly support this.
This requires no changes to Cedar, and is maximally flexible (standard comments can appear anywhere).

Asking users to develop their own documentation tools could resulted in multiple ad-hoc tools that are likely to fail to handle certain edge cases (e.g., `///` in a string) unless they substantially re-implement the Cedar parser.
Alternatively, we could provide the tools for generating documentation in this manner, but this implies standardizing the format and position of these comments, which is essentially what this RFC proposes, just without considering JSON formats.

Comments do not exist in the JSON format, so this alternative provides nothing for documenting a JSON formatted policy or schema.

### Annotations as documentation

We use the existing annotation feature to hold documentation.
Annotations already supports multi-line strings, so documentation can still be written without too much syntax overhead.

```cedar
@doc("
Allow users to create list and see the lists they own.

The `GetLists` action only returns the lists owned by that users, so this policy
does not allow users to see lists created by others.
")
@id("policy0")
permit (
    principal,
    action in [Action::"CreateList", Action::"GetLists"],
    resource == Application::"TinyTodo"
);
```

The Cedar AST (and JSON formatted EST) contains attributes, making it unambiguous what a comment is documenting,
and the Cedar Rust SDK provides functions for extracting annotations which could be used to build a documentation tool without re-implementing the Cedar parser.

The design of annotations only supports annotations at the start of policies, but we could extend this to support annotations in new positions as easily as we could introduce doc comments in those positions.
We would need to accept at least [RFC 48](https://github.com/cedar-policy/rfcs/pull/48) to document schema elements.

### Existing tools for literate programming

Rather of building a custom solution for Cedar, we could point users to existing literate programming tools.
One powerful option is [Entangled](https://entangled.github.io/) which would allow users to structure their documentation however they like.

The drawback to this alternative is that it would require that users install a second tool distributed separately from Cedar.
Different users may also decide to use different literate programming tools, meaning their policy and schema source may not be directly compatible without a pre-processing pass to remove the literate comments.
This concern could be addressed by explicitly recommending particular tools, or making directly Cedar parsers directly depend on Rust crates implementing literate programming.

Because this alternative amounts to using some tool as pre-processing pass before passing policies and schema to Cedar, it remains available to users regardless of what opinionated stance we choose for the Cedar language.
Users who want more sophisticated literate programming features can always use their tool of choice.
