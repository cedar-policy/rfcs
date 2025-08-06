# Proposal for Policy Store Specification

#### Authors

* Dhaval Desai (@ossdhaval)
* Michael Schwartz (@nynymike)

## Related issues and PRs

- Reference Issues: None
- Implementation PR(s): (leave this empty)

## Timeline

- Started: TBD
- Accepted: TBD
- Stabilized: TBD

## Summary

Create a specification that recommends a JSON descriptor file to store Cedar policies, schemas, default entities, and other relevant information.

## Motivation


_Why are we doing this? What use cases does it support? What is the expected outcome?_

_Please focus on explaining the motivation so that if this RFC is not accepted, the motivation could be used to develop alternative solutions. In other words, enumerate the constraints you are trying to solve without coupling them too closely to the solution you have in mind._

------

The proposal in this RFC targets the following constraint:

### Lack of a recommended method to co-locate and bind policies, schema, and other information

Cedar does not prescribe any method or system that co-locates and binds together the information about the schema, and the policies that use that schema. In Cedar, a policy's binding with its schema happens at the time of evaluation. This approach gives flexibility to combine any schema with any policy at evaluation time. But in practice, more often than not, the policies are targeted to a specific schema, which they use every time. 

In light of this fact, not having a prescribed method of co-location and binding the policy, schema and other information has the following drawbacks:
 
* Versioning: in the audit logs to create a cryptographic chain of custody, it's critical to know the exact version of the policies at evaluation time. Formally binding the policies and schema makes the audit logs more clear
* Productivity: Developers will have to separately map all the assets individually. Federated identity protocols like SAML and OpenID typically bundle entity metadata, which simplifies both development and operations
* Risk: The lack of a formal binding increases the risk of error, e.g., using the wrong schema or schema version

This lack of a prescribed method for co-locating and binding the policy, schema and other information together, creates more pain points for large organizations. Large organizations invariably see a multitude of policies and corresponding schemas. To maintain order, organizations will establish their own conventions and structures for storage policies and schemas. Invariably, this will result in inconsistent storage structures across different organizations or within different teams in the same organization.

Such inconsistency in methods used by organizations will create the following systemic issues in the Cedar ecosystem:

- Impedes the development and deployment of third-party tools that need to access policies and schema. For instance, third-party policy analysis tools, visualization tools, or workflow integration tools like n8n. A uniform method of storing information across teams and organizations will reduce the configuration and customization burden on third-party tools.  
- Adds overhead to achieve interoperability. For instance, a merger between two companies that use different storage methods. Tools and apps written by one organization will not be able to be deployed without the additional effort to unify policy and schema storage methods.
- Makes it difficult for policy administrators who work with different teams of the same organisation if the teams have their policies and schema stored differently. 

### Proposed solution

This RFC proposes to create a new "policy store" specification. The specification will recommend a file descriptor format that contains all information required to evaluate an authz request. 

Sample policy-store-descriptor.json structure--only an illustrative hypothetical sample--check below [design](detailed-design) for the details.

```
{
    "cedar_version": "4.4.0",
    "policy_stores": {
        "9e96b204911d1c3": {
            "name": "Acme Analytics Web Application",
            "description": "Acme's premier tool for counting narwhals, doves and gorns.",
            "policies": {"a270f688133cd00": "base64-content",...},
            "trusted_issuers": {...},
            "schema": "base64-content"
            "default_entities": {"1694c954f8d9": "base64-content",...}
        }
    }
}
```

## Benefits

### Easier for End Users
Having one one file versus three lowers the transaction costs for end-users of Cedar. As working with policies and schema is quite common, the cumulative productivity benefit of a small optimizations can add up! 

### Strong versioning

* For forensic analysis of an audit log, you must know the exact version of the policies and schema in use at the time of the decision. 
* Versioning provides an opportunity for review and governance. For example, the CISO may want to review the policies of a certain application and then review all subsequent changes. Versioning aligns with existing change management and CI/CD pipelines.
* Strong versioning aligns with cloud native declartive syntax goals, making the deployment of new code and rollback to old code easier.

