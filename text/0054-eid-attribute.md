# Include entity ID as a special attribute

## Timeline

- Started: 2024-02-22

## Summary

Add a pseudo-attribute `$id` that when applied to an entity reference returns its entity identifier.

## Basic example

`Action::"readFile".$id == "readFile"`

## Motivation

When an entity's EID is meaningful (and not a random, unique identifier), it could be useful for logic expressed in policies. For example, in RFC 53 we propose enumerated entity types, such as the following:
```
entity Course enum ["CMSC330", "CMSC351", "MATH241", "ENGL101"];
```
This schema definition indicates four `Course`-typed entities, i.e., `Course::"CMSC330"`, `Course::"CMSC351"`, `Course::"MATH241"`, and `Course::"ENGL101"`. You might like to write a policy that refers to the EIDs of these values, e.g.,
```
permit(
    principal in Group::"students",
    action == Action::"addCourse",
    resource is Course
) when {
    !(resource.$id like "CMSC*") && context.today < context.addDeadline ||
    context.today < (context.addDeadline-1)
}
```
This policy states that a student can add a non computer-science course any time up to the add-deadline, but computer science courses must be added a day before that.

You could similarly want to examine `Action` entities' EIDs:
```
permit(principal, action, resource)
when {
    action.$id like "read*" && prinicpal in resource.readers
}
```
Here the policy writer assumes that all "read" actions are prefixed by `read` in their EID.

## Detailed design

This proposal adds a new "pseudo attribute" `$id` on entity references such that `E::x.$id == x` (for all EIDs `x` and all entity types `E`).

Because `$id` not a normal attribute according to Cedar's grammar, it cannot be confused with a user-defined attribute of an entity. The `$id` "attribute" it not stored with a referenced entity's other attributes -- it is merely an alias for the entiy reference's EID. This means that if the entity does not have any declared attributes, it need not appear in the entity store.

The fact that the attribute is always equal to the EID can be useful for avoiding false alarms when performing policy analysis, since the invariant `E::x.$id == x` can be communicated to the analyzer.

## Drawbacks

Cedar policy writers are generally advised that EIDs should be (inherently unmeaningful) unique identiifers, rather than meaningful names. For example, we would advise against defining a `User::"AliceSmith"` UID in favor of designing `User::"XXX-YYY"`, where `XXX-YYY` is a unique identifier and `User::"XXX-YYY".name == "Alice Smith"`. This design ensures that if the existing Alice Smith deletes her account and a new Alice Smith creates one, the latter will get a different unique identifier and therefore not "inherit" the former's policies (if they have not been deleted in a timely fashion).

An exception to this advice is action names, e.g., `Action::"readFile"` or `Action::"sharePhoto"`. Another exception is enumerated entities (RFC 53), which essentially generalize what's available to actions to other entities. For these cases, making the EID available for examination would make sense. The risk is that a general `$id` feature could encourage the unwise design of making EIDs meaningful names when they should not be. 

## Alternatives

The obvious alternative is to do nothing: Users can  define an entity so that it has an `id` attribute (or equivalent, with another name) that is sure to match its EID. This approach is more work for users, and potentially leads to imprecise analysis results, but also does not encourage potentially bad practices.

Another alternative is to allow `$id` for `Action` entities and enumerated entities (if RFC 53 is accepted), but not for others. The EID is likely to be meaningful in these cases, and this RFC would make things easier for users, e.g., they don't need to add an entity with an explicit attribute to the entity store.