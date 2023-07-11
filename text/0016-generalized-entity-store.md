# Generalized Entity Store

## Related issues and PRs

- Implementation PR(s): https://github.com/cedar-policy/cedar/pull/171, which is a pull request from https://github.com/prakol16/cedar

## Timeline

- Start Date: 2023-07-11
- Date Entered FCP:
- Date Accepted:
- Date Landed:

## Summary

Entity storage ideally should not be restricted to JSON files. We should either allow users to add their own custom storage methods or add support for some non-JSON common storage methods (e.g. databases) ourselves.

## Basic example


```rust
struct MyOwnDatabase {
    // ...
}

impl EntityDatabase for MyOwnDatabase {
    fn get_entity_of_uid(&self, uid: &EntityUID) -> Option<Entity> {
        // custom implementation which could e.g. make a request to a database
    }
}
```

This could be code written by users, or we could hide `EntityDatabase` and instead, there could be several storage solutions (other than the default JSON one) that we write ourselves.

## Motivation

  - Currently, every request reads the entire JSON file, reparsing all of the attributes, even though the overwhelming majority of requests will need to read only a few entries of the entity store. In general, with many entities, it may not even be feasible to load all of the entities into memory at once.

  - In the future, we can turn partial expression evaluations into queries so that we can efficiently find e.g. all of the photos that a user has access to. Ideally, we would leverage existing query languages such as SQL and existing storage solutions which are already optimized to respond to these kinds of queries efficiently, rather than try to rebuild this on our own.

  - Some users may already have infrastructure that uses databases or other storage methods for their applications. This makes integrating Cedar into existing software easier, because users are not boxed in to one particular storage format.


## Detailed design


We would generalize the authorizer to accept any `EntityDatabase`, not just `Entities`:

```rust
impl Authorizer {
    // old:
    pub fn is_authorized_old(&self, q: &Request, pset: &PolicySet, entities: &Entities) -> Response

    // proposed change:
    pub fn is_authorized<T : EntityDatabase>(&self, q: &Request, pset: &PolicySet, entities: &T) -> Response
}
```

Here is the current interface for `EntityDatabase` (see [the source](https://github.com/prakol16/cedar/blob/e5df52e118e378c2142aaa6d9a4781f0f67b8064/cedar-policy-core/src/entities.rs#L265) for more comments and the implementation of the trait for `Entities`):

```rust
pub trait EntityDatabase {
    /// Given a uid, get the corresponding entity if it exists
    /// The entity should already have an `ancestors` attribute which represents
    /// the transitive closure ancestors, not the direct parents
    fn get_entity_of_uid(&self, uid: &EntityUID) -> Option<Entity>;

    /// Returns whether this database should return expressions for unknown entities
    fn is_partial(&self) -> bool;
}
```

Essentially, we abstract the `Entities` struct by replacing the hash map with a function.

The other key change that needs to be made is to evaluate attributes lazily. This slightly changes the semantics (see the second point in "drawbacks" below) when an attribute evaluation would error.

There are many possible ways to implement this change. I've done it here by passing around a mutable parameter `EvaluatorCache` that keeps a reference to the entity and its evaluated attributes after the first load of the entity, and uses the cache wherever possible.

The [current implementation](https://github.com/prakol16/cedar/blob/e5df52e118e378c2142aaa6d9a4781f0f67b8064/cedar-policy-core/src/evaluator.rs#L81) only errors when an entity with a malformed (i.e. cannot be evaluated) attributed is loaded **and** that attribute is fetched (so if only other, valid attributes of the entity are referenced, no error will occur). This is another detail that could be changed (e.g. we could error when the entity is loaded, regardless of which attributes are fetched, if any attribute errors in its evaluation).

## Drawbacks

Why should we *not* do this?

- If we expose `EntityDatabase` and allow any user to write their own custom implementation, this reveals previously hidden information. This makes it more difficult to add changes/features that an `EntityDatabase` should support because it would become a breaking change.

- This changes the semantics of the evaluation when some entity contains a restricted expression that would result in an error. Previously, even initializing the evaluator would result in an error since all attributes were evaluated up front. Now, due to the laziness, an error only occurs if that entity is needed.

    - This change is essentially inevitable if we want to be able to handle requests without loading the entire entity store into memory.

    - This could be somewhat mitigated by offering a validation tool that checks to ensure no expression in an entity store errors when evaluated with respect to some particular set of extensions.

- We now have to assume the transitive closure really was computed correctly rather than being able to check ourselves (of course, we can offer a tool that does validation, but at request-time, we do not want to load the whole entity store, so we cannot check this on each request).

    - Again, this seems inevitable if we ever want to support respond to requests without loading the entire entity store.

- There is potential for abuse e.g. using infinite databases. Since the hash table lookup is replaced by a function call calling arbitrary (potentially user-written) code, there are no guarantees even on e.g. finiteness of the implicit database. This is an issue for validation.

## Alternatives

- We could simply provide a tool that converts a database to our own JSON format for the entity store. This helps users migrate to Cedar (point 3 in motivation) while avoiding all of the drawbacks from the previous section. However, this does not allow efficient partial evaluation queries leveraging SQL; more importantly it requires the entire entity store to be loaded for each request (and avoiding this is the primary purpose of this RFC).

- Similar to the above, we could allow multiple storage formats as part of the UI, all of which are implicitly converted to `Entities` by loading the entire database. This also mitigates all of the drawbacks from the previous section, while still satisfying motivations 2 and 3 (allowing efficient SQL queries on the entity store and helping users integrate Cedar into existing applications). However, it still does not address motivation 1 since the entire entity store needs to be loaded into memory for each request, which is very inefficient.

## Unresolved questions

- What exactly should the semantics be for entities which are loaded if some of the attributes error in their evaluation?

- How should we enforce transitive closure of the entities' `ancestors` property?

- To what degree should `EntityDatabase` be exposed to the user, so that they can write their own implementations?

- How should we integrate our current validation methods with this RFC?