### Create a self-contained unit

The policy store standardizes the JSON schema of the policy store metadata. This helps with deployment, keeping several elements that should not be separated bundled together as one unit. 

### Policy grouping and separation of concern

Organisations may create a policy store to group shared policies. This could perhaps help organizations maintain a master set of policies for certain types of applications, for example, a policy store that applies to all Internet-facing web applications. 

### Interoperable tools and knowledge

A robust Cedar third party developer ecosystem will help drive broader adoption of Cedar. A standard policy store format will promote interoperability of third-party tools. 

## Detailed design

* [Field descriptions](#field-descriptions) below define each field in the JSON structure. 
* The [JSON schema](#json-schema-for-the-policy-store) provides an accurate structure of the policy store. 
* Refer to the policy store [examples](#policy-store-examples) to help visualize the policy store in real-life usage.

### Field Descriptions

The structure below loosely follows policy store JSON structure, minus some structural elements removed for clarity.

- `cedar_version`: The version of the CEDAR policy language used to write policies in this policy store.
- `policy_stores`: A mapping of policy store identifiers (hex hashes) to their configurations. 
  - `<policy_store_id>`: A single policy store identified by its unique hash key.
    - `name`: A human-readable name for the policy store.
    - `description`: An optional description for the policy store.
    - `policies`: A mapping of policy IDs to their definitions. A policy store can have multiple policies.
      - `<policy_id>`: A single policy object identified by its unique ID.
        - `description`: Optional description of the policy.
        - `creation_date`: ISO 8601 formatted timestamp indicating when the policy was created.
        - `policy_content`: base64-encoded CEDAR policy content.
    - `trusted_issuers`: A mapping of trusted issuer IDs to their metadata.
      - `<issuer_id>`: unique hash to identify a trusted issuer
        - `name`: Name of the trusted issuer.
        - `description`: A human-readable description of the issuer
        - `openid_configuration_endpoint`: OpenID Connect discovery endpoint URL for this issuer.
        - More fields can be added to describe the trusted issuer and token metadata
    - `schema`: base64-encoded Cedar schema used by policies in this store. There can be only one schema per policy store.
    - `default_entities`: A mapping of entity IDs to base64-encoded JSON entity data. 

##### Trusted issuers

The `trusted_issuers` field is OPTIONAL. It contains information about a domain that mints JWT tokens. A store can have many trusted issuers, each who issue different kinds of tokens. Specifying the trusted issuers enables Cedar-based PDPs to establish the sources of truth who can supply evidence to satisfy policies. The signed tokens from trusted issuers are essential to establish a cryptographic chain of custody that compliments policy store versioning, proven delivery of the policy store, and secure deliver of decision logs. 

###### Claims to schema mapping

OPTIONAL. Different issuers may use different claims to convey the same information, e.g. `STATE` v. `ST`. The trusted issuer metadata helps Cedar users normalize such differences by defining how the JWT claims of issuers map to shared Cedar entity attributes, and how to parse strings sent as JWT token claims.

##### Default Entities

OPTIONAL. A JSON object that contains base64 encoded JSON entity data. 

The default entities JSON is used to capture static resource entities, for example organization information that doesn't frequently change. This enables reviews and a consistent change control process (like git) for resource information that is important for policy. 

- Reusability of entities. The default entities have unique identifiers that make the reuse of such entities easier across policies. 

Sample default entity JSON:

```
{
    "1694c954f8d9": {
        "entity_id": "1694c954f8d9",
        "o": "Acme Dolphins Division",
        "org_id": "100129",
        "domain": "acme-dolphin.sea",
        "regions": ["Atlantic", "Pacific", "Indian"]
    },
    "74d109b20248": {
        "entity_id": "74d109b20248",
        "description": "2025 Price List",
        "products": {"15020": 9.95, "15050": 14.95,}
        "services": {"51001": 99.00, "51020": 299.00,}
    }
}
```



### JSON Schema for the policy store

[JSON Schema](https://json-schema.org/) for policy store JSON.

```
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "description": "Top-level schema representing a CEDAR policy store configuration.",
  "required": ["cedar_version", "policy_stores"],
  "properties": {
    "cedar_version": {
      "type": "string",
      "description": "The version of the CEDAR policy language used to write policies in this policy store"
    },
    "policy_stores": {
      "type": "object",
      "description": "A mapping of policy store identifiers (hex hashes) to their configurations",
      "patternProperties": {
        "^[a-fA-F0-9]{40,64}$": {
          "type": "object",
          "description": "A single policy store identified by its unique hash key",
          "required": ["name", "policies", "trusted_issuers", "schema"],
          "properties": {
            "name": {
              "type": "string",
              "description": "A human-readable name for the policy store."
            },
            "description": {
              "type": "string",
              "description": "An optional description for the policy store."
            },
            "policies": {
              "type": "object",
              "description": "A mapping of policy IDs to their definitions. A policy store can have multiple policies",
              "patternProperties": {
                "^[a-fA-F0-9]{40,64}$": {
                  "type": "object",
                  "description": "A single policy object identified by its unique ID.",
                  "required": ["description", "creation_date", "policy_content"],
                  "properties": {
                    "description": {
                      "type": "string",
                      "description": "Optional description of the policy."
                    },
                    "creation_date": {
                      "type": "string",
                      "format": "date-time",
                      "description": "ISO 8601 formatted timestamp indicating when the policy was created."
                    },
                    "policy_content": {
                      "type": "string",
                      "description": "Base64-encoded CEDAR policy content."
                    }
                  }
                }
              },
              "additionalProperties": false
            },
            "trusted_issuers": {
              "type": "object",
              "description": "A mapping of trusted issuer IDs to their metadata.",
              "patternProperties": {
                "^[a-fA-F0-9]{40,64}$": {
                  "type": "object",
                  "description": "Metadata for a trusted issuer identified by a unique hash.",
                  "required": ["name"],
                  "properties": {
                    "name": {
                      "type": "string",
                      "description": "Name of the trusted issuer."
                    },
                    "description": {
                      "type": "string",
                      "description": "A human-readable description of the issuer (e.g., identity provider type)."
                    },
                    "openid_configuration_endpoint": {
                      "type": "string",
                      "format": "URI",
                      "description": "OpenID Connect discovery endpoint URL for this issuer."
                    },
                    "additionalProperties": true
                  }
                }
              },
              "additionalProperties": false
            },
            "schema": {
              "type": "string",
              "description": "Base64-encoded schema associated with the policy store."
            },
            "default_entities": {
              "type": "string",
              "description": "Base64-encoded entities that contain static information needed by an application."
            }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

## Policy store examples

### Policy store with two policies

```
{
    "cedar_version": "4.4.0",
    "policy_stores": {
        "9496b204911615307f6338de8a18c6885f2370793c31": {
            "name": "todo_app_policy_store",
            "description": "",
            "policies": {
                "1310471f02198263fbd487f6b695afd929cbe830dc91": {
                    "description": "",
                    "creation_date": "2025-07-23T09:57:06.348765",
                    "policy_content": "QGlkKCIiKQpwZXJtaXQocHJpbmNpcGFsID09IEphbnM6OlVzZXI6OiJBbGljZSIsIGFjdGlvbiA9PSBKYW5zOjpBY3Rpb246OiJSZWFkIiwgcmVzb3VyY2UgPT0gSmFuczo6QXBwbGljYXRpb246OiJ0b2RvIik7"
                },
                "2227b487ece354ac4bf822f5f0f1f083532361db2691": {
                    "description": "",
                    "creation_date": "2025-07-23T09:59:55.341180",
                    "policy_content": "QGlkKCIiKQpwZXJtaXQocHJpbmNpcGFsID09IEphbnM6OlVzZXI6OiJKYWNrIiwgYWN0aW9uID09IEphbnM6OkFjdGlvbjo6IlNlYXJjaCIsIHJlc291cmNlID09IEphbnM6OlJvbGU6OiJTZWFyY2hhYmxlIik7"
                }
            },
            "trusted_issuers": {
                "3af079fa58a915a4d37a668fb874b7a25b70a37c03cf": {
                    "name": "jans",
                    "description": "Jans IDP",
                    "openid_configuration_endpoint": "https://jans-host.com/.well-known/openid-configuration",
                    "token_metadata": {
                        "access_token": {
                            "trusted": true,
                            "entity_type_name": "Jans::Access_token",
                            "user_id": "sub",
                            "token_id": "jti",
                            "workload_id": "rp_id",
                            "claim_mapping": {},
                            "required_claims": [
                                "jti",
                                "iss",
                                "aud",
                                "sub",
                                "exp",
                                "nbf"
                            ],
                            "role_mapping": "role",
                            "principal_mapping": [
                                "Jans::Workload"
                            ]
                        },
                        "id_token": {
                            "trusted": true,
                            "entity_type_name": "Jans::id_token",
                            "user_id": "sub",
                            "token_id": "jti",
                            "role_mapping": "role",
                            "claim_mapping": {},
                            "principal_mapping": [
                                "Jans::User"
                            ]
                        },
                        "userinfo_token": {
                            "trusted": true,
                            "entity_type_name": "Jans::Userinfo_token",
                            "user_id": "sub",
                            "token_id": "jti",
                            "role_mapping": "role",
                            "claim_mapping": {},
                            "principal_mapping": [
                                "Jans::User"
                            ]
                        },
                        "tx_token": {
                            "trusted": true,
                            "entity_type_name": "Jans::Access_token",
                            "user_id": "sub",
                            "token_id": "jti"
                        }
                    }
                },
                "7e84b6790b6cc3a5aa8d9501295abf62d6a07bcb3665": {
                    "name": "acb",
                    "description": "second issuer",
                    "openid_configuration_endpoint": "https://jans-host.com/.well-known/openid-configuration",
                    "token_metadata": {
                        "access_token": {
                            "trusted": true,
                            "entity_type_name": "Jans::Access_token",
                            "user_id": "sub",
                            "token_id": "jti",
                            "workload_id": "rp_id",
                            "claim_mapping": {},
                            "required_claims": [
                                "jti",
                                "iss",
                                "aud",
                                "sub",
                                "exp",
                                "nbf"
                            ],
                            "role_mapping": "role",
                            "principal_mapping": [
                                "Jans::Workload"
                            ]
                        },
                        "id_token": {
                            "trusted": true,
                            "entity_type_name": "Jans::id_token",
                            "user_id": "sub",
                            "token_id": "jti",
                            "role_mapping": "role",
                            "claim_mapping": {},
                            "principal_mapping": [
                                "Jans::User"
                            ]
                        },
                        "userinfo_token": {
                            "trusted": true,
                            "entity_type_name": "Jans::Userinfo_token",
                            "user_id": "sub",
                            "token_id": "jti",
                            "role_mapping": "role",
                            "claim_mapping": {},
                            "principal_mapping": [
                                "Jans::User"
                            ]
                        },
                        "tx_token": {
                            "trusted": true,
                            "entity_type_name": "Jans::Access_token",
                            "user_id": "sub",
                            "token_id": "jti"
                        }
                    }
                }
            },
            "schema": "ewogICAgIkphbnMiOiB7CiAgICAgICAgImNv...",
            "default_entities": {"1694c954f8d9": "ey3dIlkXdmZhs9la0...", ...}
        }
    }
}
```

## Drawbacks

Why should we *not* do this? Please consider:

There are no apparent drawbacks to creating this specification. Primarily owing to the facts below:

- Implementation cost: None, as this specification does not require any code changes in the Cedar language
- Migration of applications using Cedar: Apps using Cedar can choose not to adopt this specification. It is voluntary. If they choose to adopt, the apps can take a gradual path to adopt this specification. Release of this specification does not force compliance or timelines on applications using Cedar. 

## Alternatives

Not applicable

## Unresolved questions

None






