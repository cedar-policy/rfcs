# Create a batch version of is_authorized

## Related issues and PRs

- Reference Issues:
  [k9securityio/cedar-py#13](https://github.com/k9securityio/cedar-py/issues/13)
- Implementation PR(s): <!-- (leave this empty) -->

## Timeline

- Start Date: 2023-07-11
- Date Entered FCP: <!-- (leave this empty, update when the PR enters FCP) -->
- Date Accepted: <!-- (leave this empty, update when the PR is merged) -->
- Date Landed:
  <!-- (leave this empty, update when the implementation is in a stable
  release) -->

## Summary

Initial experiments with language bindings show that while calling
`is_authorized` for single requests is adequately performant, doing a full
round-trip many times to satisfy a single higher-level operation incurs
significant overhead ("consistently 2 orders of magnitude greater \[than the
cost of calling the function in Rust]").

As a result, we propose a batch version of `is_authorized` that can accept a
list of authorization requests and provides a matching list of responses,
eliminating the repeated round-trip overhead.

## Basic examples

### All or nothing

In this example, all of the requests in the batch must be allowed in order for
the action to be taken. If any request is denied, the action is rejected.

A concrete example of this would be a higher-level action that is composed of
multiple actions, potentially on multiple resources. Here we show a
`score_photo` composite operation that requires the principal to have both the
`view` and `score` permissions on a photo in order for it to be successful.

```rust
const ACTION_VIEW: EntityUid = ...;
const ACTION_SCORE: EntityUid = ...;

fn score_photo(principal: EntityUid, photo: EntityUid, context: Context, score: u8) {
    let view_request = Request::new(Some(principal), Some(ACTION_VIEW), Some(photo), context);
    let score_request = Request::new(Some(principal), Some(ACTION_SCORE), Some(photo), context);
    let requests = vec![view_request, score_request];

    // not shown: obtaining policy set and entities

    let authorizer = Authorizer::new();

    let responses = authorizer.is_authorized(&requests, policy_set, entities);

    // all requests must be allowed to take action; if any
    // are denied then reject the action
    if responses.iter().any(|&x| x.decision() == Decision::Deny) {
        // reject
        return
    }

    // apply score
}
```

### Filtering on authorization result

In this example, `list_photos` is tasked with returning a list of photos that
the principal has access to.

```rust
const ACTION_LIST: EntityUid = ...;

fn list_photos(principal: EntityUid, context: Context) -> Vec<Photo> {
    // not shown: obtaining list of photo IDs
    let photo_ids: Vec<EntityUid> = ...;
    let requests = vec![];

    for id in photo_ids {
        requests.push(Request::new(Some(principal), Some(ACTION_LIST), Some(id), context))
    }

    // not shown: obtaining policy set and entities

    let authorizer = Authorizer::new();

    let responses = authorizer.is_authorized(&requests, policy_set, entities);

    let photos = vec![];

    // we should have a request for each photo ID
    // (in order) and a response for each request,
    // so transitively we have a response for each
    // photo ID.
    for (photo_id, response) in photo_ids.iter().zip(responses.iter_mut()) {
        match response.decision() {
            Decision::Allow => {
                let photo = ...;
                photos.push(photo)
            },
            Decision::Deny => {
                // skip
            }
        }
    };

    photos
}
```

## Motivation

At time of writing at least three language bindings exist
([ref](https://github.com/cedar-policy/cedar-awesome#language-and-platform-integrations))
that provide mechanisms to call the Cedar Authorizer's
[`is_authorized` method](https://github.com/cedar-policy/cedar/blob/d9201161d8ce45e015c8bcb1cd4191c11039709a/cedar-policy/src/api.rs#L300).

While the majority of requests likely operate on a single resource and can be
handled efficiently by the current implementation, some requests (especially
`list` requests) may need to check authorization against multiple resources, and
it is inefficient to do a full round-trip for every request. Similarly, a
higher-level operation may involve multiple lower-level actions on multiple
resources.

In naive comparison testing with the
[k9securityio/cedar-py](https://github.com/k9securityio/cedar-py)
`is_authorized` implementation against a
[very naive `is_authorized_batch` implementation](https://github.com/glb/cedar-py/commit/98bf3e1fa2e90bb6f7326cbd846a3293fdbd960b),
I observed speedups of at least 5x for even simple cases, as documented in
[k9securityio/cedar-py#13](https://github.com/k9securityio/cedar-py/issues/13).

@skuenzli also
[reported](https://github.com/k9securityio/cedar-py/issues/13#issuecomment-1629790294)
that:

> The time observed in Python is consistently 2 orders of magnitude greater than
> the authorizer.is_authorized call. These particular requests use a simple
> policy, a simple schema, and ~170 entities.

The initial thought was to simply create an `is_authorized_batch` API for the
`cedar-py` Python binding, but in discussion in the Cedar Policy Language Slack
there was support from @aaronjeline and @andrewmwells-amazon for exposing this
API in Cedar core so that it could be picked up more easily by other language
bindings, as they expect those bindings to have similar needs and performance
concerns.

## Detailed design

### Accept a batch of requests with the current shape

This approach creates a new `is_authorized_batch` function, similar to the
`is_authorized` function, that accepts a list of `Request` structs
([ref](https://github.com/cedar-policy/cedar/blob/d9201161d8ce45e015c8bcb1cd4191c11039709a/cedar-policy/src/api.rs#L2006))
and returns a list of `Response` structs
([ref](https://github.com/cedar-policy/cedar/blob/d9201161d8ce45e015c8bcb1cd4191c11039709a/cedar-policy/src/api.rs#L338)),
which might have an implementation something like this:

```rust
impl Authorizer {
    /// Returns a vector of authorization responses for the input vector of requests
    /// with respect to the given `PolicySet` and `Entities`.
    ///
    /// The order of responses matches the order of requests.
    pub fn is_authorized_batch(
        &self,
        requests: &Vec<Request>,
        policy_set: &PolicySet,
        entities: &Entities,
    ) -> Vec<Response> {
        let mut responses: Vec<Response> = vec![];

        for request in requests {
            let response = self.is_authorized(request, policy_set, entities);
            responses.push(response);
        }

        responses
    }
}
```

In the special case where the input `requests` list is empty, the function
should be a no-op and return an empty list.

An advantage of this alternative is that it gives full flexibility to the API
consumer in how they structure and batch requests.

A disadvantage of this alternative is that for the initial motivating case of a
`list` operation on a set of resources the principal, action, and context will
be duplicated across the list of requests. However, this is not necessarily a
fatal disadvantage, as a language binding author could write optimized versions
of the binding that translates the special cases on the Rust side of the binding
and generates the list of `Request` objects from a more-optimized intermediate
representation.

## Drawbacks

1. Expanding the API surface can be confusing to consumers, as they may not know
   which of the `is_authorized_*` methods best meets their needs.

2. If this proposal is implemented too conservatively by simply duplicating the
   `is_authorized` function and dropping in some code to iterate over the input
   requests, having both `is_authorized` and `is_authorized_batch` APIs could
   result in double the amount of code to maintain.

3. If this proposal is implemented too aggressively by making `is_authorized`
   accept a batch of requests and not maintaining the existing function
   signature, existing Cedar applications would need to be updated.

## Alternatives

### Do nothing

It is entirely acceptable to do nothing in the Cedar core to accommodate this
request. The published `is_authorized` API is sufficient, and language binding
authors can independently create batch implementations to optimize for their
needs as they discover them.

A disadvantage of encouraging independent evolution is that bindings may
diverge, causing barriers for developers who may want or need to use multiple
language bindings in their work.

### Accept a modified request that has multiple resources but uses the same principal, action, and context

This approach addresses the motivating need of optimizing authorization
evaluation for `list` operations on a batch of resources and goes no further. A
simple embodiment of this approach might start with something similar to the
following `struct` definition:

```rust
pub struct BatchRequest {
    principal: Option<EntityUid>,
    action: Option<EntityUid>,
    resource: Vec<EntityUid>,
    context: Context,
}
```

An advantage of this alternative is that it minimizes the amount of duplicated
data passed from the language binding when the batch of requests can be
represented in this way.

A disadvantage of this alternative is that it does not extend well to the more
general case of evaluating multiple authorization requests that vary in more
than the resource being referenced.
