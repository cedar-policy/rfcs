# Allow datetime constructor to represent all valid dates

## Related issues and PRs

- Reference Issues:
- Implementation PR(s): 

## Timeline

- Started: 2026-01-02
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC proposes redefining the grammar of the datetime constructor to allow for more than four digits in a year.

## Motivation

The `datetime` type currently allows for a theoretical range of 2^63 milliseconds before and 2^63-1 milliseconds after the UNIX epoch, but support for datetimes with years far in the past or future is awkward in at least the following ways:
1. There is no way to directly construct a `datetime` with a year outside the range [0000, 9999] in policy. Instead, a `datetime` within the valid range of years must be created and then altered via the use of the `offset()` method.
2. There is no documented JSON serialization format for entities containing a `datetime` with a year outside the range [0000, 9999]. The [proposed entity literal syntax](https://github.com/cedar-policy/rfcs/pull/104) also provides no mechanism for serializing such a `datetime`. This means that `datetime`s can be constructed programmatically via the SDK which cannot then be serialized.

## Detailed design

The maximum representable Cedar datetime, corresponding to 2^63−1 milliseconds since the Unix epoch, is `+292278994-08-17T07:12:55.807Z`. The minimum representable Cedar datetime, corresponding to 2^63 milliseconds before the UNIX epoch, is `-292275055-05-17T16:47:04.192Z` (using the [proleptic Gregorian calendar](https://en.wikipedia.org/wiki/Proleptic_Gregorian_calendar)). Therefore, in order to cover the full range of the 64-bit `datetime` type, the string argument to the `datetime()` constructor must support a nine-digit year.

In order to preserve backwards compatibility and readability for the common case of a four-digit year, this RFC proposes that the existing grammar for the string argument to the `datetime()` constructor be amended to allow both the four-digit year RFC 3339 format and nine-digit expanded year profile of ISO 8601, as distinguished by a leading `+` or `-` token.

If the string represents a timestamp outside the range of a Cedar `datetime`, then the `datetime()` expression generates an error when evaluated.

For example:
```
datetime("2025-01-06T00:11:22.333Z") => valid RFC 3339, no leading + or -
datetime("0000-01-06T00:11:22.333Z") => valid RFC 3339, corresponds to 1 BCE (per ISO 8601 rules)
datetime("+000002025-01-06T00:11:22.333Z") => valid positive nine-digit expanded year ISO 8601
datetime("-000002025-01-06T00:11:22.333Z") => valid negative nine-digit expanded year ISO 8601

datetime("+00002025-01-06T00:11:22.333Z") => invalid, only eight-digits in year
datetime("000002025-01-06T00:11:22.333Z") => invalid, more than four-digit year without a leading +/-
datetime("25-01-06T00:11:22.333Z") => invalid, two digit year
datetime("+292278994-08-17T07:12:55.808Z") => invalid, timestamp overflows 64-bit storage size
```

Serialization of a `datetime` must emit:
* the four-digit RFC 3339 format for `datetime`s with years in the range [0000, 9999]
* the nine-digit expanded year ISO 8601 profile for negative years and years requiring more than four digits

## Drawbacks

1. Deserialization of `datetime()` strings becomes marginally more complicated, requiring overflow checks and handling of the year 0 as 1 BCE.
2. Similarly, serialization becomes marginally more complicated because the format chosen (RFC 3339 vs nine-digit expanded year ISO 8601) now depends on the value of the `datetime`.
3. Cedar `datetime`s remain difficult to convert to certain commonly used types in Cedar implementations. For example, Rust's `chrono` crate [limits date types to +/- 262,000 years](https://docs.rs/chrono/latest/chrono/#limitations), well less than the allowable range for Cedar `datetime`s. Python's [datetime.MAXYEAR of 9999](https://docs.python.org/3/library/datetime.html#datetime.MAXYEAR) is even more restrictive.

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
2. A similar construction would have to be devised for the [proposed entity literal syntax](https://github.com/cedar-policy/rfcs/pull/104).
3. This construction seems to be a tacit approval of allowing extension method invocations in serialized entities generally. In the author's opinion, Cedar entities ought to be considered [plain old data](https://en.wikipedia.org/wiki/Passive_data_structure) and such constructions as the one proposed in this alternative are contrary to that idea.

The upside of this approach is that it's not a breaking change and preserves the ability to perform authorizations involving exotic dates.

### Alternative 2: restrict the range of years in Cedar datetimes to [0001, 9999]

This is a tempting alternative, but unfortunately breaks analyzability of Cedar, which makes it a non-starter.

### Alternative 3: create a new datetime constructor which takes a duration string

For representing `datetime`s with years outside the currently allowable range, a new constructor could be created:

```
datetimeOffsetFromEpoch("2521723d12h15m1s12ms")
datetimeOffsetFromEpoch("-2521723d12h15m1s12ms")
```

The downsides of this approach are:
1. It's not human-readable.
2. No other extension type has multiple constructor functions, so this alternative would be treading new ground without a very compelling reason to do so.

An alternative construction would allow for `datetimeOffsetFromEpoch()` to take a `duration` as an argument instead, but that violates the current requirement that all extension functions must take a single argument of type string.

## Unresolved questions

None