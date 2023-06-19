- Start Date: 2023-06-16 
- Target Major Version: 3.0
- Reference Issues: https://github.com/cedar-policy/cedar/issues/99
- Implementation PR: https://github.com/cedar-policy/cedar/pull/79

# Summary

Policy authors may not always know every attribute that may exist for every entity type in their schema,
or they may want to benefit from some amount of validation before they have finished (or even begun) enumerating every entity type, action, and every attribute for these entity types and action contexts.
This RFC proposes extending the Cedar policy validator to operate in an unsound mode
that would enable detecting some errors in policies with an incomplete or even entirely empty schema.
The proposed validation mode does not attempt to detect all type error.
A policy which validates without a schema or with a partial schema may still encounter errors during evaluation.

Partial schema validation aims to permit three kinds of schema incompleteness:
1. Incomplete enumeration of entity types or actions.
2. Incomplete attributes for record types.
3. Incomplete entity hierarchy specification.

# Basic example

The following policy will always result in a runtime error when evaluating the `>` operator.
This operator is defined on `Long`s, but the policy attempts to apply it with a string as the right operand.

```
permit(principal, action, resource) when {
  principal.access_level > "5"
};
```

The Cedar policy validator can detect this error,
but it will currently raise another error because the attribute `access_level` is not defined for the principal entity type.
With partial schema validation, we will assume that the principal entity type may have attributes which we do not know about,
so accessing `access_level` is not an error.
We will still  detect the error due to the application of `>` since the error arises regardless of the type of `access_level`.
Fixing the errors by replacing `"5"` with `5` will allow the policy to pass partial schema validation.

The partial schema validator does not know if `access_level` will be present during policy evaluation,
and it does not know if the attribute will be a `Long` if it is present.
When either of these is not the case, there will be an error during evaluation that partial schema validation cannot detect ahead of time.

# Motivation

We want to provide some of the benefits of policy validation to Cedar users who have not written or may not be able to write a schema. 
Detecting any amount potential errors during development is preferable to discovering the errors later,
but we strive to provide a guarantee of soundness which partial schema validation cannot provide on its own.
Because of this, our second motivation is to provide a path towards adoption of validation with a complete schema,
so Cedar users who may have been discouraged by the initial investment of time required to write a complete schema can build one incrementally.

# Detailed design

As stated earlier, partial schema validation supports schema with three kinds of incompleteness:
entity types and actions declarations,
attributes declarations for record types,
and entity type and action hierarchy specifications.
The following subsections describe the design of each in detail.

## Missing entity types and actions

Policies may reference entity types and actions which are not declared in the schema.
Undeclared entity types and actions are treated as incomplete according to the second two kinds of incompleteness.
At the extreme, it should be possible to have a schema that does not declare any entity types or actions.

This policy will validate with an empty schema that does not declares either of the entity types or the action.
Partial schema validation will detect any trivial type errors like the one in the first basic example if they appear in the body of the policy.

```
permit(principal == User::"alice", action == Action::"view", resource == Photo::"vacation.jpg")
```

## Missing attributes

A record type, including when written as part of entity type or action context attributes, does not need to list every attribute in that record.
In the basic example shown earlier an error was reported for an incorrect operand
while ignoring an access to an undeclared attribute.
After fixing the error, we are left with a policy that is accepted by partial schema validation even when there is no schema available.

```
permit(principal, action, resource) when {
  principal.access_level > 5
};
```

The policy now passes partial schema validation because `access_level` might exist for the principal entity and it might be a value of type `Long`,
but we do not *know* that both of these are always true.
When either of these is not the case, there will be an error during evaluation that partial schema validation cannot detect ahead of time.

### Implementation: Bottom Type

