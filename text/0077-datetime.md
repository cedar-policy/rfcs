# `datetime` extension

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started:

## Summary

We currently support extension functions for IP addresses and decimal values.
A popular request has been support for dates and times as well, but there are several complexities here (e.g., timezones and leap years) that have delayed work on this.
Recall that for anything we add to Cedar, we want to be able to formally model in Lean using our verification-guided development approach (see [this blog post](https://www.amazon.science/blog/how-we-built-cedar-with-automated-reasoning-and-differential-testing)).
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
  context.currentTime.timeDelta(principal.hireDate).getDays() >= 365
};
```

## Motivation

Here are some of the applications we've seen that have prompted requests for this functionality:

- Apply certain rules after some day in future. For instance, say that some new legislation is going into effect at that date.
- Check whether an action is occurring is in certain time frame, like during working hours (Monday - Friday, 9am - 5pm).

Previously for these types of applications, our suggestion has been to use Unix timestamps (see Alt. A) or to pass the result of time computations in the context (see Alt. B).
But these are not ideal solutions because Cedar policies are intended to be _readable_ and _auditable_.
Unix timestamps fail the readability criteria: an expression like `context.now < 1723000000` will be difficult for most people to read and understand.
Passing in pre-computed values in the context (e.g., a field like `context.isWorkingHours`) makes authorization logic difficult to audit because it moves this logic outside of Cedar policies and into the calling application.

### Additional examples

Only allow user "alice" to view JPEG photos for one week after creation.

```cedar
permit(
  principal == User::"alice",
  action == PhotoOp::"view",
  resource is Photo
) when {
  resource.fileType == "JPEG" &&
  context.currentTime.timeDelta(resource.creationDate).getDays() <= 7
};
```

Allow access from a certain IP address only between 9am and 6pm UTC.

```cedar
permit(
  principal,
  action == Action::"access",
  resource
) when {
  context.srcIp.isInRange(ip("192.168.1.0/24")) &&
  9 <= context.currentTime.getHours() &&
  context.currentTime.getHours() < 18
};
```

**TODO**: Add more examples (esp. one using dates) & improve explanation of current examples

## Detailed design

This RFC proposes supporting two new extension types: `datetime`, which represents a particular instant of time, up to second accuracy, and `duration` which represents a duration of time.
To construct and manipulate these types we will provide the functions listed below.
All of this functionality will be hidden behind a `datetime` feature flag (analogously to the current decimal and IP extensions), allowing users to opt-out if they do not want this functionality.

- `datetime(s)` constructs a datetime object. Like with our other constructors, strict validation requires `s` to be a string literal, although evaluation/authorization support any string-typed expression. The string must have the form "YYYY-MM-DDThh:mm:ss".
  - **TODO**: More details about the input format. Probably just to follow the ISO standards.
- `d.isBetween(d1, d2)` checks whether date `d` is between dates `d1` and `d2` (inclusive).
- `d.isBefore(d1)` checks whether date `d` is before date `d1` (non-inclusive).
- `d.timeDelta(d1)` computes the difference between two datetime objects and returns a duration object.
- `d.getYear()`, `d.getMonth()`, `d.getDay()`, `d.getHours()`, `d.getMinutes()`, `d.getSeconds()` return the relevant component of the date or duration object as a long value.
- **TODO**: Anything else we want to add?

Internally, the a datetime object will have a structure like the following:

```cedarschema
{
  year: long,
  month: long,
  day: long,
  hours: long,
  minutes: long,
  seconds: long,
}
```

The datetime parsing function will be responsible for ensuring validity of the structure (e.g., that `month` is between 1 and 12).

**TODO**: Precisely describe validity constraints to show that they can be encoded in SMT.

### Out of scope

- **Conversion between UTC and epochs:** this will be particularly difficult to model and verify in Lean (although it's technically possible, see [this paper](https://dl.acm.org/doi/abs/10.1145/3636501.3636958) which does something similar in the Coq proof assistant). Since it will likely require input-dependent loops, it is unlikely that this can be reasoned about efficiently with SMT.
- **TODO**: Likely more to add here (e.g., timezones, leap seconds, a function to get the day of the week)

### Support for date/time in other authorization systems

AWS IAM supports [date condition operators](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html#Conditions_Date), which can check relationships between date/time values in the ISO 8601 date format or Unix time. You can find an example of a IAM policy using date/time [here](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_aws-dates.html).

## Drawbacks

**TODO**

## Alternatives

### Alt. A: Use Unix time / timestamps / epochs

One of our suggested workarounds for date/time functionality has been to use [Unix time](https://en.wikipedia.org/wiki/Unix_time), which measures the number of non-leap seconds that have elapsed since 00:00:00 UTC on January 1, 1970. Unix time is commonly used in computing systems, and there are many libraries available to convert between more familiar day formats and Unix time.

**TODO**: Rewrite example policies above using Unix time

### Alt. B: Pass results of time checks in the context

Another workaround we have suggested is to simply handle date/time logic _outside_ of Cedar, and pass the results of checks in the context. For example, you could pass in fields like  `context.isWorkingHours` or `context.dayOfTheWeek`.

**TODO**: Add example policies

### Alt. C: Represent dates with records

Most of the complexity in the current proposal will come from the need to parse timestamps. In the Rust library (and in other implementations of Cedar in standard languages), this can be done with a library function, but Lean does not provide these utilities, so we will have to build them ourselves.

We can avoid some of this complexity by changing the signature of the `datetime` function to take a record, like `{year: 2024, month: 7, day: 31, hour: 12, minute: 15, second: 0}`. This will require parsing on the user side, which presumably can be done with a library.

But once we remove parsing from the equation, this extension looks more like an application of _Cedar function macros_ than a proper extension function. See the (currently archived) [RFC 61](https://github.com/cedar-policy/rfcs/pull/61) for more details.

## Potential extensions

### Ext. A: Provide a `currentTime` function

The examples above expect `currentTime` to be passed in the context during the authorization request.
An alternative would be to provide a `currentTime()` extension function that computes the current time at policy evaluation time.

## Unresolved questions

TBD
