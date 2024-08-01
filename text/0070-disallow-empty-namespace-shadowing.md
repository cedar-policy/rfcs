# Disallow shadowing definitions in the empty namespace

## Related issues and PRs

- Reference Issues: Successor to [RFC 64]
- Implementation PR(s):

## Timeline

- Started: 2024-06-26

## Summary

In schemas, disallow definitions of entity types, common types, and actions that
would shadow definitions of other entity types, common types, or actions in the
empty namespace.

## Basic example

Borrowing and slightly tweaking the example from [RFC 64]:

```
entity User {
    email: String,
};

namespace Demo {
    entity User {
        id: String,
    };

    entity Account {
        owner: User,
    };
}
```

Today, this schema is accepted, and `Account.owner` is assumed to be
`Demo::User` and not the empty-namespace `User`.
As noted in [RFC 64], there is no way for the user to indicate that they intend
`Account.owner` to be the empty-namespace `User`.
Rather than add syntax to enable this (as proposed in [RFC 64]), this RFC
proposes to make this situation an error -- disallowing declaring a `User` type
in the `Demo` namespace when one already exists in the empty namespace.

## Motivation

Name shadowing is complicated and confusing; schemas using name shadowing may
look like they are doing one thing when they are actually doing another.
For Cedar policy and schema authors, this can cause misunderstandings and make
it more difficult to write correct schemas and policies.
By disallowing shadowing in the most egregiously ambiguous cases -- when the
name being shadowed was declared in the empty namespace -- we nudge users to
make the schema clearer, for instance by renaming a type, or moving a
conflicting empty-namespace declaration into a new namespace.

## Detailed design

We disallow shadowing a type or action in the empty namespace with a new
declaration in a nonempty namespace.
For entity and common types, we disallow this shadowing regardless of whether
the shadowed declaration is an entity or common type, and regardless of whether
the shadowing declaration is an entity or common type.
For actions, we only disallow shadowing other actions; we continue to allow an
action to have the same name as an entity or common type (in the same namespace
or in the empty namespace).

This RFC does not disallow shadowing altogether; in particular, it does not
disallow shadowing a entity typename with a common typename in the same namespace,
as originally proposed in [RFC 24] (see "Disambiguating Types in Custom Syntax",
and in particular Rule 5 in that section):
```
// Allowed today, and still allowed after this RFC
namespace NS {
    entity User {
        id: String,
    }
    type User = User;
    // or, more confusingly, type User = String;
}
```

This RFC also does not disallow shadowing the names of primitive or extension
types, where you can still refer to the shadowed type using `__cedar`, again as
explained in [RFC 24].
Conceptually, primitive and extension types are not declared in the empty
namespace; they are declared in the `__cedar` namespace, and implicitly imported
as part of a prelude.
That is how we could explain (e.g. in the Cedar docs) why the rule is different
for shadowing entity/common types and shadowing primitive/extension types.
(Internally, another reason for continuing to allow shadowing
primitive/extension types, is that we want to be able to introduce new extension
types without any possibility of breaking existing schemas.)

This RFC does not change anything about [cedar#579].
We still plan to implement [cedar#579], which allows users to refer to types in
the empty namespace, in cases where they are not shadowed.

This RFC does apply the new restriction uniformly in both the human and JSON
schema syntaxes.
The motivation and situation is the same in both syntaxes for the case of an
entity typename shadowing an entity typename, and for the case of a common
typename shadowing a common typename.
For the case of an entity typename shadowing a common typename or vice versa,
this RFC still proposes to disallow in both syntaxes, even though these
situations are not ambiguous in the JSON syntax, which distinguishes between
entity type and common type references.
See [this RFC discussion thread](https://github.com/cedar-policy/rfcs/pull/70#discussion_r1659120108).

## Drawbacks

### Drawback 1

The motivation section for [RFC 64] claimed that
> Users justifiably expect that they can refer to any declared typename (in any
> namespace) from any position in the schema, by writing a fully qualified name.
> The fact that [RFC 24] did not provide a way to refer to typenames in the empty
> namespace by using some kind of fully qualified name seems like an oversight,
> and should be corrected for consistency.

This RFC does not address that motivation, and effectively counterclaims that
users don't actually expect this.

### Drawback 2

If [RFC 69] or something similar are eventually accepted, the error in this RFC
may not be so easily avoided, if the empty-namespace definition is part of a
third-party library being imported by the user.
In that case, the user couldn't easily rename the empty-namespace type or move
it into a nonempty namespace.

To address this drawback, we should guide library authors to not declare library
types or actions in the empty namespace (and instead, e.g., declare them in a
namespace named after the library).
We could even codify that rule, requiring that all libraries have a name and all
declarations in the library live in the corresponding namespace, or alternately,
implicitly prefixing all library declarations with the library name as a
toplevel namespace.
Many existing package systems have similar rules or mechanisms.

## Alternatives

[RFC 64] proposed instead introducing new schema syntax to allow users to refer
to entity and common types in the empty namespace whose names are shadowed by
declarations in the current namespace.
(RFC 64 could be naturally extended to actions as well.)

Introducing new schema syntax is a major change, and in the discussion on
[RFC 64] we have been, to date as of this writing, unable to agree on a syntax for
this which is clear and acceptable to everyone.
On the RFC thread and in offline discussions, the leading candidates for such a
syntax are currently (as of this writing) `::User`, `root User`, or
`__cedar::Root::User` (reusing the `__cedar` namespace reserved in [RFC 52]).
But it seems apparent that none of these options are immediately intuitive to
all users; if we were to introduce such a syntax, we run the risk of
complicating the schema syntax only to not actually clarify the situation
because the new syntax is still unclear.

Finally, this shadowing situation is viewed as an unlikely edge case in general,
and certainly one that can easily be avoided by users (by renaming types/actions
or moving empty-namespace declarations into a namespace).
It seems expedient to resolve this in the easiest, clearest way possible.
This RFC proposes that disallowing the premise is easier and clearer than
designing and implementing new schema syntax that will only be used in an
unlikely edge case.


[RFC 24]: https://github.com/cedar-policy/rfcs/blob/main/text/0024-schema-syntax.md
[RFC 52]: https://github.com/cedar-policy/rfcs/blob/main/text/0052-reserved-namespaces.md
[RFC 64]: https://github.com/cedar-policy/rfcs/pull/64
[RFC 69]: https://github.com/cedar-policy/rfcs/pull/69
[cedar#579]: https://github.com/cedar-policy/cedar/issues/579