We implement typechecking for an access to an undeclared attribute by assigning all undeclared attributes the bottom type.
The bottom type function like the [TypeScript `any` type](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#any).
It is used to ensure that the type is allowed to appear in any expression without causing additional type errors.
The `>` operator expects a value of type `Long` as its operand.
It will in fact accept any subtype of `Long`, and the bottom type is a subtype of every type, so it accepted.

By using the bottom type, we admit some inconsistent expressions.
For example, `principal.access_level > 5 && principal.access_level like "admin*"` is inconsistent because it requires that the attribute is both a `String` and a `Long`.
This is not possible for any Cedar value, but the bottom type is nonetheless accepted in both locations.

Importantly, this problem only exists for partial schema validation.
The standard validation mode does not assign the bottom type to undefined attributes, instead reporting an error immediately.

### Partial Attribute Information

The example so far demonstrates validation without a schema,
but partial schema validation can use information from a partial schema to detect further errors.
Suppose we know that the `principal` is a `User` entity and that for these entities `access_level` is not a `Long` but instead is a `String`.
We could add the following entity type entry to the schema.

```
"User": {
  "shape": {
    "type": "Record",
    "attributes": {
      "access_level": {"type": "String"}
    },
    "additionalAttributes": true
  }
}
```

We can now typecheck the policy under the assumption that `access_level` is a `String`,
so the partial schema validator will report an error,
this time for the left `>` operand.
Including `"additionalAttributes": true` in the schema informs the validator that the listed attributes are still incomplete,
so an expression `principal.role == "Admin"` would still be accepted by the validator.

Alternatively, we might have complete information about the attributes present for `User` entities.
When we know that `access_level` does not exist, the `shape` for the principal entity type can include `"additionalAttributes": false` to specify that there are no undeclared attributes for this entity type.
An access to `access_level` is then immediately an error.
Note that it is not possible to specify that a particular attribute does *not* exist while leaving the possibility that *other* attributes may exist.
If the entity type has some other attributes, they must be declared at this point to avoid false positives in policies accessing those attributes.

The following declaration for the `User` entity type states that a `User` entity will have exactly one attribute `admin_level`.
Given this schema, the example policy will be rejected because it contains an access to an attribute that does not exist.

```
"User": {
  "shape": {
    "type": "Record",
    "attributes": {
      "admin_level": {"type": "String"}
    },
    "additionalAttributes": false,
  }
}
```

## Missing hierarchy

Entity types and actions may be a member of entity types (actions, respectively) beyond those they are explicitly declared to be members of in the schema.

The following policy checks if the principal is a member of the group `Group::"admins"`.

```
permit(principal in Group::"admins", action, resource);
```

Suppose that `Group` is not listed in the `memberOfTypes` list for the principal entity type.
Seeing this, the standard validator would know that the type of the `in` expression is `False` and raise an error stating that this policy can never evaluate to `true`.
Using partial schema validation, we can specify that the `memberOfTypes` list is incomplete as in the following declaration.
The partial validator will also assume that any undeclared entity type always has an incomplete `memberOfTypes` list.

```
"User": { "additionalMemberOfTypes": true, }
```

With this information, the validator will assume that the principal may be in any group,
so any `in` expression with a `User` entity as the left operand will have type `Boolean` instead of `False`.
This will cause the validator to accept the policy so long as the rest of the policy typechecks.

## Schema Format

We extend the schema format to support the above example schema.
Specifically, we add the following properties to the JSON:

* Any record type, including the record types for entity attributes and action context attributes, may include `"additionalAttributes": true` to specify that values having that record type may have attribute other than those declared.
* An entity type declaration may include `"additionalMemberOfTypes": true` to specify that entities with that entity type may have ancestor entity types other than those in its  `memberOfTypes` list.
* An action definition may include `“additionalMemberOf”: true` having the same purpose as `additionalMemberOfTypes` for entity type, but applying to the `memberOf` list.

All properties added to the schema default to `false`,
so an entity declaration in a schema read by the partial schema validator will be interpreted the same as when read by the standard validator.


## Effect on the standard validator

This change does not necessarily require any change to the behavior of the standard validator,
but the additions to the schema format could be soundly supported.
An entity or record with `"additionalAttributes": true` would have an open attributes record,
meaning only that a `has` expression applied to it could only have type Boolean and not False.
This would not allow access to undeclared attributes in the standard validation mode.
Similarly, `additionalMemberOfTypes` and `additionalMemberOf` would mean that an `in` expression involving the effected entity types or actions would have type Boolean rather than False
while still reporting an error for any undeclared entity types appearing in policies.

# Drawbacks

The primary drawback to this approach to partial schema validation is that it does not provide any soundness guarantees which could be provided by inference based approach to partial schema validation.
When partial schema validation as proposed accepts a policy, it gives no guarantees about what error could occur when evaluating the policy.

By adding this form of partial schema validation, we may also make it more difficult to add schema type inference later.
A sound, type inference based, approach to partial schema validation would report _more_ type error than this proposal,
so it could not be used as a drop-in replacement.
We would instead need to offer it as a separate validation mode,
but supporting multiple partial schema validation options could be confusing for users.

# Alternatives

* Policy validation is not required to use Cedar,
  so we could continue to support validation for only users who are able to provide a complete schema.
* We could design an implement a type inference algorithm for Cedar.
