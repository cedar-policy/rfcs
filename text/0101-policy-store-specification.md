# Proposal for Policy Store Specification

#### Authors

* Dhaval Desai (@ossdhaval)
* Michael Schwartz (@nynymike)

#### Contributors

* Victor Moreno (@Swolebrain)

## Related issues and PRs

- Reference Issues: None
- Implementation PR(s): (leave this empty)

## Timeline

- Started: TBD
- Accepted: TBD
- Stabilized: TBD

## Summary

Create a specification that recommends a structured directory format to store Cedar policies, schemas, default entities, and other relevant information. The specification supports both a developer-friendly directory structure for development and editing, and a compressed archive format for distribution and deployment. Each policy and template is stored as an individual human-readable file, enabling better version control, IDE support, and collaborative development workflows.

## Motivation

The proposal in this RFC targets the following constraint:

### Lack of a recommended method to co-locate and bind policies, schema, and other information

Cedar does not prescribe any method or system that co-locates and binds together the information about the schema and the policies that use that schema. This approach gives flexibility to combine any schema with any policy at evaluation time. But in practice, more often than not, the policies are targeted to a specific schema, which they use every time. 

The following drawbacks stem from not having a prescribed method of co-location and binding the policy, schema, and other information:
 
* **Versioning**: In the audit logs to create a cryptographic chain of custody, it's critical to know the exact version of the policies and the schema used at evaluation time. For example, when using schema-based entity parsing. Formally binding the policies and schema makes the audit logs more clear.
* **Productivity**: Developers will have to separately map all the assets individually. Federated identity protocols like SAML and OpenID typically bundle entity metadata, which simplifies both development and operations
* **Risk**: The lack of a formal binding increases the risk of error, e.g., using the wrong schema or schema version

This lack of a prescribed method creates even more pain for large organizations, as they have to deal with a multitude of policies and corresponding schemas. To maintain order, organizations will establish their own conventions and structures for storage policies and schemas. Invariably, this will result in inconsistent storage structures across different organizations or within different teams in the same organization.

Such inconsistency in methods used by organizations will create the following systemic issues in the Cedar ecosystem:

- Reduces PDP interoperability, for example makes it harder to move a policy store from Janssen Project Cedarling to Amazon Verified Permissions and vice versa. 
- Impedes the development and deployment of third-party tools that need to access policies and schema. For instance, third-party policy analysis tools, visualization tools, or workflow integration tools like n8n. A uniform method of storing information across teams and organizations will reduce the configuration and customization burden on third-party tools.  
- Reduces portability, for instance, a merger between two companies that use different storage methods. Tools and apps written by one organization will not be able to be deployed without the additional effort to unify policy and schema storage methods. Also makes it difficult for policy administrators who work with different teams of the same organisation if the teams have their policies and schema stored differently. 

### Proposed solution

This RFC proposes to create a new "policy store" specification. The specification will recommend a structured format that contains all information required to evaluate an authz request.

The policy store can be distributed in two formats:

1. **Directory Structure Format**: A folder-based approach where each component (policies, templates, schema, entities) is stored as individual files within a structured directory hierarchy
2. **Archive Format**: A compressed archive (zip file) with the file extension `.cjar`, containing the same directory structure for easy distribution and deployment

See the sample directory structure below:

```
policy-store/
├── metadata.json                    # Policy store metadata
├── manifest.json                    # Inventory of files
├── schema.cedarschema               # Cedar schema file
├── policies/                        # Individual policy files
│   ├── policy-001.cedar
│   ├── policy-002.cedar
│   └── ...
├── templates/                       # Policy template files
│   ├── template-001.cedar
│   └── ...
├── entities/                        # Default entity files
│   ├── organizations.json
│   ├── roles.json
│   └── ... 
└── trusted-issuers/                 # Trusted issuer configurations
    ├── issuer-001.json
    └── ...
```

For distribution, this directory structure can be packaged as a zip file with the `.cjar` file extension, providing a single deployable unit while maintaining the benefits of individual file organization.

## Benefits

