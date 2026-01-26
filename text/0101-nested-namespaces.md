# Allow Nested Namespaces in Cedar Schemas

## Related issues and PRs

- Reference Issues:
- Implementation PR(s):

## Timeline

- Started: 2025-08-22
- Accepted: TBD
- Stabilized: TBD

## Summary

As of today, Cedar does not allow for defining nested namespaces. Instead, a schema writer must define fully qualified namespaces at the top-level of a schema file. At times this can be unintuitive and make it difficult to write schemas with proper name hygiene.

## Basic example

Suppose, we want to write a Schema for defining entity's and types that are grouped in a hierarchical structure (e.g., representing components of an organization). Consider the below example schema that defines entity types for AWS's and Google's identity and storage services.

```
namespace aws {
  namespace iam {
    entity User {
      department: String,
      role: String,
      clearanceLevel: Long
    }
    entity Group {
      groupType: String,
      maxClearance: Long
    }
  }

  namespace s3 {
    entity Bucket {
      region: String,
      sensitivity: Long
    }

    entity Object {
      type: String,
      owner: iam::User
    }
  }
}

namespace google {
  namespace identity {
    entity User {
      email: String,
      organizationId: String,
    }
    entity ServiceAccount {
      displayName: String,
      projectId: String,
    }
  }

  namespace storage {
    entity Bucket {
      projectId: String,
      location: String,
      storageCLass: String,
    }
    entity Object {
      contentType: String,
      owner: identity::User,
    }
  }
}
```

Note, that in today, the above schema is not possible due to nested namespaces. Instead, one must write the above schema as:

```
namespace aws::iam {
  entity User {
    department: String,
    role: String,
    clearanceLevel: Long
  }
  entity Group {
    groupType: String,
    maxClearance: Long
  }
}

namespace aws::s3 {
  entity Bucket {
    region: String,
    sensitivity: Long
  }

  entity Object {
    type: String,
    owner: aws::iam::User
  }
}

namespace google::identity {
  entity User {
    email: String,
    organizationId: String,
  }
  entity ServiceAccount {
    displayName: String,
    projectId: String,
  }
}

namespace google::storage {
  entity Bucket {
    projectId: String,
    location: String,
    storageCLass: String,
  }
  entity Object {
    contentType: String,
    owner: google::identity::User,
  }
}
```

While the current namespaces make it possible to distinguish between the similarly named `aws::iam::User` and `google::identity::User` and `aws::s3::Bucket` and `google::storage::Bucket`. It is unintuitive that  the sub-namespaces cannot be nested in a single namespaces for `aws` and `google`, respectively and similarly that one cannot refer to `iam::User` inside `aws::s3` without fully qualifying the name as `aws::iam::User`.

## Motivation

In authorization, many types are naturally structured in a hierarchy (e.g., why we support defining hierarchies of identities). As such, it would be more intuitive for users to be allowed to define hierarchical namespaces that are explicitly nested that allow referencing those related resources via relative paths. Programmers naturally (and I think rightfully), expect to be able to define namespaces and types in a structured way.

## Detailed design

This RFC proposes updating the parser and name resolution algorithm for Cedar Schemas to enable nested namespaces with relative namespace resolution (for nested namespaces). Consider the example from above (with AWS and Google identity and storage entity types). This RFC proposes that both schemas are accepted and once parsed result in equal Schemas.

### Updated Schema Syntax

This RFC proposes that a Schema is a sequence of `Decl`s, a namespace is a namespace declaration containing a sequence of `Decls` and a `Decl` may now be a `Namespace`. This is opposed to the current grammar in which  a Schema is a sequence of `Namespaces` which is either a namespace declaration containing a sequence of `Decl`s or a `Decl` without any surrounding namespace (i.e., within the root level namespace).

The proposed grammar will allow for both nested namespaces (new) and fully qualified namespaces at the top level (current).

