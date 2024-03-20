# Policy and Schema Doc Comments

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2024-02-28

## Summary

Cedar should support documentation comments (doc comments) on both policy and schema elements.
Doc comments are a refinement to our current comments, distinguished by a third `/` and restricted in where they appear.
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

Doc comments may also be placed immediately prior schema elements to document the purpose of entity types and actions.

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

The syntax of Cedar policies is designed to be easy to read and understand, but even the cleanest code requires some amount of documentation. 
Cedar naturally supports comments so policy authors can leave remarks in their code.

This RFC is largely motived by [this comment on RFC 48](https://github.com/cedar-policy/rfcs/pull/48#issuecomment-1937735924).
It also addresses the request in [Cedar issue 660](https://github.com/cedar-policy/cedar/issues/660) for comments in the JSON policy format. 

## Detailed design

### Policies

* Documentation for the policy as whole appears before the policy effect. It may be anywhere in relation to annotations on that policy.

### Schema

### Improperly placed commented

For an initial, backwards compatible, change, comments starting with `///` that are not in a legal position for doc comments will be parsed as standard comments.
This is likely to cause some confusion if users think a particular comment is a document comment but it is not parsed as such, but it allows us to release this feature without a breaking change to the Cedar language.
We may emit a warning if the parsers are updated to support warnings emitting warnings.
We can then make this an error in a future major version of the Cedar.

## Drawbacks

1. This is a significant change to the parsers for policies and schema, both in their human readable and JSON forms.
   There is always a possibility of mistakes when making changes to our parsers.
2. This will eventually be a breaking change to the policy format.
   Although, as noted above, we don't need to make this change immediately.
3. We are likely to find that users want to add doc comments in a position we didn't anticipate. 
4. It partially duplicates the functionality of annotations.

## Alternatives

### Alternative doc comment syntax

Choosing to use Rust style doc comments feels natural after developing Cedar in Rust, but we should at least consider alternative syntax options.
In particular, we could avoid making a breaking by using block style dec comments (`/** ... */`).

### Regular comments are good enough

Our position is that documentation should be written in standard Cedar comments. 
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
and the Rust API provides functions for extracting annotations which could be used to build a documentation tool without re-implementing the Cedar parser.

The drawback to this solution is that annotation can currently only appear at the start of policies.
We would need to accept [RFC 48](https://github.com/cedar-policy/rfcs/pull/48) before we could document schema elements.
Annotations are also very limited in where they can appear.
The RFC proposes allowing doc comments on individual scope conditions, but annotation do not support this granularity.
If taking this alternative, we should consider extending annotations to have at least some of this flexibility.

### Existing tools for literate programming

Rather of building a custom solution for Cedar, we could point users to existing literate programming tools.
One powerful option is [Entangled](https://entangled.github.io/).
This tool would allow users to structure their documentation however they like, even rearranging definitions and intermixing policy and schema definitions.

````
Allow users to create list and to see what lists they own.
The `GetLists` action only returns the lists owned by that users, so this policy
does not allow users to see lists created by others.
```{file=policies.cedar}
@id("policy0")
permit (
    principal,
    action in [Action::"CreateList", Action::"GetLists"],
    resource == Application::"TinyTodo"
);
```

This entity defines our central user type
```{file=schema.cedarschema.json}
entity User { 
    <<user-attributes>>
}
```

The location where this user works. E.g., ABC17 or XYZ77.
```{#user-attributes}
location : String,
```

A numeric level describing this users job.
```{#user-attributes}
location : String,
```
````

The drawback to this alternative is that it would require that users install a second tool distributed separately from Cedar.
Different users may also decide to use different literate programming tools, meaning their policy and schema source may not be directly compatible without a pre-processing pass to remove the literate comments.
This concern could be addressed by explicitly recommending particular tools, or making directly Cedar parsers directly depend on Rust crates implementing literate programming.

Because this alternative amounts to using some tool as pre-processing pass before passing policies and schema to Cedar, it  available to users regardless of what opinionated stance we choose for the Cedar language.
Users who want more sophisticated literate programming features can always use their tool of choice.
