# `path` extension type

## Related issues and PRs

- Reference Issues: [#103](https://github.com/cedar-policy/rfcs/issues/103)
- Implementation PR(s): (leave this empty)

## Timeline

- Started: 2026-06-05
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC proposes a `path` extension type for Cedar. A path represents a variable-length, ordered sequence of strings — for example, the components of a filesystem path, S3 object key, URL path, MQTT topic, or reversed hostname. The `path` type exposes two matching methods, `.matches()` and `.prefixMatches()`, whose arguments must be string literals. This restriction keeps Cedar's SMT-based policy analysis decidable and efficient. String splitting and delimiter handling are intentionally out of scope; path values are constructed from pre-parsed components supplied by the application.

## Basic example

The following policy allows principals to read objects under the `reports/2025/` prefix of an S3-like object store:

```cedar
permit(
  principal is User,
  action == S3Action::"GetObject",
  resource is S3Object
) when {
  resource.key.prefixMatches("reports", "2025")
};
```

Here `resource.key` is a `path` value whose components are pre-parsed from the raw key string. If the key is `"reports/2025/annual.pdf"`, the application constructs `path("reports", "2025", "annual.pdf")` and stores it on the entity.

The following policy matches exactly a three-component path with a wildcard in the middle:

```cedar
permit(
  principal is User,
  action == Action::"read",
  resource is File
) when {
  resource.path.matches("data", "*", "config.json")
};
```

This matches `["data", "prod", "config.json"]` but not `["data", "prod", "extra", "config.json"]` (four components) or `["data", "prod", "config.yaml"]` (last component doesn't match).

## Motivation

Many authorization use cases involve resources whose identifiers encode a tree hierarchy: filesystem paths, S3 object keys, URL paths, MQTT topic paths, SPIFFE SVIDs, and domain names. Cedar currently has no built-in representation for variable-length sequences of strings, forcing policy authors to choose between awkward workarounds.

**Hierarchy modeling** works when parent entities exist as Cedar entities and Cedar's `in` operator applies. For implicit hierarchies — S3 keys, URL paths, MQTT topics — the parents do not exist as entities, and creating synthetic ones imposes significant overhead on the calling application.

**Tag-based modeling** splits a path into numbered tags (`"key0"`, `"key1"`, etc.). This works but is verbose, non-obvious, and requires policy authors to carefully manage tag numbering and boundary conditions. The approach is difficult to discover without guidance, and the intent is obscured by the bookkeeping.

**String attributes with `like`** (`resource.keyString like "reports/2025/*"`) is fragile when components can contain the delimiter, cannot enforce exact component count, and cannot distinguish "one wildcard component" from "multiple components matching `*`".

The `path` type packages this common pattern into a clean, analyzable abstraction.

### Use cases

The following use cases motivated this RFC.

**Filesystem paths and S3 object keys.** Prefix matching checks whether a resource lives under a given directory; wildcard patterns handle variable segments such as account IDs or environment names.

**URL paths and SPIFFE SVIDs.** Resources identified by URL path can store path segments as a `path` value, enabling prefix-based access control without synthetic parent entities.

**Hostname suffix matching.** Domains are naturally represented as reversed component sequences: `["com", "github"]` for `github.com`. Storing a pre-reversed hostname as a `path` value enables suffix matching via `.prefixMatches()`. Given a reversed hostname attribute, the following patterns map cleanly:

| Pattern | Cedar expression |
|---|---|
| `github.com` (exact) | `context.host.matches("com", "github")` |
| `*.github.com` (one subdomain) | `context.host.matches("com", "github", "*")` |
| `**.github.com` (one or more subdomains) | `context.host.prefixMatches("com", "github", "*")` |
| `foo.*.github.com` (wildcard second-level) | `context.host.matches("com", "github", "*", "foo")` |

For patterns like `foo.**.github.com` — at least one subdomain, ending with `foo` — both ends can be constrained by combining a forward and reversed path attribute:

```cedar
context.host.prefixMatches("com", "github", "*") &&
context.reversedHost.prefixMatches("foo")
```

**MQTT topic paths** and **OAuth scopes** (e.g., `"repo:status"`) follow the same pattern as filesystem paths and can be handled with `.matches()` and `.prefixMatches()`.

## Detailed design

### The `path` type

The `path` extension type represents an ordered, variable-length sequence of strings. It supports equality: two paths are equal if and only if they have the same number of components and the same string at every position. The `path` type does not support `<`, `<=`, `>`, or `>=` comparisons.

### Constructor

The `path(string, ...)` function constructs a `path` value from zero or more string-typed arguments:

```cedar
path("reports", "2025", "annual.pdf")  // 3-component path
path()                                  // empty path
path(resource.bucket, context.tenant)  // dynamic components
```

Arguments may be any string-typed expression — they are not required to be literals. Strict validation requires each argument to have type `string`.

### Matching methods

The `path` type provides two methods for checking path structure. Pattern syntax follows Cedar's `like` operator: `*` matches zero or more characters within a single component; all other characters match literally. Patterns do not match across component boundaries.

#### `.matches(pattern1, ..., patternN)`

Returns `true` if the path has **exactly** `N` components and each matches the corresponding pattern:

```cedar
path("data", "prod", "config.json").matches("data", "*", "config.json")  // true
path("data", "prod", "config.json").matches("data", "*")                  // false — length 3 ≠ 2
path().matches()                                                           // true — empty matches empty
```

#### `.prefixMatches(pattern1, ..., patternN)`

Returns `true` if the path has **at least** `N` components and the first `N` match the corresponding patterns:

```cedar
path("reports", "2025", "annual.pdf").prefixMatches("reports", "2025")  // true
path("reports", "2024", "annual.pdf").prefixMatches("reports", "2025")  // false — second component
path("reports").prefixMatches("reports", "2025")                        // false — too short
path("anything", "goes").prefixMatches()                                // true — zero patterns
```

#### Argument restrictions

**All arguments to `.matches()` and `.prefixMatches()` must be string literals**, enforced by strict validation. This is the same restriction that requires arguments to `datetime()` and `duration()` to be literals, and for the same reason: it is what makes these methods analyzable. See [Analyzability](#analyzability).

### Element access

`.get(n)` returns the component at zero-based index `n` as a `string`. The argument must be a non-negative integer literal; a computed index is a strict validation error. Accessing an out-of-bounds index is an evaluation error.

```cedar
path("foo", "bar", "baz").get(0)  // "foo"
```

`.get()` is useful when a specific position carries a fixed semantic meaning, such as a tenant ID in the first component of a URL path.

`.has(n)` can be used to avoid the evaluation error, by ensuring that `n` exists within the path.

### Suffix matching

The `path` type does not provide `.suffixMatches()`. Suffix matching requires locating the start position based on the runtime path length — an unbounded computation that cannot be encoded as a decidable SMT formula. See [Drawbacks](#drawbacks).

The most common suffix use case — matching the final component — can be handled by storing it as a separate attribute:

```cedar
resource.dirPath.prefixMatches("reports", "2025") &&
resource.fileName like "*.csv"
```

For general suffix matching, users can store a pre-reversed path as an additional attribute and apply `.prefixMatches()` to it.

### Pre-parsing

Path values are constructed from pre-parsed components via `path()`. Applications are responsible for splitting path strings into components and handling domain-specific ambiguities (e.g., leading slashes, repeated delimiters). This follows Cedar's design philosophy of pushing parsing and normalization to the application layer.

### JSON encoding

In entity and context data:

```json
{ "__extn": { "fn": "path", "arg": ["reports", "2025", "annual.pdf"] } }
```

In the policy AST, the `path()` constructor and its methods follow the same convention as other variadic extension functions:

```json
{ "path": [{ "Value": "reports" }, { "Value": "2025" }, { "Value": "annual.pdf" }] }
```

### Schema

```json
{ "type": "Extension", "name": "path" }
```

### Analyzability

Cedar's SMT-based analysis decides properties like "does policy A permit any request that policy B forbids?" For analysis to be decidable, all operations on a type must be expressible as finite formulas in theories SMT solvers handle.

The key insight is that arguments to `.matches()` and `.prefixMatches()` are always literal patterns known at analysis time. Given `p.matches("reports", "2025", "*")`, the analyzer knows the expected length (3) and the exact pattern at each position, and encodes the call as a fixed conjunction of `like`-style string constraints — finite, quantifier-free, and decidable.

If non-literal arguments were allowed, the analyzer would need to reason about pattern sequences of unknown length, requiring universal quantification over pattern values. This falls outside the decidable SMT theories Cedar targets.

`.get(n)` requires a literal index for the same reason: the analyzer substitutes the access with a direct reference to the `n`-th component rather than encoding general array-indexing semantics.

## Drawbacks

1. **New extension type maintenance burden.** Adding `path` increases Cedar's language surface area and requires updates to the specification, Lean formalization, Rust implementation, and any other language implementations.

2. **Pre-parsing requirement.** Applications that store paths as plain strings today would need to pre-parse them into components. This is a one-time migration cost for existing Cedar deployments.

3. **No suffix matching.** The absence of `.suffixMatches()` means naturally suffix-oriented use cases require data model restructuring. This is a fundamental constraint: suffix matching requires a runtime reversal operation whose loop bound is not statically known, which requires universal quantifiers over path indices and is not decidable in Cedar's SMT theories. The workarounds (separate final-component attribute, or pre-reversed path attribute) are functional but less ergonomic.

4. **Analysis cost scales with pattern length.** Each argument to `.matches()` or `.prefixMatches()` adds SMT constraints. Very long patterns may slow analysis, though path depths in real authorization scenarios are rarely large enough for this to be a practical concern.

5. **Empty components are not restricted.** The `path` type allows empty string components. Applications that do not want them (e.g., from a leading slash) must filter during pre-parsing.

## Alternatives

### Alternative A: Tag-based modeling

Each path component is stored as a numbered entity tag (`"key0"`, `"key1"`, etc.). This is the most naturally available workaround today, but it is verbose, non-obvious, requires manual boundary-condition management, and buries intent under bookkeeping. The `path` type replaces this pattern with a clean abstraction.

### Alternative B: Records for fixed-length paths

Records with positional fields work for paths whose length is fixed by the schema. They fail for variable-length paths — S3 keys, URL paths, MQTT topics — which is exactly what this RFC targets.

### Alternative C: String attributes with `like`

`resource.keyString like "reports/2025/*"` is fragile when components can contain the delimiter, cannot enforce exact component count, and cannot distinguish "one wildcard component" from "multiple components". It provides no structural abstraction for hierarchical identifiers.

### Alternative D: Delimiter-aware string matching

A `pathMatches(pathString, patternString, delimiter)` function would avoid the pre-parsing requirement but would introduce delimiter semantics — leading/trailing slashes, repeated delimiters, empty components — into Cedar's evaluation and formal specification, and would make analysis harder because component count becomes a runtime property of the string value. Cedar's philosophy of keeping parsing in the application layer argues against this approach.

## Unresolved questions

- **`.get()` inclusion.** Should element access be included here or deferred to a follow-on? The primary value of `path` comes from `.matches()` and `.prefixMatches()`; `.get()` adds convenience but also implementation and specification surface area.

- **Wildcard semantics.** Pattern matching follows Cedar's `like` semantics: `*` matches zero or more characters within a single component and does not cross component boundaries. This means `path("foo", "bar").matches("*")` is `false` (length 2, not 1). The interaction between zero-length matches and the hostname use case (where `*.github.com` should require a non-empty subdomain) should be confirmed.

- **Empty path behavior.** Should `path()` — a zero-component path — be a valid value? `path().matches()` and `path().prefixMatches()` would both return `true`, which seems correct, but edge cases in entity data deserve consideration.
