# Schema libraries

## Related issues and PRs

- Reference Issues: Inspired by [RFC 58], but includes new material not present in RFC 58
- Implementation PR(s):

## Timeline

- Started: 2024-06-07

## Summary

Allow Cedar schemas to include/import "libraries" of definitions from local
files and/or remote URLs.

This RFC does not propose that the Cedar team would build or maintain any such
libraries; it only proposes the mechanism for importing libraries from local
files and/or remote URLs.

## Basic example

Human schema format:
```
import "https://raw.githubusercontent.com/cedar-policy/cedar-examples/release/3.2.x/cedar-example-use-cases/document_cloud/document_cloud.cedarschema";
import "https://example.com/cedar_schemas/oidc.cedarschema";
import "https://example.com/cedar_schemas_json/foobar.cedarschema.json";

namespace "MyApp" {
  ...
}
```

JSON schema format:
```
{
  "imports" : [
    "https://raw.githubusercontent.com/cedar-policy/cedar-examples/release/3.2.x/cedar-example-use-cases/document_cloud/document_cloud.cedarschema",
    "https://example.com/cedar_schemas/oidc.cedarschema",
    "https://example.com/cedar_schemas_json/foobar.cedarschema.json"
  ],
  "MyApp": {
    ...
  }
}
```

## Motivation

Some data sources are common across many applications and useful to many Cedar
users, either within the same organization or even across organizations.

### 1. Within the same organization

This RFC would allow an organization to define its own libraries of schema
definitions, which could be reused across many different schemas (say, for
different webapps owned by the organization).
For instance, the organization might have common definitions of `User` or
`Account` that apply in many different applications, and although those
applications may not want to share entire Cedar schemas, with this RFC they
could share just the definitions of `User` or `Account`, which could be defined
once in a central location (in the same or separate libraries).

### 2. Across organizations

For another motivating example, consider identity providers (IdPs) which comply
with the OpenID Connect standard (OIDC).
The OIDC standard includes a list of attributes that exist on a user type; this
is naturally declared as a Cedar entity type.
With this RFC, anyone could provide a "library" representing Cedar definitions for
OIDC types, and provide that library as a Cedar schema file at some URL; and then
other Cedar users could use those definitions simply by importing the file from that URL.
This would allow the Cedar community to gradually coalesce on the "best" way to
represent an OIDC user in Cedar.

### Motivations common to both scenarios

In both of the above scenarios (within-organization and cross-organization),
we obtain three key benefits:
1. Saving each Cedar user the effort of writing common declarations themselves.
  This facilitates code reuse in schemas, and makes it easier to get started
  with Cedar.
2. Providing a way to define common types and actions in a centralized way,
  which ensures many schemas agree on the "correct" or "best practices"
  definitions, and provides a single place to make updates if updates are
  required.
3. Facilitating code reuse for Cedar authorization calls, not just schemas.
  When everyone shares a common definition of `OIDC::User`, the community could
  conceivably converge on a reusable library function for, e.g., converting an
  OIDC token into Cedar entity data.
  This would further make it easier to get started with Cedar.
  (Note that this RFC does not propose the Cedar team writing or maintaining
  either library definitions for use in schemas or library functions for use in
  Cedar authorization calls. It only points out that the community could
  converge on these things.)

## Detailed design

Import statements are only allowed at the top level, outside of all namespace
declarations.
(In the future, another RFC could propose allowing imports in other positions.)
An import statement (in the human schema format) consists of the keyword
`import`, a single string (surrounded in double-quotes), and a terminating
semicolon (`;`).
The string argument to `import` must be either a local file URI (beginning with
`file:///`), or a remote URL (beginning with either `http://` or `https://`).

The target of the import must be a raw file containing a valid Cedar schema.
This schema may contain any definitions that are valid today in Cedar schemas,
including namespaces, entity type definitions, common type definitions, and
action declarations.
The validator will (at least conceptually) concatenate all of these definitions
into the schema at the location of the `import` statement.

Cedar will autodetect whether the imported schema is a human-format or
JSON-format schema.
(Today, there are no strings that are both valid human-format and valid
JSON-format schemas; this RFC proposes encoding that as a design principle in
perpetuity.)
In particular, all valid JSON-format schemas must have `{` as their first
non-whitespace character, and no valid human-format schemas have `{` as their
first non-whitespace character.

This RFC does not propose any mechanism for versioning libraries.
Instead, it proposes that versioning would be done _above_ the Cedar layer,
i.e., should be the responsibility of library authors.
For instance, library authors could provide a different URL for different
versions of their library, avoiding changing the contents of the URL for the
existing versions of the library.
This RFC doesn't preclude later adding a versioning feature, in which case the
syntax proposed in this RFC would be interpreted as "import the latest version
of this library".

In the JSON format, we do not need to reserve the namespace named `"imports"`:
if `"imports"` maps to a JSON object, it represents the namespace `"imports"`,
while if `"imports"` maps to a JSON array, it represents import statements as
defined in this RFC.

## Drawbacks

1. The Cedar validator, and other tools that rely on schemas, will have to make
network calls in order to perform their jobs. This has availability and latency
implications which may not be acceptable for some users. Of course, those users
could simply not use this feature.
2. Cedar schemas would no longer be self-contained, in that a single (hopefully
readable) file contains all of the relevant definitions. To mitigate this, we
could provide a utility that displays the schema with all imports expanded.
3. The Cedar Rust code would have to bring in substantial new dependencies, so
that it could download libraries from remote URLs. To mitigate this for users
who are concerned about this and don't need/want this feature (e.g., in
resource-constrained environments, offline environments, Wasm, etc), we could
put the remote-URL functionality behind a Cargo feature, so that it and its
dependencies could be opted-into / opted-out-of at compile time. (This RFC
proposes it would be enabled by default, but the Cargo feature would allow users
to compile-time disable it.)
4. Implementation complexity for the Cedar validator and other tools that rely
on schemas.

This is not a breaking change for any existing Cedar users.
All existing valid Cedar schemas remain valid.

## Alternatives

### Alternative A: Distribute libraries without the `import` mechanism

Cedar already supports schemas spread over multiple files, in APIs like
[`Schema::from_schema_fragments()`].
So, users could reasonably easily distribute and use libraries today, without
any `import` mechanism.
When calling Cedar APIs, they would provide library schema files in addition to
the rest of their schema.

### Alternative B: Explicit declaration of human/JSON format, not autodetection

Instead of the autodetection mechanism described above, we could require schema
authors to explicitly indicate whether they are importing a human-format or
JSON-format library.
For instance, in the human schema format, this could look like
```import [json] "https://..."```
(where the absence of `[json]` would indicate the human format, since Cedar
positions that as the default format).

## Unresolved questions

### URI/URL formats

This RFC currently proposes allowing local file URIs beginning `file:///`, and
remote URLs beginning `http://` or `https://`. We could expand this to more options, such as:
- `ftp` URLs
- `file://hostname/<path>` for specifying local-network files (see
  [Wikipedia on "File URI scheme"](https://en.wikipedia.org/wiki/File_URI_scheme))
- other schemes?

We could also restrict this to fewer options, e.g., remove `http://` and require
`https://` only for remote URLs.

[RFC 58]: https://github.com/cedar-policy/rfcs/pull/58
[`Schema::from_schema_fragments()`]: https://docs.rs/cedar-policy/latest/cedar_policy/struct.Schema.html#method.from_schema_fragments
