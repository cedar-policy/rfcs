# Restrict range of datetime to years 0001-9999

## Related issues and PRs

- Reference Issues:
- Implementation PR(s): 

## Timeline

- Started: 2026-01-02
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC proposes redefining the valid range of years for the `datetime` as [0001, 9999], which is a breaking change.

## Motivation

The `datetime` type currently allows for a theoretical range of 2^63 milliseconds before and 2^63-1 milliseconds after the UNIX epoch, but support for datetimes with years far in the past or future is awkward in at least the following three ways:
1. There is no way to directly construct a `datetime` with a year outside the range [0000, 9999] in policy. Instead, a `datetime` within the valid range of years must be created and then altered via the use of the `offset()` method.
2. There is no documented JSON serialization format for entities containing a `datetime` with a year outside the range [0000, 9999]. The [proposed entity literal syntax](https://github.com/cedar-policy/rfcs/pull/104) also provides no mechanism for serializing such a `datetime`. This means that `datetime`s can be constructed programmatically via the SDK which cannot then be serialized.
3. Cedar implementations and applications which interface with them are unable to utilize date/time libraries which cannot represent such a `datetime`. For example, Rust's `chrono` crate [limits date types to +/- 262,000 years](https://docs.rs/chrono/latest/chrono/#limitations), well less than the allowable range for Cedar `datetime`s. Python's [datetime.MAXYEAR of 9999](https://docs.python.org/3/library/datetime.html#datetime.MAXYEAR) is even more restrictive.

## Detailed design

This RFC proposes that the range of valid `datetime`s be restricted to between `0001-01-01T00:00:00.000Z` and `9999-12-31T23:59:59.999Z` inclusive (or -62135596800000 and 253402300799999 in terms of milliseconds since the UNIX epoch at UTC). In other words, every valid Cedar `datetime` should be representable as an RFC 3339 timestamp in UTC, although the converse is not necessarily true.

The lower bound excludes year 0000 to avoid the use of astronomical year numbering (i.e. 0000 = 1 BCE), which would require explanation and isn't really worthwhile for any real-world use case.

The implementation for this new restriction requires two changes:
1. `datetime`s created via the `datetime()` constructor which result in a millisecond value outside the range [-62135596800000, 253402300799999] would return an overflow error
2. `datetime`s created via the `offset()` operator would similarly return an error if the resulting number of milliseconds is outside the given bounds.

Note that this limitation means that, while the date `9999-12-31T23:59:59-01:00` is parseable as an RFC 3339 timestamp, it's not a valid Cedar `datetime` because normalization to UTC would require year 10000, which is outside the proposed range.

### Breaking change considerations

While this proposal would be a breaking change due to the potential for creating new errors at policy evaluation time, the likelihood of breakage is quite low because of the unlikely nature of such exotic datetimes to appear in entity data or in policy. It's doubtful any users would find this restriction to be a barrier to upgrading.

That said, the consequences of making this change could be severe as authorization decisions could be altered by it.

## Drawbacks

1. This is a breaking change to the Cedar language specification. While the likelihood that anyone is using `datetime`s outside of the proposed range in entities or policies is low, it's theoretically possible and this change could alter authorization decisions by causing evaluations to return errors which previously did not.
2. The Cedar maintainers have raised concerns about analyzability when constraining extension values. At this time, these concerns are not well understood by the author of the RFC.
3. This change would exclude authorizations against exotic dates far in the past and into the future.

## Alternatives

### Alternative 1: allow extension methods to be expressed in entity JSON serialization

This was the feature that originally motivated this RFC. The proposal was to allow for a serialization format like this, where `offset()` wraps the `datetime()` as an `__extn` and a new `args` attribute is created to allow for multiple arguments to be passed:

```
{
  "__extn": {
    "fn": "offset",
    "args": [
      {
        "__extn": {
          "fn": "datetime",
          "arg": "1970-01-01"
        }
      },
      {
        "__extn": {
          "fn": "duration",
          "arg": "124375392000000ms"
        }
      }
    ]
  }
}
```

This solution allows entity serialization to use the same workaround afforded to policies to create `datetime`s outside the range afforded by the constructor argument.

However, this solution is undesirable for a few reasons:
1. A serialization format like the one proposed in this alternative means that Cedar implementations must either store entity attribute values as an expression or must evaluate Cedar expressions when deserializing entities from JSON, creating a new dependency. Today, all that's required of the implementation when creating entities is to parse the string argument to the type constructor function.
2. Serialization of a `datetime` in an entity would potentially depend on the value, complicating the implementation. `datetime`s with years within the [0001,9999] range could be serialized without a wrapping `offset()` while `datetime`s with years outside that range could not. Alternatively, `datetime`s could always be serialized with a wrapping `offset()`, but that would make the common-case serialization dramatically less readable than it already is.
3. A similar construction would have to be devised for the [proposed entity literal syntax](https://github.com/cedar-policy/rfcs/pull/104).
4. This construction seems to be a tacit approval of allowing extension method invocations in serialized entities generally. In the author's opinion, Cedar entities ought to be considered [plain old data](https://en.wikipedia.org/wiki/Passive_data_structure) and such constructions as the one proposed in this alternative are contrary to that idea.

The upside of this approach is that it's not a breaking change and preserves the ability to perform authorizations involving exotic dates.

### Alternative 2: allow a wider range of years in the datetime constructor

Instead of restricting the range of `datetime`, the allowable range of years in the constructor argument could be extended, like so:

```
datetime("12345-01-01T00:00:00Z")
datetime("-12345-01-01T00:00:00Z")
```

This is a tempting alternative with a few notable downsides:
1. Since the Cedar `datetime` supports years millions of years into the past and future, limitations on the use of common date/time libraries in Cedar implementations would still come into play.
2. Cedar would lose the ability to require that the `datetime` argument must conform to the ubiquitous RFC 3339 profile of ISO 8601, which only allows four digit years. ISO 8601 does allow for more digits, but it must be a fixed number and the year must begin with a `+` or `-` character, both of which are clumsy for the common case.

The upside of this approach is that it's not a breaking change and preserves the ability to perform authorizations involving exotic dates without introducing any new serialization syntax. It's also generally human-readable, although requiring a nine-digit year would strain readability somewhat.

### Alternative 3: create a new datetime constructor which takes a duration string

For representing `datetime`s with years outside the [0001-9999] range, a new constructor could be created:

```
datetimeOffsetFromEpoch("2521723d12h15m1s12ms")
datetimeOffsetFromEpoch("-2521723d12h15m1s12ms")
```

The downsides of this approach are:
1. It's not human-readable.
2. Serialization of a `datetime` in an entity would potentially depend on the value, complicating the implementation. `datetime`s with years within the [0001,9999] range could be serialized via `datetime()` while `datetime`s with years outside that range could not. Alternatively, `datetime`s could always be serialized via `datetimeOffsetFromEpoch()`, but that would make the common-case serialization dramatically less readable than it already is.
3. No other extension type has multiple constructor functions, so this alternative would be treading new ground without a very compelling reason to do so.

An alternative construction would allow for `datetimeOffsetFromEpoch()` to take a `duration` as an argument instead, but that violates the current requirement that all extension functions must take a single argument of type string.

## Unresolved questions

1. Analyzability of constrained values? This was raised previously in a Slack thread on this topic.
2. Can/should policy and entity validation detect invalid `datetime`s?