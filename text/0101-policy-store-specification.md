# Proposal for Policy Store Specification

#### Authors

- Dhaval Desai (@ossdhaval), [Gluu](https://gluu.org)
- Michael Schwartz (@nynymike), [Gluu](https://gluu.org)

#### Contributors

- Victor Moreno (@Swolebrain), [AWS](https://aws.amazon.com/)
- J. Lombardo (@jeffsec-aws), [AWS](https://aws.amazon.com/)
- Imran Siddique (@imran-siddique), [Anthropic](https://anthropic.com)
- Sean McDermott (@smcd), [UnGovr](https://www.ungovr.org/)

## Related issues and PRs

- Reference Issues: None
- Implementation PR(s): (leave this empty)

## Timeline

- Started: TBD
- Accepted: TBD
- Stabilized: TBD

## Summary

This RFC proposes the Policy Store format for distributing authorization policies and their associated evaluation artifacts.

The Policy Store format defines a canonical, PDP-neutral directory structure for organizing Cedar policies and their associated metadata. It provides a common structure to organize policies, schemas, default entities, trusted issuers, and other artifacts required for policy evaluation. Using a well-known structure reduces the need for PDP-specific configuration. It also improves the discoverability and portability of these artifacts across ecosystem tools like policy authoring tools, management, and deployment tools.

This RFC also defines a compressed archive format `.cjar` (Constraint JAR) for packaging a policy store for distribution, versioning, and deployment.

This RFC also defines the behavior of a conforming Policy Decision Point (PDP) that loads a policy store.

## Motivation

Organizations often have multiple teams or areas that write Cedar policies. Along with policies, they maintain schemas, default entities, trusted token issuers, and other metadata required to evaluate those policies using Policy Decision Points (PDPs).

Today, these artifacts are typically organized according to the requirements of the particular PDP in use. As a result, moving to a different Cedar PDP may require restructuring the artifacts or configuring the new PDP to use the existing structure. PDPs built on Cedar, such as [Cedarling](https://docs.jans.io/stable/cedarling/) and [Amazon Verified Permissions](https://aws.amazon.com/verified-permissions/), do not currently share a common structure for organizing, packaging, and versioning these artifacts. This limits portability, auditability, and interoperability between PDPs and ecosystem tools such as policy authoring tools.

### Lack of a recommended method to co-locate and bind policies, schema, and other information

Cedar does not prescribe any method or system that co-locates and binds together the information about the schema and the policies that use that schema. This gives flexibility to combine any schema with any policy at evaluation time. But in practice, more often than not, the policies are targeted to a specific schema, which they use every time.

The lack of a prescribed method to co-locate and bind policies, schema, and other information causes the following problems:

- **Versioning**: To create a cryptographic chain of custody in audit logs, it's critical to know the exact version of the policies and the schema used at evaluation time, for example, when using schema-based entity parsing. Formally binding the policies and schema makes the audit logs clearer.
- **Reasoning**: One of Cedar's key advantages is the ability to formally reason about the composition of policies. Standardizing how policies and their associated schemas are packaged makes it easier to combine and analyze policies across application deployments, identify unintended permissions, and verify organization-wide authorization invariants.
- **Productivity**: Without a common packaging convention, each Cedar integration must implement its own mechanism for organizing, distributing, and loading related authorization assets. Developers must independently manage the lifecycle of policies and schemas, increasing the complexity of testing, deployment, and rollback. Bundling these assets simplifies policy management.
- **Risk**: Without a formal binding, policies may be evaluated against an incompatible or unintended schema, resulting in authorization errors, unintended access, or legitimate requests being denied. Even if policies and schemas are independently validated, their combination may produce behavior that was never tested or approved.
- **Operations**: Without a standard packaging convention, organizations must rely on PDP-specific tools to export, import, distribute, back up, and restore policies and their associated artifacts. Managing these artifacts independently increases operational complexity and the risk of deploying inconsistent or incomplete policy stores.
- **Baseline management**: Even when a PDP maintains its own version history, a versioned policy store establishes a stable baseline against which local changes can be tracked. For example, a sandbox may be provisioned with a standard policy store, which a developer subsequently modifies to allow HTTPS connections to a specific destination. Maintaining the baseline and tracking deltas enables drift detection, impact analysis, and reconciliation with subsequent baseline releases.

This lack of a prescribed method creates even more pain for large organizations, the likely early adopters for Cedar. To maintain order, organizations will need to establish their own conventions and structures for storing policies and schemas. Invariably, this will result in inconsistent storage structures across different organizations or within different teams in the same organization.

Such inconsistency in methods used by organizations will create the following systemic issues in the Cedar ecosystem:

- Reduces PDP interoperability, for example makes it harder to move a policy store from Janssen Project Cedarling to Amazon Verified Permissions and vice versa.
- Impedes the development and deployment of third-party tools that need to access policies and schema. For instance, third-party policy analysis tools, visualization tools, or workflow integration tools like n8n. A uniform method of storing information across teams and organizations will reduce the configuration and customization burden on third-party tools.
- Reduces portability, for instance, a merger between two companies that use different storage methods. Tools and apps written by one organization will not be able to be deployed without the additional effort to unify policy and schema storage methods. Also makes it difficult for policy administrators who work with different teams of the same organization if the teams have their policies and schema stored differently.

### Proposed solution

This RFC proposes to create a new "policy store" specification. The specification will recommend a directory structure that organizes all information required to evaluate an authorization request.

The policy store can be distributed in two formats:

1. **Directory Structure Format**: A folder-based approach where each component (policies, templates, schema, entities) is stored as individual files within a structured directory hierarchy
2. **Archive Format**: A compressed archive (zip file) with the file extension `.cjar`, containing the same directory structure for easy distribution and deployment

See the policy store directory layout below:

```text
policy-store-root/
├── metadata.json                       # Required: Policy store metadata
├── integrity.json                      # Required: Package integrity inventory
├── signatures.json                     # Optional: Provenance Profile requirement
├── policies/                           # Required: Policy files
│   └── (one policy document per file)
├── schema/                             # Optional: Schema files
│   └── (Cedar schema files)
├── templates/                          # Optional: Policy template files
│   └── (one template document per file)
├── entities/                           # Optional: Default entity files
│   └── *.json                          # Entity definition files
└── trusted-issuers.json                # Optional: Trusted issuer configuration
```

A conforming Cedar PDP is one that loads policy stores as defined in this document. When an organization uses this canonical policy store structure to package Cedar policies, schemas, and related metadata, any conforming PDP can consume its policy stores.

[Appendix A](#appendix-a-other-policy-languages-informative) describes how the same format can carry policies written in other policy languages as well.

This document defines version 1.0 of the Policy Store specification.

## Benefits

### Developer-Friendly Organization

The folder-based structure provides several advantages for developers:

- **Individual file editing**: Each policy and template can be edited as a separate file, enabling better IDE support, syntax highlighting, and version control
- **Granular version control**: Git and other VCS systems can track changes to individual policies, providing clearer diff views and blame information
- **Modular development**: Teams can work on different policies simultaneously with fewer merge conflicts
- **Easier debugging**: Issues can be traced to specific policy files rather than searching through large JSON blobs

### Flexible Distribution Options

- **Development format**: Use the directory structure during development for maximum flexibility
- **Deployment format**: Package as a `.cjar` zip file for atomic deployment and distribution
- **Hybrid approach**: Tools can work with either format, converting between them as needed

### Strong versioning

- Authorization evidence must reference the exact version of the policies and schema used to render a decision. Cryptographic binding enables independent verification of the integrity of these artifacts.
- Versioning enables organizations to correlate changes in authorization policy with changes in observed behavior, supporting forensic analysis, risk assessment, and continuous governance.
- Versioning provides a foundation for policy change management, including pre-deployment analysis, approval, controlled rollout, and rollback through existing CI/CD pipelines.
- Immutable policy store versions enable organizations to verify which authorization controls were in effect across application deployments at any given time.

### Create a self-contained unit

The policy store standardizes the structure and metadata format. This helps with deployment, keeping several elements that should not be separated bundled together as one unit, whether as a directory structure or compressed archive.

### Policy grouping and separation of concern

Organizations may create a policy store to group shared policies. This could perhaps help organizations maintain a master set of policies for certain types of applications, for example, a policy store that applies to all Internet-facing web applications. The file-based structure makes it easier to organize policies by domain, team, or functionality.

### Interoperable tools and knowledge

A robust Cedar third party developer ecosystem will help drive broader adoption of Cedar. A standard policy store format will promote interoperability of third-party tools. The file-based approach is more accessible to standard development tools and workflows.

## Detailed design

This section defines the policy store format, an archive format, and the required behavior of conforming PDPs.

The design is detailed in the sections below:

- [Conventions and Definitions](#conventions-and-definitions) section defines requirement keywords and terminology
- [Directory Structure Design](#directory-structure-design) section defines the policy store directory layout and the content of each file
- [Archive Format](#archive-format) section describes how the directory structure is packaged as a `.cjar` archive
- [Loading and Verification](#loading-and-verification) section defines how a conforming PDP loads, verifies, and records a policy store
- [Relationship to Other Authorization Standards](#relationship-to-other-authorization-standards) section relates this specification to other standards
- [Security Considerations](#security-considerations) section describes security requirements and risks
- [Policy store examples](#policy-store-examples) section provides an example Cedar policy store
- [JSON Schemas (Informative)](#json-schemas-informative) section in [Reference](#reference) provides JSON Schemas for the JSON artifacts
- [Appendix A](#appendix-a-other-policy-languages-informative) describes how the format can carry other policy languages

### Conventions and Definitions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174) when, and only when, they appear in all capitals, as shown here.

#### Terminology

- **Policy Store**: A structured collection of policies, schema, and related artifacts bound together for evaluation, as defined in this document.
- **Policy Language**: The language used to author the policies in the policy store. For policy stores defined by this specification, the policy language is Cedar.
- **Directory Format**: A policy store represented as a folder hierarchy on a filesystem.
- **Archive Format**: A policy store directory hierarchy and its contents packaged as a ZIP archive with the `.cjar` file extension. It denotes a **Constraint JAR** — a self-contained package of authorization constraints (policies, schema, and related configuration) for distribution and deployment.
- **Policy Decision Point (PDP)**: A component that evaluates authorization requests against policies. See [RFC 3198](https://www.rfc-editor.org/rfc/rfc3198).
- **Conforming PDP**: A PDP that loads policy stores as defined in this document.
- **Loader**: Any component that loads a policy store. For example, a PDP, a policy authoring tool, or a PAP.
- **Release**: A policy store identified by the tuple (`policy_store.id`, `policy_store.version`, `policy_store.release_id`) in its `metadata.json`. See [Metadata](#metadata).
- **Accepted Release**: A release that the PDP has validated, recorded, and stored, as defined in [Loading, activation, and rollback](#loading-activation-and-rollback).
- **Active Snapshot**: The accepted release that the policy engine evaluates against.
- **Decision Record**: A record, such as an audit log entry, that a PDP produces for an authorization decision. Its required policy store fields are defined in [Decision Records](#decision-records).
- **Policy Administration Point (PAP)**: A component or system used by administrators to manage the lifecycle of policies and related artifacts, including the policy store.
- **Custom Token**: A token that requires specialized processing. For example: non-JWT tokens, API keys, or tokens that use a custom encryption algorithm.
- **Token Processor**: The component that validates and processes a custom token. Its interface and registration mechanism are out of scope for this specification.

### Directory Structure Design

This section defines the policy store directory layout and the content of each file.

This document does not define the syntax and semantics of policies, templates, schemas, or entity types. These are defined by the Cedar language. This document defines only the entity file format ([Entity Files](#entity-files)).

#### Policy Store Directory Structure

The root of a policy store (directory or archive) is referred to as the **policy store root**. The following layout is REQUIRED for conformant policy stores:

```text
policy-store-root/
├── metadata.json                       # Required: Policy store metadata
├── integrity.json                      # Required: Package integrity inventory
├── signatures.json                     # Optional: Provenance Profile requirement
├── policies/                           # Required: Policy files
│   └── (one policy document per file)
├── schema/                             # Optional: Schema files
│   └── (Cedar schema files)
├── templates/                          # Optional: Policy template files
│   └── (one template document per file)
├── entities/                           # Optional: Default entity files
│   └── *.json                          # Entity definition files
└── trusted-issuers.json                # Optional: Trusted issuer configuration
```

#### File Naming Conventions

- **Metadata file**: MUST be named `metadata.json`
- **Integrity file**: MUST be named `integrity.json`
- **Signatures file**: MUST be named `signatures.json`
- **Policy files**: MUST be stored in `policies/` and SHOULD have the `.cedar` extension. File names SHOULD be descriptive but are not required to match policy identifiers
- **Schema files**: MUST be stored in `schema/`. File names follow Cedar conventions (for example, `.cedarschema` for the Cedar schema format or `.cedarschema.json` for the JSON schema format)
- **Template files**: MUST be stored in `templates/` and SHOULD have the extension conventional for the declared policy language
- **Entity files**: MUST be stored in `entities/` and MUST have the `.json` extension
- **Trusted issuer file**: MUST be named `trusted-issuers.json`
- **Archive file**: MUST have the `.cjar` suffix (see [Archive Format](#archive-format))

#### File Content Requirements

- **Metadata file**: REQUIRED. Contains policy store metadata as defined in [Metadata](#metadata).
- **Integrity file**: REQUIRED in both the Directory Format and the Archive Format. Contains the package integrity inventory as defined in [Package Integrity](#package-integrity).
- **Signatures file**: OPTIONAL. Contains provenance and approval signatures as defined in [Provenance Profile](#provenance-profile).
- **Policy files**: REQUIRED. `policies/` contains one or more policy files. Each file MUST contain exactly one Cedar policy, with a stable unique identifier as defined in [Policy Identifiers](#policy-identifiers).
- **Schema files**: OPTIONAL. When `schema/` is present, it MUST contain all Cedar schema artifacts required for the policies in that store. PDPs that require schema MUST reject a policy store that omits `schema/`. 
- **Template files**: OPTIONAL. Used when templates are supported by the policy language. Each file MUST contain exactly one template document in a format valid for the declared `policy_language`, with a stable unique identifier as defined in [Policy Identifiers](#policy-identifiers).
- **Entity files**: OPTIONAL. Each file MUST contain a JSON ([RFC 8259](https://www.rfc-editor.org/rfc/rfc8259)) array of entity definitions, or a single entity definition object (which implementations MAY normalize to an array), as defined in [Entity Files](#entity-files).
- **Trusted issuer file**: OPTIONAL. Contains a map of JSON objects. Each key-value pair describes a token type released by an issuer trusted by the organization, as defined in [Trusted Issuers](#trusted-issuers).

#### Policy Identifiers

Each policy and template in a policy store MUST be uniquely identifiable within that store. Cedar PDPs typically require an `@id()` annotation in each policy file.

Tools MUST preserve policy files without altering policy identifiers.

#### Entity Files

Each entity definition has the following members:

- `uid`: REQUIRED object with `type` and `id` string fields identifying the entity by its Cedar entity type and entity ID.
- `attrs`: REQUIRED object containing entity attributes.
- `parents`: OPTIONAL array of parent entity references for hierarchical relationships. Each reference is an object with `type` and `id` string fields.
- `tags`: OPTIONAL object mapping tag names to tag values. Each value MUST conform to the tag type that the policy store's schema declares for the entity type.

PDPs MAY map this interchange format to engine-native entity representations on load.

An informative JSON Schema for entity files is in [Entity File Schema](#entity-file-schema).

#### Metadata

The `metadata.json` file provides version and descriptive metadata for the policy store. An informative JSON Schema is in [metadata.json Schema](#metadatajson-schema).

##### Metadata structure

The top-level JSON object MUST contain the following keys:

| Key | Description |
| :--- | :--- |
| `policy_store_spec_version` | REQUIRED string. Version of the Policy Store specification that this policy store conforms to. This revision of the specification defines the value `"1.0"`. |
| `policy_language` | REQUIRED string. Identifies the policy language. For policy stores defined by this specification, the value MUST be `"cedar"`. |
| `policy_language_version` | REQUIRED string. Version of the Cedar language used by artifacts in this store (for example, `"4.4.0"`). This is the Cedar language version, not the version of a Cedar SDK or PDP. |
| `policy_store` | REQUIRED object containing policy store metadata fields defined below. |
| `governance` | OPTIONAL object containing governance-related metadata fields defined below. |

###### policy_store Object

| Key | Description |
| :--- | :--- |
| `id` | REQUIRED string. A unique identifier for the policy store. It MUST be a URI conforming to [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986), either a URL (for example, `https://example.com/apps/analytics/policystore/`) or a URN (for example, `urn:acme:policystore:analytics`), and MUST uniquely identify the policy store. Values are compared by exact string match. |
| `name` | REQUIRED string. A human-readable name for the policy store. |
| `description` | OPTIONAL string. A human-readable description. |
| `version` | REQUIRED non-empty string. A publisher-assigned version label (for example, `"1.2.0"`), scoped to `policy_store.id`. The version is a human-readable label; it is not an exact content identity. A version MAY have several releases, distinguished by `release_id`, each with its own `package_digest` ([Package digest](#package-digest)). See [Loading, activation, and rollback](#loading-activation-and-rollback) for more details. |
| `release_id` | REQUIRED non-empty string. A publisher-assigned identifier that distinguishes releases of the same version, so that a publisher can iterate on a version without changing its label. It MUST be unique within the pair (`policy_store.id`, `policy_store.version`); it need not be globally unique. The tuple (`policy_store.id`, `policy_store.version`, `policy_store.release_id`) identifies a release. |
| `created_date` | OPTIONAL string. Date-time when the policy store was created, in the `date-time` format of [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339). |

Implementations MUST NOT add additional top-level keys to `metadata.json` unless documented by a future revision of this specification. The `policy_store` object MUST NOT contain keys other than those defined here unless documented by a future revision.

###### governance Object

| Key | Description |
| :--- | :--- |
| `owner` | REQUIRED string. A URN identifier that uniquely identifies an organizational entity accountable for the policy store. |
| `author` | REQUIRED string. A URN identifier that uniquely identifies an organizational entity that is responsible for creating or updating the policy store. |
| `policy_domain` | REQUIRED string. A URN identifier for the domain or the area within the organization to which the policies in the policy store apply. |
| `jurisdictions` | OPTIONAL non-empty array of unique strings. The jurisdictions whose law the organization has determined applies to authorization decisions made under this policy store. See [Jurisdictions](#jurisdictions). |

###### Jurisdictions

Each element of `governance.jurisdictions` MUST be a two-letter lowercase code that corresponds to an ISO 3166-1 alpha-2 country code (for example, `us` or `ke`). Values are compared by exact string match. 

`jurisdictions` differs from `policy_domain`. `policy_domain` identifies the organizational domain to which the policies apply. `jurisdictions` identifies the legal systems that govern decisions made under the store. It also differs from the location where a PDP runs, which this specification does not record.

`jurisdictions` is informational:

- A PDP MUST NOT use it to evaluate authorization requests.
- A loader MUST reject a policy store in which `jurisdictions` is present but is not an array of unique strings that match `^[a-z]{2}$`.
- A loader SHOULD report, but MUST NOT reject for, a code that is not an assigned ISO 3166-1 alpha-2 code.
- The basis for a listed jurisdiction, such as the statute and provision that apply, is not recorded in the policy store. Organizations record it in their control mapping.

###### Metadata example (non-normative)

```json
{
  "policy_store_spec_version": "1.0",
  "policy_language": "cedar",
  "policy_language_version": "4.4.0",
  "policy_store": {
    "id": "https://example.com/apps/analytics/policystore/",
    "name": "Acme Analytics Web Application",
    "description": "Policies for the analytics web application.",
    "version": "1.2.0",
    "release_id": "2025-01-15-main-a1b2c3",
    "created_date": "2025-01-15T10:30:00Z"
  },
  "governance": {
    "owner": "urn:acme:team:policy-owners",
    "author": "urn:acme:team:policy-authors",
    "policy_domain": "urn:example:application:analytics",
    "jurisdictions": ["us", "ke"]
  }
}
```

#### Trusted Issuers

The `trusted-issuers.json` file identifies the token issuers and token types trusted by the policy store. A PDP MAY use this configuration to validate JWTs ([RFC 7519](https://www.rfc-editor.org/rfc/rfc7519)) or any other kind of artifact and map their claims to Cedar entities for use in policy evaluation.

An informative JSON Schema is provided in [Trusted Issuer Schema](#trusted-issuer-schema).

##### Trusted issuers structure

`trusted-issuers.json` contains a map of JSON objects.

The key of each map entry names an entity type, defined in the policy store's schema, that this token is materialized as (for example, `Acme::Id_Token`).

A schema entity type name MUST NOT be declared by more than one map entry within `trusted-issuers.json`. Because map keys are JSON member names, a loader MUST detect duplicate member names while parsing and reject the policy store, rather than relying on a parser that silently keeps one of the values.

The value of each map entry is a JSON object that describes a token released by an issuer trusted by the organization. This specification defines the following members:

- `typ`: REQUIRED non-empty string. The type of token released by the issuer. Valid values are `jwt` for JSON Web Tokens or `custom` for non-JWT tokens. Values are compared case-insensitively and producers SHOULD emit lowercase values. This member should not be confused with the JOSE header parameter `typ` ([RFC 7515](https://www.rfc-editor.org/rfc/rfc7515)).
- `issuer`: REQUIRED string. An identifier for the issuer that matches the regular expression `^[A-Za-z_][A-Za-z0-9_]*$`.
- `configuration_endpoints`: REQUIRED object when `typ` is `jwt`, OPTIONAL when `typ` is `custom`. For a `custom` token, the token processor decides whether and how to use it. For type `jwt`, describes where the issuer's signing keys are obtained and which `iss` claim value is expected. When present, the object MUST use exactly one of the following forms:

  - Discovery form: the object contains only `openid_configuration`, the `https` URI ([RFC 3986](https://www.rfc-editor.org/rfc/rfc3986)) of the issuer's OpenID Connect discovery document, ending in `/.well-known/openid-configuration`. The PDP obtains signing keys from the `jwks_uri` in that document. 
  - Static form: the object contains `jwks`, the `https` URI ([RFC 3986](https://www.rfc-editor.org/rfc/rfc3986)) of the issuer's JSON Web Key Set, and `iss`, the issuer's `https` URL (for example, `https://idp.example.com`). Both members are REQUIRED. The PDP obtains signing keys from `jwks` and expects the token's `iss` claim to equal `iss`.

  In both forms, the PDP compares the expected value with the token's `iss` claim by exact string comparison.
- `token_id`: The name of the claim that uniquely identifies a token of this type, so that every token can be referred to, for example in a decision record.
  - When `typ` is `jwt`, it is an OPTIONAL string that names a claim in the JWT payload. It defaults to `jti`.
  - When `typ` is `custom`, it is a OPTIONAL string that names a claim in the token processor's output. It has no default. The named claim MUST be present in the output, whether or not `required_claims` lists it.
- `required_claims`: OPTIONAL array of claim names that MUST be present for the token to be considered valid. Claim names MUST NOT repeat within the array. For `jwt` tokens, these are claims in the JWT payload, and the PDP also validates the values of registered claims as defined in Section 4.1 of [RFC 7519](https://www.rfc-editor.org/rfc/rfc7519). For `custom` tokens, these are claims in the output of the token processor ([Custom token type](#custom-token-type)). The list is a minimum. It does not restrict the claims that a token or a token processor's output may contain.

Declaring a token type does not require an authorization request to present a token of that type. Every declared token type is optional at evaluation time.

Organizations MAY add extension fields to any map entry. Extension fields are expected for `custom` tokens, because this specification cannot anticipate the information that a token processor needs. For example, an entry might carry the root certificate authority that the processor uses to validate a chain of signed tokens. The following rules apply:

- An extension field MUST NOT alter the meaning of a field defined in this specification.
- Extension field names SHOULD begin with `x-`, so that they cannot collide with fields that a later revision of this specification defines.
- A PDP MUST NOT reject a policy store because an entry contains an extension field that the PDP does not recognize.
- This specification does not define the meaning of any extension field. The token processor for a `custom` token MAY read the extension fields of that token's entry.
- Interoperable tools SHOULD preserve unknown fields when reading and writing policy stores.

Extension fields are part of `trusted-issuers.json`, so they are covered by its digest in `integrity.json` and by the package digest.

###### Trusted issuers example (non-normative)

The following `trusted-issuers.json` declares two entity types. `Acme::Id_token` is a JWT that the PDP validates using the issuer's OpenID Connect discovery document. `Lapis::federation_chain_token` is a `custom` token that a token processor validates.

```json
{
  "Acme::Id_token": {
    "typ": "jwt",
    "issuer": "Acme",
    "configuration_endpoints": {
      "openid_configuration": "https://idp.example.com/.well-known/openid-configuration"
    },
    "token_id": "jti",
    "required_claims": ["jti", "iss", "aud", "sub", "exp"]
  },
  "Lapis::federation_chain_token": {
    "typ": "custom",
    "issuer": "Lapis",
    "token_id": "chain_token_id",
    "configuration_endpoints": {
      "jwks": "https://anchor.federation.example.org/jwks.json",
      "iss": "https://anchor.federation.example.org"
    },
    "required_claims": [
      "chain_token_id",
      "chain_id",
      "federation_id",
      "sub",
      "origin_issuer",
      "issuer_chain",
      "hop_count",
      "trust_anchor",
      "chain_digest",
      "validated_at",
      "exp"
    ],
    "x-root-ca": {
      "uri": "https://pki.federation.example.org/root-ca.pem",
      "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    },
    "x-max-hops": 5
  }
}
```

In the `Lapis::federation_chain_token` entry:

- `token_id` names `chain_token_id`, the claim in the token processor's output that identifies the token.
- `configuration_endpoints` gives the key set of the federation's trust anchor. It is optional for a `custom` token, and the processor decides how to use it.
- `required_claims` lists the minimum output of the processor. It includes identifiers (`chain_token_id`, `chain_id`, `federation_id`, `sub`) and provenance (`origin_issuer`, `issuer_chain`, `hop_count`, `trust_anchor`, `chain_digest`, `validated_at`). The processor may return more claims.
- `x-root-ca` and `x-max-hops` are extension fields. `x-root-ca` identifies the root certificate authority that the processor validates the chain against, with the SHA-256 digest of its certificate. `x-max-hops` limits the number of links in the chain. A PDP does not interpret them.

The next example declares `Acme::Access_token` with the static form instead of the discovery form. The PDP obtains signing keys directly from the `jwks` URI and expects the token's `iss` claim to equal `iss`. A `trusted-issuers.json` declares a given entity type only once, so this example is an alternative to the first entry above, not an addition to the same file.

```json
{
  "Acme::Access_token": {
    "typ": "jwt",
    "issuer": "Acme",
    "configuration_endpoints": {
      "jwks": "https://idp.example.com/.well-known/jwks.json",
      "iss": "https://idp.example.com"
    },
    "token_id": "jti",
    "required_claims": ["jti", "iss", "aud", "sub", "exp"]
  }
}
```

##### Custom token type

The `custom` token type describes a token that the PDP cannot validate using JSON Web Token ([RFC 7519](https://www.rfc-editor.org/rfc/rfc7519)) mechanisms. These tokens require specialized processing. Examples include CBOR Web Tokens, vendor-specific or legacy token formats, or artifacts like JWT trust chains.

Like all other map entries in `trusted-issuers.json`, a map entry for a custom token describes the schema entity types those tokens should be mapped to during policy evaluation. A PDP validates a custom token using a token processor.  A token processor contains the logic to interpret and validate custom tokens, and how a custom token is materialized as a Cedar entity. A token processor's output is a set of named claims; `required_claims` refers to those names. 

The output MAY contain claims in addition to those in `required_claims`. This specification does not limit their names, number, or value types, because it cannot anticipate the information that a deployment's custom tokens carry. A PDP MUST NOT reject a custom token, or a policy store, because the processor output contains a claim that `required_claims` does not list. How a PDP makes additional claims available to policy evaluation, for example as attributes of the entity that the token is materialized as, is outside the scope of this specification.

Consistent with the scope of this specification, this section defines policy store configuration for custom token types only. It does not define how a PDP validates a custom token, how a token processor is implemented or registered.

###### PDP Support

A custom token configuration in the `trusted-issuers.json` does not identify the token processor that handles a given entity type; the binding between a declared type and a processor is deployment configuration outside the policy store.

Because of this, a PDP loading a policy store that declares tokens of `custom` type is responsible for determining whether it can process each declared entity type. A PDP SHOULD perform this check while loading the policy store and reject the store if it cannot, rather than deferring the failure to the first evaluation request that presents such a token.

#### Package Integrity

Every policy store MUST contain the reserved root file `integrity.json`, which inventories the files of the store along with their computed SHA-256 digest. This file enables the integrity check of each file inside the policy store at the time of loading by the PDP. At the time of loading the policy store, a PDP MUST recompute the SHA-256 digest of each file and compare it with the digest recorded in `integrity.json`.

Example `integrity.json` for the [example Cedar policy store](#example-cedar-policy-store) is shown below:

```json
{
  "policy_store_spec_version": "1.0",
  "files": {
    "metadata.json": {
      "sha256": "c4ddf8db41b073f53f7dd164ecf3eb77f3615d736219948154c33de5d0c8f9d2",
      "media_type": "application/json",
      "critical": true
    },
    "schema/app.cedarschema": {
      "sha256": "4fc78b6079bd00946985ed36676c4d5e0448c9b4ff29a8889db586ff2890dba4",
      "media_type": "text/plain",
      "critical": true
    },
    "policies/alice-read-access.cedar": {
      "sha256": "3e7b54f202481240fcbcdcc16847b19a9de3a5239cb051f5eb199b352f6451ed",
      "media_type": "text/plain",
      "critical": true
    },
    "policies/jack-search-access.cedar": {
      "sha256": "cc05a9c1be08eec692df00d45ce4262bf373e6c9a15e138d4edad5e7b50cc739",
      "media_type": "text/plain",
      "critical": true
    },
    "entities/default-roles.json": {
      "sha256": "04d7a75579b21cf84289a365a7d113201ced13b82790229ac2a212c02220c32c",
      "media_type": "application/json",
      "critical": true
    },
    "trusted-issuers.json": {
      "sha256": "754dc83765da5421f6a8592cc0858a2d9ef2dc41172a92adfd4935c6eb9baf7c",
      "media_type": "application/json",
      "critical": true
    }
  }
}
```

##### Inventory and content identity

`integrity.json` MUST be a UTF-8 JSON object satisfying the input constraints of [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785). Duplicate JSON property names MUST be rejected before they can be discarded by a parser. Its only members are:

| Member | Requirement |
| :--- | :--- |
| `policy_store_spec_version` | REQUIRED string. The version of this specification that the inventory conforms to. It MUST equal `policy_store_spec_version` in `metadata.json`. |
| `files` | REQUIRED object mapping relative file paths to artifact descriptors. |

Each descriptor MUST contain exactly these members:

| Member | Requirement |
| :--- | :--- |
| `sha256` | REQUIRED string of 64 lowercase hexadecimal characters, the SHA-256 digest of the exact uncompressed file bytes. |
| `media_type` | REQUIRED non-empty media type string describing the artifact representation. |
| `critical` | REQUIRED boolean indicating that the loader must understand and process the artifact to accept the store. |

`files` MUST inventory every regular file, including `metadata.json`, except `integrity.json` and `signatures.json`. It MUST NOT inventory directories or either of those two files. Missing files, unlisted files, duplicate paths, and digest mismatches MUST cause rejection. The inventory is subject to the same [path rules](#safe-package-paths) as the package.

`metadata.json` MUST have media type `application/json` and `critical: true` because it binds together the store identifier, version, release identifier, policy language and version, and governance claims. All policy, schema, template, entity, and issuer artifacts used for evaluation MUST be critical. A loader MUST reject a critical artifact whose representation or role it cannot process. Non-critical artifacts MAY be ignored semantically, but their bytes MUST still be verified. A media type such as `application/octet-stream` describes opaque bytes; it does not show that a loader understands them.

#### Package digest

The package digest applies to every policy store, whether or not the [Provenance Profile](#provenance-profile) is in effect. Every PDP computes the package digest during [Policy Store Loading](#policy-store-loading) and uses it in release and decision records.

The package digest is `sha256:` followed by the lowercase hexadecimal SHA-256 digest of the UTF-8 JCS serialization of the entire `integrity.json` object ([RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)).

The digest identifies the inventoried content and descriptors. ZIP compression, ZIP entry order, and JSON object-member ordering in `integrity.json` do not change it. Changing an artifact's bytes, path, media type, or criticality does. Signatures in `signatures.json` ([Provenance Profile](#provenance-profile)) are excluded to avoid a circular digest and permit approvals to be added without changing content identity. A digest alone does not authenticate its producer.

The package digest does not depend on the bytes of the `.cjar` archive. A tool MUST NOT use a hash of the archive file as a substitute for it.

Because `metadata.json` is inventoried in `integrity.json`, any change to the `metadata.json` changes the package digest. Hence, two releases that differ in `policy_store.version` or `policy_store.release_id` always have different package digests. Identical content therefore cannot be re-tagged as a new release without changing its digest.

#### Provenance Profile

Package integrity shows that the files match `integrity.json`, but not who produced the release or whether it was approved. The Provenance Profile lets a PDP verify a release's producer and approvers, and detect tampering, without relying on a package digest obtained out of band.

The Provenance Profile adds one reserved root file, `signatures.json`, which carries signatures over the [package digest](#package-digest) (`package_digest`). [Provenance Verification](#provenance-verification) defines how a loader verifies these signatures.

##### Signature file format

`signatures.json` MUST be a UTF-8 JSON array of JWS Compact Serialization strings ([RFC 7515](https://www.rfc-editor.org/rfc/rfc7515)), with at least one element. Duplicate JSON members MUST be rejected in decoded protected headers and payloads. Each JWS payload MUST be a UTF-8 JSON object containing exactly these three string members:

| Member | Requirement |
| :--- | :--- |
| `profile` | MUST be `policy-store-provenance-1`. |
| `package_digest` | The package digest computed as defined in [Package digest](#package-digest). |
| `purpose` | Either `provenance` or `approval`. |

Each protected header MUST contain exactly `alg` and `kid`. The latter is a non-empty identifier resolved against deployment-configured verification keys. This profile uses standard base64url-encoded JWS payloads; detached or unencoded payloads are not supported. Implementations MUST support ES256 as defined in [RFC 7518](https://www.rfc-editor.org/rfc/rfc7518). Other digital-signature algorithms MAY be permitted by deployment policy. The `none` algorithm and shared-secret MAC algorithms MUST NOT be accepted.

The following sample `signatures.json` carries one provenance signature and one approval signature. The digest and signature values are illustrative.

```json
[
  "eyJhbGciOiJFUzI1NiIsImtpZCI6ImFjbWUtcmVsZWFzZS0yMDI2In0.eyJwcm9maWxlIjoicG9saWN5LXN0b3JlLXByb3ZlbmFuY2UtMSIsInBhY2thZ2VfZGlnZXN0Ijoic2hhMjU2OjUwZDg1OGUwOTg1ZWNjN2Y2MDQxOGFhZjBjYzVhYjU4N2Y0MmMyNTcwYTg4NDA5NWE5ZThjY2FjZDBmNjU0NWMiLCJwdXJwb3NlIjoicHJvdmVuYW5jZSJ9.havHcBwB_HJMHdkrqDZJPUixI7JqFX5DBzeLyfR2GPkRAlTb0oZ6WffOhY9S4L2LtK7a-C6LJ4Ry6ErSS7f2vw",
  "eyJhbGciOiJFUzI1NiIsImtpZCI6ImFjbWUtc2VjdXJpdHktYXBwcm92ZXIifQ.eyJwcm9maWxlIjoicG9saWN5LXN0b3JlLXByb3ZlbmFuY2UtMSIsInBhY2thZ2VfZGlnZXN0Ijoic2hhMjU2OjUwZDg1OGUwOTg1ZWNjN2Y2MDQxOGFhZjBjYzVhYjU4N2Y0MmMyNTcwYTg4NDA5NWE5ZThjY2FjZDBmNjU0NWMiLCJwdXJwb3NlIjoiYXBwcm92YWwifQ.yYi5gAYA_SGtdiAx1CmGTydutnewz7H8M_0Lp5jBd4dF3lJCgEHyBBThDJB7fqzIXdw36DY0WkXne86moVMoog"
]
```

In the decoded form, the first element's protected header and payload are:

```json
{"alg": "ES256", "kid": "acme-release-2026"}
```

```json
{
  "profile": "policy-store-provenance-1",
  "package_digest": "sha256:50d858e0985ecc7f60418aaf0cc5ab587f42c2570a884095a9e8ccacd0f6545c",
  "purpose": "provenance"
}
```

The second element's protected header and payload are:

```json
{"alg": "ES256", "kid": "acme-security-approver"}
```

```json
{
  "profile": "policy-store-provenance-1",
  "package_digest": "sha256:50d858e0985ecc7f60418aaf0cc5ab587f42c2570a884095a9e8ccacd0f6545c",
  "purpose": "approval"
}
```

### Archive Format

The Archive Format packages the Directory Format as a ZIP archive (Constraint JAR, `.cjar`).

- The archive MUST use the ZIP format and `.cjar` file extension.
- Paths inside the archive MUST match the Directory Format layout relative to the policy store root.
- The archive MUST NOT require extraction to a specific absolute path; relative paths MUST be preserved.
- Archive file names SHOULD follow the pattern `{policy-store-name}-{version}-{release_id}.cjar` where `policy-store-name` is a file-name-safe label for the store, `version` matches `policy_store.version` and `release_id` matches `policy_store.release_id` in `metadata.json`. The file name is a convenience only; it is not authoritative and MUST NOT override `policy_store.version`, `policy_store.release_id`, or the [`package_digest`](#package-digest).

### Loading and Verification

This section defines how a conforming PDP loads, verifies, accepts, and records a policy store.

#### Policy Store Loading

PDPs and tools that load policy stores MUST perform steps 1 through 11 below, in order. They SHOULD perform step 12, as described in [Custom token type](#custom-token-type).

1. Detect format (directory or `.cjar` archive), enforce [Safe Package Paths](#safe-package-paths), and normalize to an isolated directory view.
2. Verify required files and directories exist.
3. Verify `integrity.json` as defined in [Package Integrity](#package-integrity). The loader selects the inventory and digest rules from `policy_store_spec_version` in `integrity.json`, because `metadata.json` is not yet verified at that point. The loader MUST reject a value it does not implement. The loader MUST confirm that `metadata.json` is present in the inventory and that its bytes match before using any metadata value.
4. The PDP MUST compute the [package digest](#package-digest) of every policy store it loads, including when the Provenance Profile is not in effect, because acceptance and decision records use it.
5. Parse and validate `metadata.json`, including `governance.jurisdictions` when present ([Jurisdictions](#jurisdictions)).
6. Confirm the implementation supports the declared `policy_store_spec_version`. A PDP MUST reject a policy store whose `policy_store_spec_version` it does not implement. The loader MUST also reject the store if the `policy_store_spec_version` values in `metadata.json` and `integrity.json` differ.
7. Apply the deployment's provenance requirement and, when `signatures.json` is present or provenance is required, verify the [Provenance Profile](#provenance-profile) as defined in [Provenance Verification](#provenance-verification). Complete verification before loading artifacts into the policy engine.
8. Confirm the implementation supports the declared `policy_language` and `policy_language_version`, or reject the store.
9. If present, load `schema/`; then load policies and optional templates, entities, trusted issuers, and custom token types according to policy engine rules.
10. Verify policy engine-specific requirements if any (such as unique policy identifiers).
11. Verify that no schema entity type is declared by more than one map entry in `trusted-issuers.json`.
12. If `trusted-issuers.json` defines any `custom` type tokens ([Custom token type](#custom-token-type)), then determine whether the implementation can process each declared entity type.

Failure at any step that the loader performs MUST result in rejecting the policy store for evaluation. Rejection MUST leave the previously active store unchanged.

The PDP records accepted and activated releases as defined in [Loading, activation, and rollback](#loading-activation-and-rollback), using values from the verified `metadata.json` bytes and the computed `package_digest`.

#### Safe Package Paths

These requirements apply to both signed and unsigned stores. Loaders MUST validate entry names before extraction or opening files. A path MUST be relative to the store root, use `/` as its separator, and contain no empty, `.` or `..` component. Absolute paths, drive-qualified paths, backslashes, NUL, and control characters MUST be rejected. Loaders MUST NOT percent-decode paths or otherwise repair invalid paths into valid ones.

Loaders MUST reject duplicate file paths, file/directory conflicts, and paths that alias one another under the target filesystem's rules, including case folding and Unicode normalization. Names interpreted as device names or alternate data streams, and names that cannot be represented without filesystem rewriting, MUST be rejected. An explicit ZIP directory entry MAY end in one `/`; remove only that trailing separator when validating its directory name. Conflicting ZIP local-header and central-directory names MUST be rejected.

Only regular files and directories are permitted. Symbolic links, hard links, device entries, and filesystem reparse points MUST be rejected. Loaders MUST prevent writes or reads outside an isolated store root, including through pre-existing links. They MUST enforce configured limits on entry count, total uncompressed bytes, individual file size, and decompression work before accepting a store.

Verification and subsequent loading MUST use the same immutable snapshot of file bytes. Verifying a directory and later reopening mutable paths is insufficient. Archive metadata, executable bits, timestamps, and entry order MUST NOT affect policy evaluation.

#### Loading, activation, and rollback

A loader loads a policy store as defined in [Policy Store Loading](#policy-store-loading).

On successful load, the PDP MUST record the tuple (`policy_store.id`, `policy_store.version`, `policy_store.release_id`, `package_digest`), subject to the rules in [Load outcomes](#load-outcomes).

A PDP can hold several accepted releases with the same `policy_store.id` and `policy_store.version`, distinguished by `policy_store.release_id`. This lets a publisher iterate on a version without changing its version number. Activation selects which of these releases the policy engine evaluates against. On activation, the PDP MUST record the tuple of the release it makes active.

Selection and activation of a release are PDP concerns and out of scope for this specification. Publishing, fetching, uploading, approving, and activating are separate permissions. Any mechanism that delivers a policy store to a PDP remains subject to administrative authentication and authorization; accepting a package MUST NOT grant its producer permission to activate it. This specification adds no activation, rollback, or revocation mechanism and no ability for a resource to push policy into a PDP.

When a deployment supports rollback, which activates an earlier accepted release, each rollback MUST be authorized through the deployment's administrative process and logged with the selected digest.

##### Load outcomes

The PDP validates the policy store and its metadata as defined in [Policy Store Loading](#policy-store-loading), and computes the `package_digest` ([Package digest](#package-digest)). The PDP MUST apply the following outcome, based on whether the tuple (`policy_store.id`, `policy_store.version`, `policy_store.release_id`) has already been recorded:

| Condition | Outcome |
| :--- | :--- |
| The tuple is new and the policy store is valid. | The PDP accepts and stores the release. |
| The tuple is already recorded with the same `package_digest`. | The load is idempotent and nothing new is stored. |
| The tuple is already recorded with a different `package_digest`. | The PDP rejects the policy store. |
| The policy store fails validation. | The PDP rejects the policy store. |

The PDP SHOULD report the outcome to the party that supplied the policy store, together with the `policy_store.id`, `policy_store.version`, and `policy_store.release_id` from the verified `metadata.json` and the computed package digest.

Before supplying the policy store to the PDP, the policy administrator SHOULD ensure the validity of the policy store and correct version management.

This specification does not define updates or deletion of existing policy store releases. Policy store lifecycle management is out of scope for this specification. To change the content of a release, the publisher creates a new release, distinguished by `release_id`.

##### Release records

A conforming PDP MUST record each accepted release with the following members:

- `id`: REQUIRED. The `policy_store.id` from the verified `metadata.json`.
- `version`: REQUIRED. The `policy_store.version` from the verified `metadata.json`.
- `release_id`: REQUIRED. The `policy_store.release_id` from the verified `metadata.json`.
- `package_digest`: REQUIRED. The computed [package digest](#package-digest).
- `provenance_verified`: REQUIRED boolean. `true` when the release was accepted with a verified [Provenance Profile](#provenance-profile), otherwise `false`.
- `active`: OPTIONAL boolean. `true` when the release is the active snapshot that the PDP evaluates against. Selection and activation of a release are PDP concerns; a PDP that has no such concept omits this member.

The PDP SHOULD enable authorized PDP administrators or a PAP system to read information about policy store releases accepted by the PDP. The mechanism to read this information is out of scope for this specification.

##### Active snapshot and rollout

Acceptance and activation are distinct. Accepting a release records and stores it; activation makes one accepted release the active snapshot that the policy engine evaluates against. Accepting a newer release does not change the active snapshot until that release is activated.

For the purpose of decision evidence, the content a PDP "used" for a decision is the release of its active loaded snapshot at decision time. During a rollout, when a newer release has been accepted but not yet activated, the PDP MUST report the `policy_store.version` and `package_digest` of the currently active snapshot, not those of the newer, not-yet-activated release. A single decision MUST be evaluated entirely against one active snapshot. See [Decision Records](#decision-records) for the values a decision record carries.

#### Provenance Verification

A deployment MAY accept stores without the [Provenance Profile](#provenance-profile), but MUST configure that decision outside the incoming package. If `signatures.json` is present, the complete profile MUST be verified or the store rejected. A loader that does not support the profile MUST reject stores that contain `signatures.json`. A provenance-required deployment MUST reject a store whose `signatures.json` is missing; it MUST NOT retry it as an unsigned store.

##### Provenance and approvals

Each [`signatures.json`](#signature-file-format) array element MUST be structurally valid and bind the computed package digest and profile. Unknown keys or locally disallowed algorithms do not count toward acceptance. A signature using a configured key and permitted algorithm MUST verify or the package MUST be rejected. Acceptance MUST require at least one verified provenance signature from an authorized producer and every approval required by local policy. Distinct-approver thresholds MUST count independently authorized principals, not signatures or keys; multiple keys belonging to one principal count once.

The deployment MUST define which keys may assert provenance or approval for the expected store identifier and `governance.policy_domain`. It MUST select the expected store and policy domain from the authenticated administrative request or local configuration, then compare them with the verified metadata. It MUST NOT let package-supplied identifiers select a less restrictive trust policy. An approval signature does not by itself authorize upload or activation.

The `governance.owner` and `governance.author` URNs, and the `governance.jurisdictions` codes, are claims. A verified signature shows only that an authorized key signed the package digest. It does not show who holds that key. The deployment's own identity and authorization policy links each key to an organization or an accountable role.

##### Trust configuration

Trust anchors, permitted algorithms, approval thresholds, key validity periods, and revocation status MUST be managed outside the incoming package. Key rotation MAY allow a configured overlap, but a package cannot introduce its own replacement trusted key. A revoked key MUST NOT count toward new acceptance. Previously activated content requires a deployment decision when its signer is revoked; this format does not provide a revocation service. If required current trust information is unavailable, the loader MUST reject the policy store.

##### Freshness and rollback

When the profile is in effect, the loader MUST confirm that `metadata.json` is in the inventory bound by the verified signatures before treating any metadata value as authenticated.

A valid old signature remains cryptographically valid. Deployments MUST apply an external freshness or rollback policy for the expected store and record the accepted digest. A signed version string or creation date alone is insufficient. A missing signature, unsupported profile, or failed verification MUST NOT cause a downgrade to unsigned acceptance.

##### Validation cases for implementers

The following are test requirements, not a claim that a conformance suite or interoperable implementations exist. Begin with a structurally valid store, an authorized provenance signer, all locally required approvals, and a configured expected store and policy domain. Unless stated otherwise, change only the indicated input.

| Case | Expected result |
| :--- | :--- |
| Unmodified package with current authorized signatures | Accept after base-format and engine validation. |
| Repack ZIP with different compression and entry order | Same package digest; accept. |
| Reorder inventory JSON properties without changing values | Same package digest; accept. |
| Change one policy byte or metadata governance claim | Reject artifact digest mismatch. |
| Change artifact bytes and update the inventory hash, keeping old signatures | Reject signed package-digest mismatch. |
| Omit an inventoried file or add an unlisted regular file | Reject inventory mismatch. |
| Delete `integrity.json` | Reject missing required file. |
| Use `../outside`, `/absolute`, `C:/outside`, or a backslash path | Reject before extraction. |
| Repeat a ZIP path, duplicate a JSON member, or introduce a file/directory collision | Reject before ambiguous data is consumed. |
| Add a link entry or mutate the directory after verification | Reject; never evaluate unverified bytes. |
| Supply an unsupported critical artifact with otherwise valid signatures | Reject unsupported artifact. |
| Change the signature profile identifier, set an unsupported `policy_store_spec_version` in `integrity.json`, or add an unknown inventory member | Reject unsupported profile or structure. |
| Set `policy_store_spec_version` in `integrity.json` to a value that differs from `metadata.json` | Reject version mismatch. |
| Alter a signature under a trusted, permitted key | Reject cryptographic verification failure. |
| Sign only with an unknown or revoked key | Reject unmet provenance or approval policy. |
| Supply provenance but remove a required approval | Reject unmet approval policy. |
| Repeat one approval to meet a distinct-approver threshold | Reject unmet threshold. |
| Delete `signatures.json` where local policy requires provenance | Reject attempted unsigned downgrade. |
| Replay an older valid package disallowed by local rollback policy | Reject despite valid signatures. |
| Change metadata to a different store with weaker trust settings | Reject expected-store mismatch. |
| Load a new `release_id` for an already recorded (`policy_store.id`, `version`) | Accept as a new release. |
| Reload the same (`policy_store.id`, `version`, `release_id`, `package_digest`) | Accept as idempotent; no new content identity. |
| Reuse the same (`policy_store.id`, `version`, `release_id`) with a different `package_digest` | Reject release-digest conflict. |

##### Questions for review

This draft proposes the reserved file name `signatures.json`, the profile identifier `policy-store-provenance-1`, JWS Compact Serialization as the signature envelope, and ES256 as the mandatory algorithm. Reviewers should confirm these choices before the profile is finalized. Remaining open items are listed in [Unresolved questions](#unresolved-questions).

#### Decision Records Recommendations

A PDP that produces a [decision record](#terminology) for an authorization decision SHOULD include the `policy_store.id`, the `policy_store.version`, and the [`package_digest`](#package-digest) of the active loaded snapshot used to reach that decision. It SHOULD also include the `policy_store.release_id`. The id identifies the policy store, the version records the human-readable release label, the release identifier distinguishes releases of the same version, and the `package_digest` lets audit evidence verify the exact policy content that was used.

The PDP SHOULD also record whether the active snapshot was accepted with a verified [Provenance Profile](#provenance-profile).

Consistent with [Loading, activation, and rollback](#loading-activation-and-rollback), "the active loaded snapshot used" is the snapshot active at decision time. When a newer release has been accepted but not activated, the decision record SHOULD report the version and digest of the currently active snapshot.

### Relationship to Other Authorization Standards

This section describes how this specification relates to other authorization standards.

#### NMOP Policy Sharing Model

Separation of responsibilities between policy store governance and distribution may follow the recommendations in Section 6.2 of the [NMOP policy sharing model](https://datatracker.ietf.org/doc/draft-cabanillas-nmop-authz-policy-sharing-model/).

#### GovOps TRACE profile

This subsection is informative. The [GovOps TRACE profile](../govops-trace-profile.md) (`tag:govops.owasp.org,2026:trace-v1`) defines signed `AUTHORIZATION_DECISION` records. A PDP that emits them maps policy store values into the record's `trace.policy` object:

| `trace.policy` member | Policy store value |
| :--- | :--- |
| `policy_store_id` | `policy_store.id` of the active snapshot |
| `policy_store_version` | `policy_store.version` of the active snapshot |
| `policy_store_release_id` | `policy_store.release_id` of the active snapshot |
| `bundle_hash` | `package_digest` of the active snapshot |
| `policy_language` | `policy_language` |
| `policy_language_version` | `policy_language_version` |

### Security Considerations

#### Policy store

Policy stores contain authorization rules and may include sensitive configuration. Implementations MUST protect policy stores at rest and in transit using appropriate access controls for the deployment environment.

Deployments SHOULD use signed releases or secure artifact repositories where provenance is required.

[Package Integrity](#package-integrity) defines content verification for every policy store. The [Provenance Profile](#provenance-profile) adds signer authorization for deployments that require it. [Safe Package Paths](#safe-package-paths) applies to every policy store. HTTPS and artifact hashes alone do not establish that a producer is authorized to change the active policy store.

The `policy_store.version` label is not anti-rollback protection or exact content identity. Audit correctness depends on binding each decision to the [`package_digest`](#package-digest) of the active snapshot and rejecting reuse of a release tuple with conflicting content ([Loading, activation, and rollback](#loading-activation-and-rollback)). Deployments SHOULD retain acceptance, activation, and decision records so that a decision can be traced to the exact policy content that produced it.

Trusted issuer configuration determines which token issuers a PDP accepts. Incorrect issuer configuration can allow unauthorized principals. Implementations MUST validate `configuration_endpoints` URIs and token metadata before trusting tokens in production.

Policy stores SHOULD be treated as part of the trusted computing base for authorization decisions. Loading a policy store from an untrusted source without validation is NOT RECOMMENDED.

#### Policy store delivery

A PDP SHOULD protect any mechanism that delivers a policy store to it by taking appropriate measures to authenticate and authorize the request. Accepting a package MUST NOT grant its producer permission to activate it ([Loading, activation, and rollback](#loading-activation-and-rollback)).

#### Custom tokens

Custom type tokens ([Custom token type](#custom-token-type)) move credential validation out into a deployment-supplied token processor. The token processor is part of the trusted computing base for authorization decisions.

Because a custom type token need not have a configuration document, there is no standard mechanism for key rotation, token status, or revocation. Deployments that accept custom type tokens MUST provide these controls through the token processor or surrounding infrastructure.

All declared token types are optional, so a PDP may reach a decision with fewer tokens than a deployment anticipated. Deployments SHOULD review policies that reference custom token entity types to confirm that a decision remains correct when tokens of those types are absent.

## Policy store examples

The following example illustrates a Cedar policy store. It is not normative.

### Example: Cedar policy store

A Cedar-based PDP ([Cedar](https://docs.cedarpolicy.com/)) might use `policy_language` value `"cedar"`, place a Cedar schema file under `schema/`, and use `.cedar` policy files:

```text
todo-app-policy-store/
├── metadata.json
├── integrity.json
├── schema/
│   └── app.cedarschema
├── policies/
│   ├── alice-read-access.cedar
│   └── jack-search-access.cedar
├── entities/
│   └── default-roles.json
└── trusted-issuers.json
```

**metadata.json:**

```json
{
  "policy_store_spec_version": "1.0",
  "policy_language": "cedar",
  "policy_language_version": "4.4.0",
  "policy_store": {
    "id": "https://example.com/apps/todo/policystore/",
    "name": "todo_app_policy_store",
    "version": "1.0.0",
    "release_id": "2025-01-10-main-9f8e7d"
  },
  "governance": {
    "owner": "urn:acme:team:policy-owners",
    "author": "urn:acme:team:policy-authors",
    "policy_domain": "urn:example:application:todo"
  }
}
```

**policies/alice-read-access.cedar:**

```cedar
@id("alice-read-policy")
permit(
  principal == App::User::"Alice",
  action == App::Action::"Read",
  resource == App::Application::"todo"
);
```

The same store can be distributed as `todo-app-policy-store-1.0.0-2025-01-10-main-9f8e7d.cjar`.

## Drawbacks

### Increased Complexity for Simple Use Cases

The folder structure approach may be overkill for simple applications with just a few policies. The overhead of managing multiple files and directories could be burdensome for basic use cases.

### Tooling Requirements

Applications will need to implement logic to:

- Parse and validate the directory structure
- Handle both directory and archive formats
- Manage file-to-policy mappings
- Validate cross-references between files

### Migration Complexity

Existing applications using ad-hoc policy storage methods will need to:

- Restructure their existing policy organization
- Update deployment pipelines to handle the new format
- Modify policy loading and validation logic

### Integrity and Provenance Complexity

Every policy store MUST contain `integrity.json`. Tools that produce policy stores must generate the inventory and update it when any artifact changes. Deployments that require the Provenance Profile must also manage signing keys, approval policy, and trust anchors outside the policy store.

### Potential for Inconsistency

With policies spread across multiple files, there's an increased risk of:

- Inconsistent naming conventions across teams
- Missing files during deployment
- Broken references between policies and entities

However, these drawbacks are mitigated by:

- **Voluntary adoption**: Applications can choose whether to adopt this specification
- **Gradual migration**: Apps can incrementally adopt the specification
- **Tooling support**: Standard tooling can help validate and manage policy stores
- **Flexibility**: Both directory and archive formats provide options for different use cases

## Alternatives

### Single JSON File Format (Original Proposal)

The original design proposed a single JSON file containing all policies, schemas, and metadata as base64-encoded content. While this approach provides a single deployable unit, it has several limitations:

- **Poor developer experience**: Policies embedded as base64 strings are not human-readable or editable
- **Version control issues**: Changes to individual policies result in large, opaque diffs
- **Limited tooling support**: Standard development tools cannot provide syntax highlighting or validation for embedded policies
- **Merge conflicts**: Multiple developers working on policies in the same JSON file will frequently encounter conflicts

### Hybrid Approach

A hybrid approach could support both formats:

- Use the directory structure during development
- Convert to JSON format for specific deployment scenarios that require a single file
- Provide tooling to convert between formats

This approach provides flexibility but increases implementation complexity.

### Database-Backed Storage

Instead of file-based storage, policies could be stored in a database with a standardized schema. This approach offers:

- **Advantages**: Better querying capabilities, atomic transactions, built-in versioning
- **Disadvantages**: Requires database infrastructure, less portable, harder to version control

### Git-Based Policy Repositories

Policies could be stored directly in Git repositories with minimal additional structure:

- **Advantages**: Leverages existing Git workflows, excellent version control
- **Disadvantages**: Requires Git infrastructure, less standardized, harder to package for deployment

### Do Nothing and Wait

Another alternative is to not create any standardized policy store specification at this time and wait for the Cedar ecosystem to mature further:

- **Advantages**:
  - No immediate implementation burden on the Cedar team
  - Allows more time to observe real-world usage patterns and pain points
  - Avoids potential premature standardization that might not fit all use cases
  - Lets the community experiment with different approaches organically

- **Disadvantages**:
  - Delays the benefits of standardization for tooling and interoperability
  - May result in more entrenched ad-hoc solutions that are harder to migrate later
  - Misses the opportunity to guide the ecosystem toward best practices early

While waiting has some merit, the current pain points around policy organization, version control, and tooling integration suggest that standardization would provide immediate value to the Cedar community.

The proposed folder/archive approach strikes a balance between developer experience, portability, and standardization.

## Unresolved questions

The following topics may be addressed in future revisions:

- Whether policy and template identifiers must be unique across policy stores, and which source provides a policy's identifier.
- How policy templates are instantiated and linked to policies in multi-file layouts.
- Support in the discovery form for multi-tenant IdPs whose discovered issuer differs from the discovery URL prefix (for example, Entra ID common); such issuers currently must use the static form.
- Whether a policy store may contain files or directories other than those defined in this specification (for example, a README at the policy store root), and how loaders treat them.
- The relationship between critical artifact descriptors in `integrity.json` and future layout extensions.
- Whether `governance.jurisdictions` can express law that is not national. ISO 3166-1 alpha-2 covers countries only. It cannot name EU-wide law such as GDPR (`eu` is an exceptionally reserved code, not an assigned country code) or subnational law such as US state statutes. Options include ISO 3166-2 subdivision codes or a registry of additional values. The ACC `x-jurisdictions` extension has the same limit, so the two formats should resolve it together.
- Whether a policy store should be able to identify the legal instrument behind a listed jurisdiction, for example with a dated identifier that pins one version of a statute, and whether that belongs in the policy store or only in the control mapping.
- Byte-level positive and negative test fixtures for the Provenance Profile, and results from independent implementations.

## Reference

### JSON Schemas (Informative)

The following JSON Schemas illustrate the structure of normative JSON artifacts. They are informative; in case of conflict, the prose requirements in this document take precedence.

#### metadata.json Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "policy_store_spec_version",
    "policy_language",
    "policy_language_version",
    "policy_store",
    "governance"
  ],
  "properties": {
    "policy_store_spec_version": { "type": "string", "minLength": 1 },
    "policy_language": { "type": "string", "minLength": 1 },
    "policy_language_version": { "type": "string", "minLength": 1 },
    "policy_store": {
      "type": "object",
      "required": ["id", "name", "version", "release_id"],
      "properties": {
        "id": { "type": "string", "format": "uri"},
        "name": { "type": "string" },
        "description": { "type": "string" },
        "version": { "type": "string", "minLength": 1 },
        "release_id": { "type": "string", "minLength": 1 },
        "created_date": { "type": "string", "format": "date-time" }
      },
      "additionalProperties": false
    },
    "governance": {
      "type": "object",
      "required": ["owner", "author", "policy_domain"],
      "properties": {
        "owner": { "type": "string", "format": "uri", "pattern": "^urn:" },
        "author": { "type": "string", "format": "uri", "pattern": "^urn:" },
        "policy_domain": { "type": "string", "format": "uri", "pattern": "^urn:" },
        "jurisdictions": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": { "type": "string", "pattern": "^[a-z]{2}$" }
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

#### Trusted Issuer Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Policy store trusted-issuers.json",
  "description": "Map of Cedar entity type name to token type entry. Duplicate keys cannot be expressed in JSON Schema and are checked at load.",
  "type": "object",
  "propertyNames": { "$ref": "#/$defs/entityTypeName" },
  "additionalProperties": { "$ref": "#/$defs/entry" },
  "$defs": {
    "identifier": {
      "description": "Single Cedar identifier.",
      "type": "string",
      "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"
    },
    "entityTypeName": {
      "description": "Cedar entity type name defined in the policy store's schema.",
      "type": "string",
      "pattern": "^[A-Za-z_][A-Za-z0-9_]*(::[A-Za-z_][A-Za-z0-9_]*)*$"
    },
    "issuer": {
      "$ref": "#/$defs/identifier",
      "description": "Identifier for the issuer."
    },
    "requiredClaims": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 },
      "uniqueItems": true,
      "default": []
    },
    "entry": {
      "type": "object",
      "required": ["typ"],
      "properties": {
        "typ": {
          "description": "case-insensitive token format.",
          "type": "string",
          "pattern": "^([Jj][Ww][Tt]|[Cc][Uu][Ss][Tt][Oo][Mm])$"
        }
      },
      "oneOf": [
        { "$ref": "#/$defs/jwtEntry" },
        { "$ref": "#/$defs/customEntry" }
      ]
    },
    "jwtEntry": {
      "type": "object",
      "required": ["typ", "issuer", "configuration_endpoints"],
      "properties": {
        "typ": { "type": "string", "pattern": "^[Jj][Ww][Tt]$" },
        "issuer": { "$ref": "#/$defs/issuer" },
        "configuration_endpoints": { "$ref": "#/$defs/keySource" },
        "token_id": {
          "description": "Claim used as the token id.",
          "type": "string",
          "minLength": 1,
          "default": "jti"
        },
        "required_claims": {
          "$ref": "#/$defs/requiredClaims",
          "description": "Presence + RFC 7519 value validation."
        }
      }
    },
    "customEntry": {
      "type": "object",
      "required": ["typ", "issuer", "token_id"],
      "properties": {
        "typ": { "type": "string", "pattern": "^[Cc][Uu][Ss][Tt][Oo][Mm]$" },
        "issuer": { "$ref": "#/$defs/issuer" },
        "token_id": {
          "description": "Claim in the processor output used as the token id.",
          "type": "string",
          "minLength": 1
        },
        "configuration_endpoints": { "$ref": "#/$defs/keySource" },
        "required_claims": {
          "$ref": "#/$defs/requiredClaims",
          "description": "Presence in processor output."
        }
      }
    },
    "keySource": {
      "description": "Exactly one form.",
      "oneOf": [
        {
          "title": "Discovery",
          "description": "Expected `iss` = this URL minus `/.well-known/openid-configuration`; keys from discovered `jwks_uri`.",
          "type": "object",
          "required": ["openid_configuration"],
          "properties": {
            "openid_configuration": {
              "type": "string",
              "format": "uri",
              "pattern": "^https://[^?#]+/\\.well-known/openid-configuration$"
            }
          },
          "additionalProperties": false
        },
        {
          "title": "Static",
          "description": "No discovery; keys from `jwks`, expected `iss` given explicitly.",
          "type": "object",
          "required": ["jwks", "iss"],
          "properties": {
            "jwks": { "type": "string", "format": "uri", "pattern": "^https://[^?#]+" },
            "iss": { "type": "string", "format": "uri", "pattern": "^https://[^?#]+$" }
          },
          "additionalProperties": false
        }
      ]
    }
  }
}
```

#### Entity File Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "oneOf": [
    { "type": "array", "items": { "$ref": "#/$defs/entity" } },
    { "$ref": "#/$defs/entity" }
  ],
  "$defs": {
    "entity": {
      "type": "object",
      "required": ["uid", "attrs"],
      "properties": {
        "uid": {
          "type": "object",
          "required": ["type", "id"],
          "properties": {
            "type": { "type": "string", "minLength": 1 },
            "id": { "type": "string" }
          },
          "additionalProperties": false
        },
        "attrs": { "type": "object", "additionalProperties": true },
        "parents": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["type", "id"],
            "properties": {
              "type": { "type": "string", "minLength": 1 },
              "id": { "type": "string" }
            },
            "additionalProperties": false
          }
        },
        "tags": { "type": "object" }
      },
      "additionalProperties": false
    }
  }
}
```

## Appendix A: Other Policy Languages (Informative)

This appendix is informative. It adds no requirements to this specification.

The policy store format does not depend on Cedar. The same layout, metadata, integrity inventory, provenance signatures, and archive format can carry policies written in another policy language, such as CEL. A policy store is specific to the policy language it contains, but it remains independent of the PDP or policy engine that evaluates that language.

### Metadata values

`policy_language` names the policy language of the store, for example `"cel"`. Identifiers are lowercase alphanumeric strings, with hyphens separating words. `policy_language_version` holds the version of that language.

### Files

- Policy and template files use the extensions conventional for the declared policy language.
- The declared policy language defines the file names and layout within `schema/`.
- Policy identifiers follow the rules of the declared policy language. For example, Cerbos PDPs identify policies by resource kind, name, and version fields within YAML or JSON policy documents.

### Entities and trusted issuers

The entity file format serves as an interchange format. A PDP maps entity definitions to the representation that its policy engine uses. Keys in `trusted-issuers.json` refer to types in the store's schema, for example a Cerbos principal schema reference.

### Loading

A PDP rejects a policy store whose `policy_language` or `policy_language_version` it does not support, as described in step 8 of [Policy Store Loading](#policy-store-loading).

### Example: CEL policy store

A CEL-based Cerbos PDP ([Cerbos](https://docs.cerbos.dev/)) can consume a policy store that has `policy_language` value `"cel"`, store JSON schemas under `schema/`, and use YAML policy files under `policies/`:

```text
hr-policy-store/
├── metadata.json
├── integrity.json
├── schema/
│   └── principal.json
├── policies/
│   └── resource_policies/
│       └── leave_request.yaml
└── trusted-issuers.json
```

**metadata.json:**

```json
{
  "policy_store_spec_version": "1.0",
  "policy_language": "cel",
  "policy_language_version": "0.25.0",
  "policy_store": {
    "id": "https://example.com/hr/policystore/",
    "name": "hr_policy_store",
    "version": "2.0.0",
    "release_id": "2025-02-02-release-4c5d6e"
  },
  "governance": {
    "owner": "urn:acme:team:policy-owners",
    "author": "urn:acme:team:policy-authors",
    "policy_domain": "urn:example:application:hr"
  }
}
```

**policies/resource_policies/leave_request.yaml (excerpt):**

```yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: default
  resource: leave_request
  rules:
    - actions: ["view:*"]
      effect: EFFECT_ALLOW
      roles: ["employee"]
```

Cerbos deployments that use a native repository layout (for example, a top-level `_schemas` directory) can translate to or from this layout when importing or exporting a `.cjar` package.

### Open questions

- A registry of recognized `policy_language` identifier strings.
- Subdirectory organization conventions under `policies/` per policy language.
- Whether the fixed entity representation is neutral across all policy languages.