```
Annotation := '@' IDENT '(' STR ')'
Annotations := {Annotations}
Schema := {Decl}
Decl := Entity | Action | TypeDecl | Namespace
Namespace := Annotations 'namespace' Path '{' {Decl} '}'
Entity := Annotations 'entity' Idents ['in' EntOrTyps] [['='] RecType] ['tags' Type] ';' | Annotations 'entity' Idents 'enum' '[' STR+ ']' ';'
Action := Annotations 'action' Names ['in' RefOrRefs] [AppliesTo]';'
TypeDecl := Annotations 'type' TYPENAME '=' Type ';'
Type := Path | SetType | RecType
EntType := Path
SetType := 'Set' '<' Type '>'
RecType := '{' [AttrDecls] '}'
AttrDecls := Annotations Name ['?'] ':' Type [',' | ',' AttrDecls]
AppliesTo := 'appliesTo' '{' AppDecls '}'
AppDecls := ('principal' | 'resource') ':' EntOrTyps [',' | ',' AppDecls]
          | 'context' ':' RecType [',' | ',' AppDecls]
Path := IDENT {'::' IDENT}
Ref := Path '::' STR | Name
RefOrRefs := Ref | '[' [RefOrRefs] ']'
EntTypes := Path {',' Path}
EntOrTyps := EntType | '[' [EntTypes] ']'
Name := IDENT | STR
Names := Name {',' Name}
Idents := IDENT {',' IDENT}

IDENT := ['_''a'-'z''A'-'Z']['_''a'-'z''A'-'Z''0'-'9']*
TYPENAME := IDENT - RESERVED
STR := Fully-escaped Unicode surrounded by '"'s
PRIMTYPE := 'Long' | 'String' | 'Bool'
WHITESPC := Unicode whitespace
COMMENT := '//' ~NEWLINE* NEWLINE
RESERVED := 'Bool' | 'Boolean' | 'Entity' | 'Extension' | 'Long' | 'Record' | 'Set' | 'String'
```


### Why relative name resolution for only structurally nested namespaces and not any namespace with the same path prefix?

Consider the schema:

```
namespace Bar {
  entity Thing; // (1)
}

namespace Foo::Bar {
  entity Thing; // (2)
}

namespace Foo {
  type MyThing = Bar::Thing;
}
```

Today, this is a currently valid schema. In which `Foo::MyThing` is a common type referring to `Bar::Thing` (definition 1). If we were to do relative name resolution based on namespaces with equal path prefixes, then `Foo::MyThing` would instead be a common type referring to `Foo::Bar::Thing` (definition 2), which would be backwards compatible.

However, this RFC proposes that for nested namespaces, most users would expect definition 2 would be used. This RFC proposes that for structurally nested namespaces, definitions defined within the namespace declaration shadow namespaces outside of the namespace declaration.

```
namespace Bar {
  entity Thing; // (1)
}

namespace Foo {
  namespace Bar {
    entity Thing; // (2)
  }
  type MyThing = Bar::Thing;
}
```

Similarly, for the below schema, this RFC proposes that `Foo::Bar::Baz::MyUser` be a common type that references definition 2, because it's nested namespace scope is the closest enclosing scope to the common type declaration. 

```
namespace Foo {
  entity User; // (1)
  namespace Bar {
    entity User; // (2)

    namespace Baz {
      type MyUser = User;
    }
  }
```

### Name Resolution Algorithm

Below is some pythonic pseudo-code for determining name resolution (simplified to only concern the portions of name resolution that are due to nested namespace, e.g., not dealing with specifics of common types, cedar_types, etc.).

The algorithm is: first check the current namespace for the name. If it's not found in the current namespace check for any containing namespaces (note, a namespace only has a parent if it is a nested namespace), and otherwise search the global namespace for the name's definition.

```
resolve(name, this_scope, global_decls):
  if name in this_scope:
    return this_scope[name]
  else if this_scope.has_parent():
    return resolve(name, this_scope.parent(), global_decls):
  else:
    return global_decls[name]
```

## Drawbacks

While this change is likely to improve how one writes schemas, we should support nested schemas in a backwards compatible way. This means that, how we perform name resolution may be tricky in order to support backwards compatibility. This may either (1) limit how much users can exploit nested namespaces to use relative namespace identifies when defining entities and types or (2) increase the complexity of name resolution which may slow down parsing of Cedar Schemas.

## Alternatives

The primary alternative is not accepting this rfc and instead keeping the status quo. I believe the current status quo is a worse user experience when writing a Cedar schema but would not encounter the drawbacks stated above.

An alternative to defaulting to use names (resolving to the name within the closest containing namespace), we could instead add explicit path identifiers for the current or containing scopes, e.g., `:this::User` and `:super::User` to help disambiguate relative versus global paths.