### Developer-Friendly Organization
The folder-based structure provides several advantages for developers:
* **Individual file editing**: Each policy and template can be edited as a separate file, enabling better IDE support, syntax highlighting, and version control
* **Granular version control**: Git and other VCS systems can track changes to individual policies, providing clearer diff views and blame information
* **Modular development**: Teams can work on different policies simultaneously without merge conflicts
* **Easier debugging**: Issues can be traced to specific policy files rather than searching through large JSON blobs

### Flexible Distribution Options
* **Development format**: Use the directory structure during development for maximum flexibility
* **Deployment format**: Package as a `.cjar` zip file for atomic deployment and distribution
* **Hybrid approach**: Tools can work with either format, converting between them as needed

### Strong versioning

* For forensic analysis of an audit log, you must know the exact version of the policies and schema in use at the time of the decision. 
* Versioning provides an opportunity for review and governance. For example, the CISO may want to review the policies of a certain application and then review all subsequent changes. Versioning aligns with existing change management and CI/CD pipelines.
* Strong versioning aligns with cloud native declarative syntax goals, making the deployment of new code and rollback to old code easier.
* **File-level versioning**: Individual policies can be versioned independently, allowing for more granular change tracking

### Create a self-contained unit

The policy store standardizes the structure and metadata format. This helps with deployment, keeping several elements that should not be separated bundled together as one unit, whether as a directory structure or compressed archive.

### Policy grouping and separation of concern

Organizations may create a policy store to group shared policies. This could perhaps help organizations maintain a master set of policies for certain types of applications, for example, a policy store that applies to all Internet-facing web applications. The file-based structure makes it easier to organize policies by domain, team, or functionality.

### Interoperable tools and knowledge

A robust Cedar third party developer ecosystem will help drive broader adoption of Cedar. A standard policy store format will promote interoperability of third-party tools. The file-based approach is more accessible to standard development tools and workflows. 

## Detailed design

The policy store specification defines both a directory structure format and an archive format. The content structure is detailed in three sections below:

