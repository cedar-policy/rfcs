# `datetime` extension

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2024-08-08
- Accepted: 2024-09-11
- Landed: TBD
- Released: TBD

## Summary

Cedar currently supports extension functions for IP addresses and decimal values.
A popular request has been support for dates and times as well, but there are several complexities here (e.g., timezones and leap years) that have delayed this.
Recall that anything we add to Cedar, we want to be able to formally model in Lean using our verification-guided development approach (see [this blog post](https://www.amazon.science/blog/how-we-built-cedar-with-automated-reasoning-and-differential-testing)).
We also want to support a decidable SMT-based analysis (see [this paper](https://dl.acm.org/doi/10.1145/3649835)).
The goal of this RFC is to narrow in on a set of date/time related features that are useful in practice, but still feasible to implement in Cedar given these constraints.

## Basic example

This RFC would support a policy like the following, which allows a user to access materials in the "device_prototypes" folder only if they have a sufficiently high job level and a tenure of more than one year.

```cedar
permit(
  principal is User,
  action == Action::"view",
  resource in Folder::"device_prototypes"
)
when {
  principal.department == "HardwareEngineering" &&
  principal.jobLevel >= 10 &&
  context.now.timestamp.durationSince(principal.hireDate) > duration("365d")
};
```

## Motivation

Previously for applications that determine authorization based on date/time, our suggestion has been to use [Unix time](https://en.wikipedia.org/wiki/Unix_time) (see Workaround A) or to pass the result of time computations in the context (see Workaround B).
But these are not ideal solutions because Cedar policies are intended to _expressive_,  _readable_, and _auditable_.
Unix timestamps fail the readability criteria: an expression like `context.now < 1723000000` is difficult to read and understand without additional tooling to decode the timestamp.
Unix timestamps are also indistinguishable from any other integral value providing no additional help in expressing the abstraction of time.
Passing in pre-computed values in the context (e.g., a field like `context.isWorkingHours`) makes authorization logic difficult to audit because it moves this logic outside of Cedar policies and into the calling application.
It is also difficult for the calling application to predict the necessary pre-computed values that a policy writer requires for their intended purpose. These may change over time, and may also differ depending on the principal, action, and/or resource.

### Additional examples

The examples below illustrate the types of policies that this proposal would enable. It assumes that the application adds a Cedar Record named `now` to `context` with the following fields:

- `timestamp`: A value of type `datetime` (defined below) representing the current time at policy evaluation
- `dayOfWeek`: A `long` value representing current the day of week (Sunday = 1, ... Saturday = 7)
- `day`: A `long` representing the current day of the month
- `month`: A `long` representing current month (January = 1)
- `year`: A `long` representing the current year

**Only allow user "alice" to view JPEG photos for one week after creation.**

```cedar
permit(
  principal == User::"alice",
  action == PhotoOp::"view",
  resource is Photo
) when {
  resource.fileType == "JPEG" &&
  context.now.timestamp.durationSince(resource.creationTime) <= duration("7d")
};
```

**Allow access from a certain IP address only between 9am and 6pm UTC.**

```cedar
permit(
  principal,
  action == Action::"access",
  resource
) when {
  context.srcIp.isInRange(ip("192.168.1.0/24")) &&
  context.workdayStart <= context.now.timestamp &&
  context.now.timestamp < context.workdayEnd
};
```

**Prevent employees from accessing work documents on the weekend.**

```cedar
forbid(
  principal,
  action == Action::"access",
  resource is Document
) when {
  [1,7].contains(context.now.dayOfWeek)
};
```

**Permit access to a special opportunity for persons born on Leap Day.**

```cedar
permit(
  principal,
  action == Action::"redeem",
  resource is Prize
) when {
  principal.birthDate.day == 29 &&
  principal.birthDate.month == 2 &&
  context.now.day == 29 &&
  context.now.month == 2
};
```

**Forbid access to EU resources after Brexit**

```cedar
forbid(
  principal,
  action,
  resource
) when {
  context.now.timestamp > datetime("2020-01-31T23:00:00Z") &&
  context.location.countryOfOrigin == 'GB' &&
  resource.owner == 'EU'
}
```

## Detailed design

This RFC proposes supporting two new extension types: `datetime`, which represents a particular instant of time, up to millisecond accuracy, and `duration` which represents a duration of time.
To construct and manipulate these types we will provide the functions listed below.
All of this functionality will be hidden behind a `datetime` feature flag (analogous to the current decimal and IP extensions), allowing users to opt-out.

### Instants of Time (`datetime`)

The `datetime(string)` function constructs a datetime value. Like with other extension function constructors, strict validation requires `string` to be a string literal, although evaluation/authorization support any string-typed expression. The string must be of one of the forms, and regardless of the timezone offset is always normalized to UTC:

- `"YYYY-MM-DD"` (date only)
- `"YYYY-MM-DDThh:mm:ssZ"` (UTC)
- `"YYYY-MM-DDThh:mm:ss.SSSZ"` (UTC with millisecond precision)
- `"YYYY-MM-DDThh:mm:ss(+/-)hhmm"` (With timezone offset in hours and minutes)
- `"YYYY-MM-DDThh:mm:ss.SSS(+/-)hhmm"` (With timezone offset in hours and minutes and millisecond precision)

The `datetime` type does not provide a way for a policy author to create a `datetime` from a numeric timestamp. One of the readable formats listed above must be used, instead.

Values of type `datetime` have the following methods:

- `.offset(duration)` returns a new `datetime`, offset by duration.
- `.durationSince(DT2)` returns the difference between `DT` and `DT2` as a `duration`. (Note that the inverse of `durationSince` is `DT2.offset(duration)`).
   An invariant for `DT1.durationSince(DT2)` is that when `DT1` is before `DT2` the resulting duration is negative.
- `.toDate()` returns a new `datetime`, truncating to the day, such that printing the `datetime` would have `00:00:00` as the time.
- `.toTime()` returns a new `duration`, removing the days, such that only milliseconds since `.toDate()` are left. This is equivalent to `DT.durationSince(DT.toDate())`

Values of type `datetime` can be used with comparison operators:

- `DT1 < DT2` returns `true` when `DT1` is before `DT2`
- `DT1 <= DT2` returns `true` when `DT1` is before or equal to `DT2`
- `DT1 > DT2` returns `true` when `DT1` is after `DT2`
- `DT1 >= DT2` returns `true` when `DT1` is after or equal to `DT2`
- `DT1 == DT2` returns `true` when `DT1` is equal to `DT2`
- `DT1 != DT2` returns `true` when `DT1` is not equal to `DT2`

Equality is based on the underlying representation (see below) so, for example, `datetime("2024-08-21T") == datetime("2024-08-21T00:00:00.000Z")` is true. This behavior is consistent with the decimal extension function, where `decimal("1.0") == decimal("1.0000")` is also true.

#### Representation

The `datetime` type is internally represented as a `long` and contains a Unix Time in milliseconds. This is the number of non-leap seconds that have passed since `1970-01-01T00:00:00Z` in milliseconds. A negative Unix Time represents the number of milliseconds before `1970-01-01T00:00:00Z`. Unix Time days are always 86,400 seconds and handle leap seconds by absorbing them at the start of the day. Due to using Unix Time, and not providing a "current time" function, Cedar avoids the complexities of leap second handling, pushing them to the system and application.

### Durations of Time (`duration`)

The `duration(string)` function constructs a duration value from a duration string. Strict validation requires the argument to be a literal, although evaluation/authorization support any appropriately-typed expressions. The `string` is a concatenated sequence of quantity-unit pairs. For example, `"1d2h3m4s5ms"` is a valid duration string.

The quantity part is a natural number. The unit is one of the following:

- `d`: days
- `h`: hours
- `m`: minutes
- `s`: seconds
- `ms`: milliseconds

Duration strings are required to be ordered from largest unit to smallest unit, and contain one quantity per unit. Units with zero quantity may be omitted.
`"1h"`, `"-10h"`, `"5d3ms"`, and `"3h5m"` are all valid duration strings.

A duration may be negative. Negative duration strings must begin with `-`.

Values of type `duration` have the following methods:

- `.toMilliseconds()` returns a `long` describing the number of milliseconds in this duration. (the value as a long, itself)
- `.toSeconds()` returns a `long` describing the number of seconds in this duration. (`.toMilliseconds() / 1000`)
- `.toMinutes()` returns a `long` describing the number of minutes in this duration. (`.toSeconds() / 60`)
- `.toHours()` returns a `long` describing the number of hours in this duration. (`.toMinutes() / 60`)
- `.toDays()` returns a `long` describing the number of days in this duration. (`.toHours() / 24`)

Values with type `duration` can also be used with comparison operators:

- `DUR1 < DUR2` returns `true` when `DUR1` is shorter than `DUR2`
- `DUR1 <= DUR2` returns `true` when `DUR1` is shorter than or equal to `DUR2`
- `DUR1 > DUR2` returns `true` when `DUR1` is longer than `DUR2`
- `DUR1 >= DUR2` returns `true` when `DUR1` is longer than or equal to `DUR2`
- `DUR1 == DUR2` returns `true` when `DUR1` is equal to `DUR2`
- `DUR1 != DUR2` returns `true` when `DUR1` is not equal to `DUR2`

Comparisons are done with respect to the sign of a duration. I.e., `duration("-1d") < duration("1s")`.

Equality is based on the underlying representation (see below) so, for example, `duration("1d") == duration("24h")` is true.

#### Representation

The `duration` type is internally represented as a quantity of milliseconds as a `long`, which can be positive, negative, or zero.

A negative duration may be useful when a user wants to use `.offset()` to shift a date backwards.
For example: `context.now.offset(duration("-3d"))` expresses "three days before the current date".

### Errors

All the extension functions proposed in this RFC will throw a type error at authorization time if called with the wrong type of arguments.
Additionally, the `datetime` and `duration` constructors will return an error if the input string does not match the expected format, or if the internal representation of the value (a 64-bit signed int) would overflow. `.offset(duration)` will return an error if the resulting datetime would overflow.

As noted above, strict validation will require passing literals to the `duration` and `datetime` constructors, and it will raise an error if those strings are malformed. Otherwise, validation is straightforward.

### JSON Encoding

Cedar supports a JSON format for policies, schemas, entities, and request contexts. The JSON representation of the `datetime` and `duration` functions will match the precedents set by the existing IP address and decimal extensions.

For example, here is the JSON encoding of the expression `datetime("2020-01-31T23:00:00Z")`, which might occur in a policy condition:

```json
"datetime": [
    {
        "Value": "2020-01-31T23:00:00Z"
    }
]
```

And here is the JSON encoding for this value when it occurs in entity or context data:

```json
{ "__extn": { "fn": "datetime", "arg": "2020-01-31T23:00:00Z" } }
```

Finally, here is the JSON encoding of the `datetime` type in a schema:

```json
{
    "type": "Extension",
    "name": "datetime"
}
```

### Out of scope

- **Conversion between UTC and epochs:** This will be particularly difficult to model and verify in Lean (although it's technically possible, see [this paper](https://dl.acm.org/doi/abs/10.1145/3636501.3636958) which does something similar in the Coq proof assistant). Since it will likely require input-dependent loops, it is unlikely that this can be reasoned about efficiently with SMT.

- **Conversion between UTC and other time zones:** Time Zones are a notoriously complex system that evolves rapidly. We avoid this complexity by offering `datetime.offset(duration).` Policy authors that require "local time" can either provide an additional datetime in `context` or provide a `duration` to the `context` and call `.offset()` to shift the time.

- **Function to get current time:** A natural extension of this proposal would be a function `currentTime()` that provides the current time instead of it being passed in through `context`. However, `currentTime()` is stateful, i.e. not pure, and cannot be modeled in SMT. It's also not useful: `currentTime() == currentTime()` may return false, and Cedar does not provide local bindings (e.g. `let t = currentTime()`). For testing purposes, Cedar would also need to provide some way to override `currentTime`. These problems all go away if `currentTime()` is not supported.

- **Leap seconds and leap years:** Cedar does not have a clock, and this proposal does not add one. Instead, applications pass the current time through `context` or an entity and let the system / application handle complexities like leap seconds and leap years. This means that Cedar cannot provide utilities like `datetime.dayOfWeek()` or `datetime.dayOfMonth()`. Cedar applications that wish to define policies based on these ideas should pass pre-computed properties through entities or through the `context`.

### Support for date/time in other authorization systems

AWS IAM supports [date condition operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html#Conditions_Date), which can check relationships between date/time values in the ISO 8601 date format or Unix time. You can find an example of a IAM policy using date/time [here](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_aws-dates.html).

[Open Policy Agent](https://www.openpolicyagent.org) provides a [Time API](https://www.openpolicyagent.org/docs/latest/policy-reference/#time) with nanosecond precision and extensive time zone support. During policy evaluation, the current timestamp can be returned, and date/time arithmetic can be performed. The `diff` (equivalent to our proposed `durationSince` operator on `datetime`) returns an array of positional time unit components, instead of a value typed similarly to our proposed `duration`.

## Alternatives

Both alternatives we propose here are "do nothing" options. They show how to encode date/time using existing Cedar types and functionality.

### Workaround A: Represent Unix time with a Long

Cedar has long suggested workarounds for date/time functionality by using the comparison and arithmetic operators with `context`-provided Unix Timestamps.

Here are the previous examples rewritten to use Unix Time.

**Only allow experienced, tenured persons from the Hardware Engineering department to see prototypes.**

```cedar
permit(
  principal is User,
  action == Action::"view",
  resource in Folder::"device_prototypes"
)
when {
  principal.department == "HardwareEngineering" &&
  principal.jobLevel >= 10 &&
  (context.currentTime - (365 * 24 * 60 * 60)) >= principal.hireDate
};
```

**Only allow user "alice" to view JPEG photos for one week after creation.**

```cedar
permit(
  principal == User::"alice",
  action == PhotoOp::"view",
  resource is Photo
) when {
  resource.fileType == "JPEG" &&
  resource.creationDate <= (context.currentTime - (7 * 24 * 60 * 60))
};
```

**Allow access from a certain IP address only between 9am and 6pm UTC.**

Cedar _does not currently support_ arithmetic division (`/`) or remainder (`%`), and therefore this example is _not expressible_, today.

```cedar
permit(
  principal,
  action == Action::"access",
  resource
) when {
  context.srcIp.isInRange(ip("192.168.1.0/24")) &&
  9 <= ((context.currentTime / (60 * 60)) % 24) &&
  ((context.currentTime / (60 * 60)) % 24) < 18
};
```

Note that the localized version of this example, with timezone offset, could be supported using the `+` or `-` operators on `context.currentTime`.

**Prevent employees from accessing work documents on the weekend.**

With Unix Time, this requires `/` and `%` operators to compute the `dayOfWeek`, which isn't currently expressible in Cedar.

**Permit access to a special opportunity for persons born on Leap Day.**

With Unix Time, this requires `/` and `%` operators to compute whether or not it is a leap year, which isn't currently expressible in Cedar.

**Forbid access to EU resources after Brexit**

```cedar
forbid(
  principal,
  action,
  resource
) when {
  context.currentTime > 1580511600 &&
  context.location.countryOfOrigin == 'GB' &&
  resource.owner == 'EU'
}
```

### Workaround B: Pass results of time checks in the context

Another workaround we have suggested is to simply handle date/time logic _outside_ of Cedar, and pass the results of checks in the `context`. For example, you could pass in fields like  `context.isWorkingHours` or `context.dayOfTheWeek`.

Here are the previous examples rewritten to use additional context.

**Only allow experienced, tenured persons from the Hardware Engineering department to see prototypes.**

```cedar
permit(
  principal is User,
  action == Action::"view",
  resource in Folder::"device_prototypes"
)
when {
  principal.department == "HardwareEngineering" &&
  principal.jobLevel >= 10 &&
  principal.hireDate <= context.minimumHiringDateForAccess
};
```

Note: assumes `context.hireDate` and `context.minimumHiringDateForAccess` are `long` values (e.g., Unix time).

**Only allow user "alice" to view JPEG photos for one week after creation.**

```cedar
permit(
  principal == User::"alice",
  action == PhotoOp::"view",
  resource is Photo
) when {
  resource.fileType == "JPEG" &&
  resource.creationDate >= context.oldestViewableDate
};
```

Note: assumes `resource.creationDate` and `context.oldestViewableDate` are `long` values (e.g., Unix time).

**Allow access from a certain IP address only between 9am and 6pm UTC.**

```cedar
permit(
  principal,
  action == Action::"access",
  resource
) when {
  context.srcIp.isInRange(ip("192.168.1.0/24")) &&
  context.isWorkingHours
};
```

**Prevent employees from accessing work documents on the weekend.**

```cedar
forbid(
  principal,
  action == Action::"access",
  resource is Document
) when {
  context.isTheWeekend
};
```

**Permit access to a special opportunity for persons born on Leap Day.**

```cedar
permit(
  principal,
  action == Action::"redeem",
  resource is Prize
) when {
  context.isMyBirthday && context.isLeapDay
};
```

**Forbid access to EU resources after Brexit**

```cedar
forbid(
  principal,
  action,
  resource
) when {
  context.afterBrexit &&
  context.location.countryOfOrigin == 'GB' &&
  resource.owner == 'EU'
}
```

## Discussion notes

### Local time

The current proposal has no direct support for local time, or time zones outside of UTC. Providing robust time zone support would add significant complications to the formal models and ruin the project's SMT-based analysis goals. Policy authors wishing to use local time can simulate it by:

- providing offsets, of the form `+/-hhmm`, to the time strings used by `datetime()`. (Note: no time zone information is retained. The time will be converted to UTC)
- utilizing the `datetime.offset()` method with `duration` values, or values passed through entities and/or `context`.

Consider the policy below that checks if a principal's local time is between 09:00 and 17:00.

```cedar
permit(
  principal,
  action == Action::"access",
  resource
) when {
  context.now.timestamp.offset(principal.timeZoneOffset).toTime() >= duration("9h") &&
  context.now.timestamp.offset(principal.timeZoneOffset).toTime() <= duration("17h")
};
```

### Operator overloading

This RFC proposes to use operators `<`, `<=`, `>`, and `>=` for comparing `datetime` and `duration` objects.
Currently in Cedar, these operations are only supported for `long`-typed values.
For other extension types with similar operations, Cedar instead uses extension functions (e.g., `.lessThan()` for decimal values).

This RFC proposes to _reverse_ this decision, and instead allow using builtin operators for extension functions, as appropriate.
This will add some implementation complexity (at least in the primary [Rust implementation](https://github.com/cedar-policy/cedar)), but it will make policies that use these operations easier to read and easier to write.

### Millisecond precision

The current proposal supports milliseconds. The ISO 8601 format does not specify a maximum precision, so we can technically allow any number of `S`s after the `.` in `YYYY-MM-DDThh:mm:ss.SSSZ`. Based on [this blog post](https://nickb.dev/blog/iso8601-and-nanosecond-precision-across-languages/), it appears that Javascript supports milliseconds (3 digits), Python supports microseconds (6 digits), and Rust and Go support nanoseconds (9 digits). Assuming nanosecond accuracy, the maximum (signed) 64-bit number (2^63 - 1) represents April 11, 2262. This date seems far enough out that any of these choices (milliseconds, microseconds, or nanoseconds) seems reasonable.

During discussion, we decided that sub-second accuracy was potentially useful, but we did not have a use case in mind for sub-millisecond accuracy.
So in the end we landed on milliseconds.
Note that this is the backwards compatible option (at least with respect to allowable date/time strings) because we can add precision later, but not remove it without a breaking change.
