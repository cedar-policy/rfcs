# Enumerated Entity Types

## Timeline

- Started: 2024-02-20

## Summary

Extend schemas to support declared enumerations of entity-typed values, analogous to how schemas can currently be used to enumerate a finite list of `Action`-typed values.

## Basic example

An enumerated entity type is declared as a normal entity type, but includes the keyword `enum` followed by the list of legal entity UIDs. Here is a simple example:
```
entity User;
entity Color enum ["red", "blue", "green"];
entity Task {
    owner: User,
    name: String,
    status: Color
};
action UpdateTask
    appliesTo { principal: [User], resource: [Task] };
```
These data definitions could be used in policies such as 
```
permit(
    principal,
    action == Action::"UpdateTask",
    resource)
when {
    principal == resource.owner &&
    resource.status != Color::"red"
};
```

## Motivation

Enumerated types are useful when you have a fixed set of possible values, and the only thing you want to do with the values is compare them for equality. While you could effectively treat an entity type as an enumeration now, without declaring it in a schema, you gain some benefits by declaring it:

- The validator can error on uses of illegal enumerated values, e.g., flagging the typo `resource.status != Color::"Red"` in the `when` clause in the basic example. 
- When using a policy analyzer, it can always generate request and entity store instances where the enumerated entity type has declared-valid values, rather than random UIDs.
- When using an IDE or web-based policy builder, the enumeration can inform auto-completion suggestions. For the basic example above, in an auto-completing IDE writing `resource.status != ` ... would pop up the three options.

## Detailed design

An enumerated entity `Foo` is declared by writing
```
entity Foo enum [ … ];
```
where `[` … `]` is the list of allowed values. These values can be strings or identifiers.

In the JSON format for schemas, you would write
```
"entityTypes": {
    ...
    "Foo": {
        "enum": [ … ]
    },
    ...
}
```

You can use an enumerated entity type anywhere you can use a normal entity type. Since an enumerated entity cannot have attributes, nor can it have ancestors in the entity hierarchy, all you can do with it is test it for equality (e.g., with `==` or `contains`).

The policy validator confirms that any enumerated entity literal in a policy is valid. The request validator does likewise. The entity store validator confirms that enumerated entities _do not_ appear in the store, or if they do, they have no attributes or ancestors. It also confirms that the declared enumerated entity type has no invalid values, and references to entities of the enumerated type are valid. The schema-based entity parser likewise confirms that parsed-in enumerated entity values are valid.

As another example, consider the following.
```
entity Application enum [ "TinyTodo" ];
entity User in [ Application ];
action CreateList
    appliesTo { principal: [User], resource: [Application] };
```
This is a generalization of our TinyTodo example from RFC 24, where we can refine the definition of `Application` to indicate that it has a single value, `Application::"TinyTodo"`. This allows the validator to catch typos in policies, such as the following.
```
permit(
    principal,
    action in [Action::"CreateList"],
    resource == Application::"TinyTODO"
);
```
Likewise the request validator would flag a request with `Application::"TinyTODO"` as its resource, and it would flag the passed-in entity store if it contained such an illegal value.

## Drawbacks

One reason not to do this is that it's not particularly full featured---you cannot do anything useful with an enumerated entity value in a policy other than compare it for equality. We consider more full-featured extensions in the alternatives below, but these have drawbacks of their own. The functionality could be easily extended later, depending on how things play out.

## Alternatives

### Alternative A: Enumerated primitive values

We previously proposed, in [RFC 13](https://github.com/cedar-policy/rfcs/blob/enums/text/0013-schema-enums.md), declaring a finite set of primitive values (strings, numbers, etc.) as an enumerated type. The [killer objection to the RFC](https://github.com/cedar-policy/rfcs/pull/13#issuecomment-1786170514) is that it introduces subtyping (you want to use the enumerated type of string as both the enumeration and the string, e.g., with `like`), which is a significant complication for policy analysis. The present proposal is not problematic for analysis as enumerated entities can be encoded like any entity, but with added ground constraints limiting what form their UIDs can take on.

### Alternative B: Enumeration as a distinct concept

Rather than specify a particular entity type as an enumeration, we could define a new concept of enumeration as another kind of primitive type. Here is a notional schema:
```
enum type Color = red | blue | green;
entity Task {
  name: String,
  status: Color
};
```
Here is a notional policy:
```
permit(
    principal,
    action == Action::"UpdateTask",
    resource)
when {
    resource.status != Color.red
};
```
This syntax is similar to what's provided for Java `enum`s. 

The benefit of this approach is that it may feel a little more natural than representing a concept, like a color, as a set of legal entity values. It would also be easy to encode this approach in a policy analysis.

The main drawback of this approach is that it introduces a new primitive type to the language that does not make much sense without schemas. Recall that for Cedar, validation with a schema is _optional_. We'd allow users to include any random enumerated identifiers (like Scheme-style _symbols_) in policies which, without validation, would fail equality checks at run-time.

The proposed approach that lists particular entity values as an enumeration makes no change to the language, leveraging the existing entity type concept. So policies without schemas still make sense. With the added schema, there is additional benefit when validating and constructing reasonable policies.

### Alternative C: Enumerated entities with hierarchy

Enumerated entities as proposed are limited in their functionality and specificity. We could extend them. For example:
```
entity Application enum [ "TinyTodo" ];
entity RequestEntity enum [ "principal", "resource" ] in [ Application ];
entity User in [ Application ];
action CreateList
    appliesTo { principal: [User], resource: [Application] };
action GetLists
    appliesTo { principal: [User, RequestEntity::"principal"],
                resource: [Application]};
```
This differs from some earlier examples in the following ways:
1. Enumerated entities can have parents in the entity hierarchy, e.g., as with `RequestEntity`, and can be parents themselves, e.g., as with `Application`
2. Enumerated entities can appear as _singleton types_, e.g., as `RequestEntity::"principal"` in the definition of action `GetLists`.

Both of these extensions are similar to what's available for `Action`s right now, but generalized to arbitrary entity types. We know that difference (1) would be directly useful in the [TinyTodo example application](https://github.com/cedar-policy/cedar-examples/tree/main/tinytodo), in particular.

You could also imagine allowing enumerated entity types to have attributes assigned to particular values.

One drawback of this approach is that it creates added complication for both the validator (e.g., to handle singleton types) and the analyzer (e.g., to deal with the more general hierarchy constraints). 

Another drawback is that it adds complication to the entity store: Once you add hierarchy constraints and attributes, you need to create actual entities to include with policy requests (or extract them from the schema at request-time). The current proposal does not require that.