* [Directory Structure](#directory-structure) section describes the folder organization and file naming conventions
* [Metadata Format](#metadata-format) section describes the metadata.json file structure
* [Archive Format](#archive-format) section describes how the directory structure is packaged for distribution
* [Examples](#policy-store-examples) section provides concrete examples of policy stores in both formats

### Directory Structure

The policy store follows a standardized directory structure:

```
policy-store-root/
├── metadata.json                    # Required: Policy store metadata
├── manifest.json                    # Inventory of folder
├── schema.cedarschema               # Required: Cedar schema file
├── policies/                        # Required: Directory containing policy files
│   ├── *.cedar                      # Individual policy files
├── templates/                       # Optional: Directory containing template files  
│   ├── *.cedar                      # Individual template files
├── entities/                        # Optional: Directory containing default entities
│   ├── *.json                       # Entity definition files
└── trusted-issuers/                 # Optional: Directory containing issuer configs
    ├── *.json                       # Individual issuer configuration files
```

#### File Naming Conventions

- **Policy files**: Must have `.cedar` extension and contain a single Cedar policy
- **Template files**: Must have `.cedar` extension and contain a single Cedar template
- **Entity files**: Must have `.json` extension and contain entity definitions in Cedar JSON format
- **Issuer files**: Must have `.json` extension and contain trusted issuer configurations
- **Schema file**: Must be named `schema.cedarschema` and contain the Cedar schema
- **Metadata file**: Must be named `metadata.json` and contain policy store metadata
- **Manifest file**: Must be named `manifest.json` and contain data about files in the policy store
- **Archive file**: Must have `.cjar` suffix

#### File Content Requirements

- **Policy files**: Each file must contain exactly one Cedar policy with an `@id()` annotation
- **Template files**: Each file must contain exactly one Cedar template with an `@id()` annotation  
- **Entity files**: Each file contains a JSON array of entity definitions or a single entity definition
- **Schema file**: Contains the Cedar schema in `.cedarschema` format
- **Metadata file**: Contains policy store metadata in JSON format (see Metadata Format section)
- **Manifest file**: Contains an inventory of all files in the policy store for validation and integrity checking 

### Metadata Format

The `metadata.json` file contains policy store metadata and configuration:

```json
{
  "cedar_version": "4.4.0",
  "policy_store": {
    "id": "9e96b204911d1c3",
    "name": "Acme Analytics Web Application", 
    "description": "Acme's premier tool for counting narwhals, doves and gorns.",
    "version": "1.2.0",
    "created_date": "2025-01-15T10:30:00Z",
    "updated_date": "2025-01-18T14:22:00Z"
  }
}
```

#### Metadata Fields

- `cedar_version`: The version of the Cedar policy language used in this policy store
- `policy_store`: Policy store configuration object
  - `id`: Unique identifier for the policy store (hex hash)
  - `name`: Human-readable name for the policy store
  - `description`: Optional description of the policy store
  - `version`: Semantic version of the policy store content
  - `created_date`: ISO 8601 timestamp when the policy store was created
  - `updated_date`: ISO 8601 timestamp when the policy store was last modified

#### Trusted Issuers

Trusted issuer configurations are stored as individual JSON files in the `trusted-issuers/` directory. Each file contains information about a domain that mints JWT tokens. Specifying trusted issuers enables Cedar-based PDPs to establish the sources of truth who can supply evidence to satisfy policies.

Sample trusted issuer file (`trusted-issuers/acme-idp.json`):

```json
{
  "id": "3af079fa58a915a4d37a668fb874b7a25b70a37c03cf",
  "name": "Acme Dolphins Division",
  "description": "Global cetacian aquariums",
  "configuration_endpoint": "https://acme-dolphin.sea/.well-known/openid-configuration",
  "token_metadata": {
    "access_token": {
      "trusted": true,
      "entity_type_name": "Jans::Access_token",
      "required_claims": ["jti", "iss", "aud", "sub", "exp", "nbf"]
    }
  }
}
```

##### Trusted Issuer Field Definitions

**Top-level fields:**
- `id`: Unique identifier for the trusted issuer (hex hash). Used internally by the PDP to reference this issuer configuration.
- `name`: Short, human-readable name for the trusted issuer. Used for display and logging purposes.
- `description`: Detailed description of the issuer, such as the organization name or identity provider type.
- `configuration_endpoint`: Endpoint URL where the issuer publishes its configuration, including the location of the JWKS endpoints for token verification.

**Token metadata fields:**
The `token_metadata` object contains configuration for different token types that this issuer can mint. Each token type is identified by a domain-chosen name (such as "access_token", "id_token", "refresh_token", etc.) which serves as a semantic short name that PDPs can use to reference this specific token type. The token type name becomes a key in the `token_metadata` object, and its value contains the configuration for that token type.

For each token type, the following configuration fields are available:

- `entity_type_name`: REQUIRED - The Cedar entity type name that represents this token type in Cedar policies. This is required for mapping tokens to policies.
- `trusted`: OPTIONAL - Boolean flag indicating whether tokens of this type from this issuer should be trusted by the PDP. When `false`, tokens are rejected during validation.
- `required_claims`: OPTIONAL - Array of JWT claim names that must be present in tokens of this type for them to be considered valid. Missing required claims will cause token validation to fail.

##### Extensibility

The trusted issuer configuration is extensible beyond the fields shown in the sample. PDPs may define additional fields as long as the PDP implementation understands how to interpret them. Extensions may include:

- **Custom token validation rules**: Additional validation logic specific to the issuer
- **Claim mapping configurations**: Mapping JWT claims to Cedar entity attributes for normalization
- **Role and permission mappings**: How to extract user roles from token claims
- **Principal mapping**: Which Cedar entity types this token can represent as a principal
- **Issuer-specific metadata**: Custom fields needed for integration with proprietary identity systems

This extensibility allows the specification to support diverse identity provider ecosystems while maintaining a common foundation for interoperability.

#### Default Entities

Default entities are stored as individual JSON files in the `entities/` directory. These files capture static resource entities, such as organization information, user groups, or action groups that don't frequently change and can be pre-loaded into the policy evaluation context.

Each entity file contains a JSON array of entity definitions that follow the Cedar JSON entity format as specified in the [Cedar JSON Schema documentation](https://docs.cedarpolicy.com/schema/json-schema.html). Each entity definition must contain the following required fields:
- `uid`: An object with `type` and `id` fields that uniquely identifies the entity
- `attrs`: An object containing the entity's attributes and their values
- `parents`: (Optional) An array of parent entity references for hierarchical relationships
- `tags`: (Optional) An object containing key-value pairs for entity metadata and classification

Sample entity file (`entities/organizations.json`):

```json
[
  {
    "uid": {
      "type": "Organization",
      "id": "acme-dolphins"
    },
    "attrs": {
      "name": "Acme Dolphins Division",
      "org_id": "100129", 
      "domain": "acme-dolphin.sea",
      "regions": ["Atlantic", "Pacific", "Indian"]
    }
  }
]
```

Sample entity file for action groups (`entities/action-groups.json`):

```json
[
  {
    "uid": {
      "type": "Acme::ActionGroups",
      "id": "Write"
    },
    "attrs": {
      "name": "Write Operations",
      "description": "Actions that modify data"
    },
    "parents": [
      {
        "type": "Acme::Action", 
        "id": "add"
      },
      {
        "type": "Acme::Action",
        "id": "modify" 
      },
      {
        "type": "Acme::Action",
        "id": "delete"
      }
    ],
    "tags": {
      "category": "data-modification",
      "risk_level": "medium",
      "audit_required": "true"
    }
  }
]
```



### Archive Format

For distribution and deployment, the policy store directory structure can be packaged as a zip archive with the file extension `.cjar`. The archive format provides:

- **Atomic deployment**: Single file contains all policy store components
- **Version control friendly**: Can be stored and versioned as a single artifact
- **Easy distribution**: Simple to share, upload, or deploy policy stores
- **Integrity**: Archive checksums help ensure policy store integrity

#### Archive Structure

The `.cjar` zip archive contains the exact same directory structure as the folder format:

```
policy-store.cjar
├── metadata.json
├── manifest.json
├── schema.cedarschema  
├── policies/
│   ├── user-access.cedar
│   ├── admin-permissions.cedar
│   └── ...
├── templates/
│   ├── resource-template.cedar
│   └── ...
├── entities/
│   ├── organizations.json
│   └── ...
└── trusted-issuers/
    ├── jans-idp.json
    └── ...
```

#### Archive Naming Convention

Policy store archives should follow the naming pattern:
`{policy-store-name}-{version}.cjar`

Examples:
- `acme-analytics-v1.2.0.cjar`
- `user-management-v2.1.3.cjar`

### JSON Schema for Metadata

[JSON Schema](https://json-schema.org/) for the metadata.json file:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "description": "Policy store metadata configuration",
  "required": ["cedar_version", "policy_store"],
  "properties": {
    "cedar_version": {
      "type": "string",
      "description": "The version of the Cedar policy language used in this policy store"
    },
    "policy_store": {
      "type": "object",
      "description": "Policy store configuration",
      "required": ["id", "name"],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^[a-fA-F0-9]{15,64}$",
          "description": "Unique identifier for the policy store (hex hash)"
        },
        "name": {
          "type": "string",
          "description": "Human-readable name for the policy store"
        },
        "description": {
          "type": "string",
          "description": "Optional description of the policy store"
        },
        "version": {
          "type": "string",
          "description": "Semantic version of the policy store content"
        },
        "created_date": {
          "type": "string",
          "format": "date-time",
          "description": "ISO 8601 timestamp when created"
        },
        "updated_date": {
          "type": "string", 
          "format": "date-time",
          "description": "ISO 8601 timestamp when last modified"
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

### JSON Schema for Trusted Issuers

[JSON Schema](https://json-schema.org/) for trusted issuer configuration files:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "description": "Trusted issuer configuration",
  "required": ["id", "name", "configuration_endpoint"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[a-fA-F0-9]{15,64}$",
      "description": "Unique identifier for the trusted issuer (hex hash)"
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "description": "Short, human-readable name for the trusted issuer"
    },
    "description": {
      "type": "string",
      "description": "Detailed description of the issuer"
    },
    "configuration_endpoint": {
      "type": "string",
      "format": "uri",
      "description": "Endpoint URL where the issuer publishes its configuration"
    },
    "token_metadata": {
      "type": "object",
      "description": "Configuration for different token types that this issuer can mint",
      "patternProperties": {
        "^[a-zA-Z_][a-zA-Z0-9_]*$": {
          "type": "object",
          "description": "Token type configuration",
          "properties": {
            "trusted": {
              "type": "boolean",
              "description": "Whether tokens of this type from this issuer should be trusted by the PDP",
              "default": true
            },
            "entity_type_name": {
              "type": "string",
              "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*::[a-zA-Z_][a-zA-Z0-9_]*$",
              "description": "The Cedar entity type name that represents this token type in Cedar policies"
            },
            "required_claims": {
              "type": "array",
              "items": {
                "type": "string",
                "minLength": 1
              },
              "uniqueItems": true,
              "description": "Array of JWT claim names that must be present in tokens of this type"
            },

          },
          "additionalProperties": true
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": true
}
```

**Note on Extension Fields**: The JSON schema above defines the core specification fields. PDPs may extend token type configurations with additional fields such as `user_id`, `token_id`, `workload_id`, `role_mapping`, `claim_mapping`, and `principal_mapping`. These extension fields should be documented by the specific PDP implementation.

### JSON Schema for Entity Files

[JSON Schema](https://json-schema.org/) for entity definition files:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "array",
  "description": "Array of Cedar entity definitions",
  "items": {
    "type": "object",
    "description": "Cedar entity definition",
    "required": ["uid", "attrs"],
    "properties": {
      "uid": {
        "type": "object",
        "description": "Entity unique identifier",
        "required": ["type", "id"],
        "properties": {
          "type": {
            "type": "string",
            "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*(::[a-zA-Z_][a-zA-Z0-9_]*)*$",
            "description": "Entity type name"
          },
          "id": {
            "type": "string",
            "description": "Entity identifier"
          }
        },
        "additionalProperties": false
      },
      "attrs": {
        "type": "object",
        "description": "Entity attributes",
        "additionalProperties": true
      },
      "parents": {
        "type": "array",
        "description": "Parent entity references for hierarchical relationships",
        "items": {
          "type": "object",
          "required": ["type", "id"],
          "properties": {
            "type": {
              "type": "string",
              "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*(::[a-zA-Z_][a-zA-Z0-9_]*)*$",
              "description": "Parent entity type name"
            },
            "id": {
              "type": "string",
              "description": "Parent entity identifier"
            }
          },
          "additionalProperties": false
        }
      },
      "tags": {
        "type": "object",
        "description": "Entity metadata and classification tags",
        "additionalProperties": {
          "type": "string"
        }
      }
    },
    "additionalProperties": false
  }
}
```

### Manifest File Format

The `manifest.json` file provides an inventory of all files in the policy store for validation and integrity checking:

```json
{
  "policy_store_id": "9496b204911615307f6338de8a18c6885f2370793c31",
  "generated_date": "2025-01-18T14:22:00Z",
  "files": {
    "metadata.json": {
      "size": 245,
      "checksum": "sha256:a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
    },
    "schema.cedarschema": {
      "size": 1024,
      "checksum": "sha256:b3a8e0e1f9ab1bfe3a36f231f676f78bb30a519d2b21e6c530c0b86a4c4700e2"
    },
    "policies/alice-read-access.cedar": {
      "size": 156,
      "checksum": "sha256:c2d4e6f2a1b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9"
    },
    "entities/default-roles.json": {
      "size": 234,
      "checksum": "sha256:d3e5f7a2b4c6d8e0f2a4b6c8d0e2f4a6b8c0d2e4f6a8b0c2d4e6f8a0b2c4d6e8"
    }
  }
}
```

## Policy store examples

### Example 1: Directory Structure Format

A complete policy store for a todo application:

```
todo-app-policy-store/
├── metadata.json
├── manifest.json
├── schema.cedarschema
├── policies/
│   ├── alice-read-access.cedar
│   └── jack-search-access.cedar
├── entities/
│   └── default-roles.json
└── trusted-issuers/
    ├── jans-idp.json
    └── acb-issuer.json
```

**metadata.json:**
```json
{
  "cedar_version": "4.4.0",
  "policy_store": {
    "id": "9496b204911615307f6338de8a18c6885f2370793c31",
    "name": "todo_app_policy_store",
    "description": "Policy store for the Todo application",
    "version": "1.0.0",
    "created_date": "2025-07-23T09:57:06.348765Z",
    "updated_date": "2025-07-23T09:59:55.341180Z"
  }
}
```

**policies/alice-read-access.cedar:**
```cedar
@id("alice-read-policy")
permit(
  principal == Jans::User::"Alice", 
  action == Jans::Action::"Read", 
  resource == Jans::Application::"todo"
);
```

**policies/jack-search-access.cedar:**
```cedar
@id("jack-search-policy")  
permit(
  principal == Jans::User::"Jack",
  action == Jans::Action::"Search", 
  resource == Jans::Role::"Searchable"
);
```

**schema.cedarschema:**
```
namespace Jans {
  entity User = {
    name: String,
    email: String
  };
  
  entity Application = {
    name: String,
    owner: User
  };
  
  entity Role = {
    name: String,
    permissions: Set<String>
  };
  
  action Read appliesTo {
    principal: User,
    resource: Application
  };
  
  action Search appliesTo {
    principal: User, 
    resource: Role
  };
}
```

**entities/default-roles.json:**
```json
[
  {
    "uid": {
      "type": "Jans::Role",
      "id": "Searchable"
    },
    "attrs": {
      "name": "Searchable",
      "permissions": ["search", "read"]
    }
  }
]
```

**trusted-issuers/jans-idp.json:**
```json
{
  "id": "3af079fa58a915a4d37a668fb874b7a25b70a37c03cf",
  "name": "jans",
  "description": "Jans IDP",
  "configuration_endpoint": "https://jans-host.com/.well-known/openid-configuration",
  "token_metadata": {
    "access_token": {
      "trusted": true,
      "entity_type_name": "Jans::Access_token",
      "required_claims": ["jti", "iss", "aud", "sub", "exp", "nbf"]
    },
    "id_token": {
      "trusted": true,
      "entity_type_name": "Jans::id_token", 
      "user_id": "sub",
      "role_mapping": "role",
      "principal_mapping": ["Jans::User"]
    }
  }
}
```

*Note: Fields such as `user_id`, `role_mapping`, and `principal_mapping` are extension fields and are not part of the core policy store specification. These are here for the purposes of illustration, e.g. how a PDP might use these fields.*

### Example 2: Archive Format

The same policy store packaged as a `.cjar` zip file:

**todo-app-policy-store-v1.0.0.cjar** contains the identical directory structure shown above.

Tools can extract the archive to work with individual files during development, then repackage for deployment.

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
  - Let the community experiment with different approaches organically
- **Disadvantages**: 
  - Delays the benefits of standardization for tooling and interoperability
  - May result in more entrenched ad-hoc solutions that are harder to migrate later
  - Misses the opportunity to guide the ecosystem toward best practices early

While waiting has some merit, the current pain points around policy organization, version control, and tooling integration suggest that standardization would provide immediate value to the Cedar community.

The proposed folder/archive approach strikes a balance between developer experience, portability, and standardization.

## Unresolved questions

### Policy ID Management
How should policy IDs be managed across the file-based format? Should they be:
- Derived from filenames?
- Required in `@id()` annotations?
- Managed in a separate index file?

### Template Instantiation
How should policy templates be instantiated and linked to their concrete policies in the file-based format?

### Cross-Policy Dependencies
How should dependencies between policies be expressed and validated in the distributed file format?

### Namespace Organization
Should policies be organized into subdirectories by namespace, or should namespace be purely a logical construct within individual policy files?
