# Add Apply keyword to Cedar language

## Related issues and PRs

- Reference Issues: 
- Implementation PR(s): 

## Timeline

- Started: 2024-01-25

## Summary

Add a keyword that allows denoted policy statements to have no impact on the
authorization decision, yet be logged in the diagnostics for later annotation
aggregation.

## Basic example

```cedar
@annotation("value")
apply (
    principal,
    action,
    resource
);
```

## Motivation

I want to be able to create policy statements that will add annotations while
not affecting the authorization outcome.  Here are some examples:

1. I want to be able to require MFA anytime someone accesses a certain table.
However, I want to be able to define permission for this table elsewhere.

2. I want to be able to send out an email everytime something is denied.
However, I want to be able to define what things are forbidden elsewhere.

3. I want to be able to send out an email regardless of if a specific event
is allowed or denied.

## Detailed design

There are three cases that are added to the language syntax:

1. Apply on permit

```cedar
@mfa("mfa prompt text")
apply on permit (
    principal,
    action == Postgres::Action::"select",
    resource == Postgres::Table::"example.com:5432/db"
);
```

2. Apply on forbid

```cedar
@email("alert@example.com")
apply on forbid (
    principal,
    action,
    resource
);
```

3. Always apply

```cedar
@email("alert@example.com")
apply (
    principal,
    action,
    resource in Postgres::Table::"example.com:5432/db"
);
```

The apply keyword will cause all matching policy statements to be added to the
diagnostics, while not impacting the authorization decision in any way.

### Changes required to parser/AST

- Update grammer to support `apply on permit` `apply on forbid` `apply` in
  addition to the existing `forbid` and `permit`

### Changes required to evaluator

- Policies that are categorized as `apply` would not impact the decision, while matches
would be added to the diagnostic.

## Drawbacks

Why should we *not* do this? Please consider:

- this does add the `apply` and `on` keyword to the grammar, thus increasing the
complexity of the Cedar language
- this may have some impact on the ability to short-circuit policy decisions,
since all apply statements need to be checked to be added to the diagnostics

## Alternatives

### Use `@apply` annotations - one pass

I have considered using an annotation `@apply("after")` as a way of implementing
this.  This works for the `apply on permit` case, although it changes the
outcome of the authorization event.  By taking into consideration the
annotation, I am able to reverse the decision to `deny` if all matching policies
are annotated with `@apply("after")`.

This alternative does not work with the `forbid` case because any matching
forbid statements will cause the entire request to be denied, regardless of if
the principal should be permitted.

This alternative does not support the general case of applying regardless of
permit / forbid.

This alternative requires no changes to the cedar engine, as it is implemented
outside of the engine.

### Use `@apply` annotations - two pass

Similar to the previous alternative, but in this one, the first call to
is_authorized would only include the policy statements that do not have an
`@apply` annotation.  This would result in the correct allow/deny decision.

The second call to is_authorized would include only the relevant `@apply`
policies.  In the case of an `allow` decision, only the `permit` policies would
be run.  In the case of a `deny` decision, only the `forbid` policies would be
run.  This would result in a list of matching policies, while not affecting the
original decision in any way.

This alternative would work correctly for both the `apply on permit` and
`apply on forbid` case.

This alternative does not support the general case of applying regardless of
permit / forbid.

A drawback in this case would be the alteration of the policy numbers in the
diagnostics, but further post-processing could correct that.

This alternative requires no changes to the cedar engine, as it is implemented
outside of the engine.

### Use the partial evaluation extension

Using partial evaluation, a policy itself could contain the requirement.  If
the requirement was unknown, then the caller could trigger an external event
to get the result.  Then the policy could be evaluated again once the value is 
known.  In the example below, `context.mfa` is the unknown.  The annotation
serves as meta-data used by the caller.

```cedar
@mfa("mfa prompt text")
permit (
    principal, 
    action == Postgres::Action::"select", 
    resource == Postgres::Table::"example.com:5432/db" 
) when { 
    context.mfa == true 
};
```

In more complicated cases, such as:
```cedar
when { context.mfa == false && context.other == "value" }
```
it may be that an MFA would be triggered, and even if the user approves the
request the end result would be `deny` due to other constraints in the when
clause.

This alternative requires no changes to the cedar engine, as it is implemented
outside of the engine.  It does depend on the partial evaluation extension.

### Use more explicit policies

Instead of depending on a single statement to define this behaviour, it is
possible to accomplish this with a more explicit set of policy:

```cedar
@mfa("mfa prompt text")
forbid ( 
    principal, 
    action == Postgres::Action::"select", 
    resource == Postgres::Table::"example.com:5432/db" 
) when { 
    context.mfa == false 
};

permit (
    principal, 
    action == Postgres::Action::"select", 
    resource == Postgres::Table::"example.com:5432/db" 
);
```

In this case, the first decision would be `deny` due to `context.mfa` being
false.  However, the annotation would hint to the caller that an MFA should
be triggered.  A second call could be made after the context is updated
to get the final decision.

It's worth noting that if the `permit` clause is omitted, an end user would be
required to mfa, but they would still be denied during the second authorization
attempt.

This alternative requires no changes to the cedar engine, as it is implemented
outside of the engine.

### Other possible names

A variety of names could work in place of `apply` for this feature.  Here are
a few possibilities:

- apply
- log
- info
- inform
- advise
- annotate
- decorate
- observe
- watch
- trigger
- notify

## Unresolved questions

None at present.
