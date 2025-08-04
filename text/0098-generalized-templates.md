# Generalized Templates

## Related issues and PRs

- Reference Issues: [#3](https://github.com/cedar-policy/rfcs/pull/3),
                    [#7](https://github.com/cedar-policy/rfcs/pull/7),
                    [#81](https://github.com/cedar-policy/cedar/issues/81),

- Implementation PR(s): (leave this empty)

## Timeline

- Started: 2025-05-13
- Accepted: TBD
- Stabilized: TBD

## Summary

Cedar templates are quite restrictive. There are only two slots provided (```?principal``` and ```?resource```) and they are limited to appearing in the scope of the template. This results in users of Cedar needing to come up with their own [solution](https://github.com/cedar-policy/rfcs/pull/3#issuecomment-1632645305) to handling templates that can not be expressed in Cedar currently. In this RFC, we propose to generalize Cedar templates in two different ways: 

1. We want to relax the restriction on the two slots (```?principal``` and ```?resource```) that Cedar currently provides to allow them to appear in the condition of the template if they also appear in the scope.

2. We want to allow for an arbitrary number of user defined slots to appear in the condition (```when/unless```) clause of the template if the type is explicitly annotated. Annotated types can be of any valid Cedar Schema Type including common types. User defined slots are different from ```?principal``` and ```?resource``` slots because they can be instantiated with values that are not entity types and also can not appear in the scope. 

For users of Cedar who do not use a schema, type declarations for generalized templates are optional. Templates will not be validated, but type checking will be performed during link-time. While this ensures that the provided values match the type of slot they are filling, it does not ensure that the policy won't experience a run-time type error.

## Basic example

### Example 1 

Suppose you are building a document signing application. For security purposes, you want to make sure that whenever someone shares a document the receiver can only access it for x amount of days. We can use generalized templates to define this as shown below. 

Everytime this template is instantiated the slots ```?principal``` and ```?resource``` will be replaced with the entity type that represents the person that you want to share the document with and the entity type representing the document that you want to share. Additionally ```?startTime``` and ```?endTime``` will be replaced with the datetime bounds.

By using generalized templates compared to an attribute of an entity to express this policy, we do not have to store information that is only relevant to our authorization decisions within an external data store. This allows us to have a cleaner seperation of concerns. 

#### Schema 
```
entity Document = {
    owner: Person 
};
entity Person;

action Access appliesTo {
    principal: FS::Person,
    resource: [FS::Document],
    context: { date: datetime }
};
```

#### Template 
```
template(?startTime: datetime, ?endTime: datetime) =>
permit(principal == ?principal, 
action, 
resource == ?resource) when 
{ ?startTime <= context.now && 
context.now <= ?endTime };
```

### Example 2
In this example, suppose we have a file sharing application where we can create folders and documents. Every document created must be in a folder. We want to express the policy that if you are an owner of the folder then you can access any document within it. We can use generalized templates to define this as shown below. 

Now everytime we create a folder, we link ```?resource``` with that folder to express this relationship. 

An alternative way to do this is to store an additional owner attribute for every document, however this has a couple of drawbacks compared to using Generalized Templates. 

(1) We lose the intent behind why we are authoring this policy. 

(2) When transferring ownership of a folder to someone else you would have to manually update the owner attribute for all document's that belong to that folder 

#### Schema
```
namespace FS {
    entity Folder;
    entity Document in Folder;
    entity Person = {
        owned_documents: Set<Document>
    };
}

action AccessDocument appliesTo {
    principal: FS::Person,
    resource: FS::Document,
};
```

#### Template
```
permit(principal, action == Action::"AccessDocument", resource in ?resource) { 
    ?resource in principal.owned_documents
}
```

### Example 3

Suppose there are certain professors with dual appointments under two different departments who want to give students of their group access to both the resources in the first department and the resources in their second department. 

Note: Although we can create two seperate templates and instantiate them individually, we would need to make sure they stay in sync. With generalized templates, since there is only one template we do not need to do so. Error states where only one part of the template is applied but not the other would not be able to occur. Generalized templates allows us to subsume the functionality described in [#7](https://github.com/cedar-policy/rfcs/pull/7) and with typed slots we can express the motivating example for template-groups.

#### Schema 
```
namespace University {
    entity Person = {
        graduationDate: dateTime
    };
    entity Department;
    entity InternalDoc in Department;
}
    
action View appliesTo {
    principal: University::Person,
    resource: University::InternalDoc,
    context: { date: dateTime }
}
```

#### Template  
```
template(?department1: University::Department, ?department2: University::Department) => 
permit(
  principal == ?principal
  action == Action::"View",
  resource 
) when {
    (resource in ?department1 || 
    resource in ?department2) &&
    context.date < principal.graduationDate 
};
```

## Motivation

This is a follow up on the discussion on [#3](https://github.com/cedar-policy/rfcs/pull/3). 

Cedar templates offer a way to change a group of policies overtime and to prevent against injection attacks that can occur when creating policies at runtime. However, there are policies that users of Cedar want to create at runtime that can't be expressed using templates today. By generalizing Cedar templates, we hope to allow for more users to be able to use templates while still balancing Cedar's core features: validation, analysis, performance, and ergonomics.

While annotating the types of user defined slots inccurs some user burden, it allows us additional expressivity while still supporting validation and analysis. It also allows us to keep Cedar performant. With types, link time validation only requires checking that the supplied values have the same type as what is annotated, the alternative being running the type checker everytime you instantiate your template. Types also serve as a form of documentation that can help you remember what your templates are able to be linked against.

## Detailed design
### Implementation 
Below I provide a brief explanation of how Cedar's typechecker will work for ```?principal``` and ```?resource``` slots in the condition of the template and for user defined slots. 

Consider this schema and template:

#### Schema 
```
namespace FS {
    entity Disk = {
        storage: Long, 
    };
    entity Folder in Disk;
    entity Document in Folder;
    entity Person;
}

action Navigate appliesTo {
    principal: FS::Person,
    resource: [FS::Disk, FS::Folder, FS::Document],
};
```
#### Template
```
permit (principal == ?principal, action == Action::"Navigate", resource in ?resource) 
when { 
  ?resource has storage && ?resource.storage == 5 
};
```
Currently, how Cedar's typechecker works is by enumerating all possible request environments for a particular action. Based off this schema, the possible ```principal``` and ```resource``` pairs would be ```(FS::Person, FS::Disk)```, ```(FS::Person, FS::Folder)```, ```(FS::Person, FS::Document)```. Under these individual request environments, we can generate the possible slot types for principal and resource. 

| Request Environment | Principal Slot Types | Resource Slot Types
| -------- | ------- | ------- |
| ```(FS::Person, FS::Disk)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk``` | 
| ```(FS::Person, FS::Folder)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder``` | 
| ```(FS::Person, FS::Document)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder```, ```?resource: FS::Document``` | 

Under each individual enumeration, we now check to see if these respective assignment of types to variables and user defined slots evaluates to a boolean. If every enumeration does, then our template passes the typechecker, otherwise it fails. With ```?principal``` and ```?resource``` now appearing in the condition of the template, we would just need to use the type supplied by the request environment to type check it. 

Since user defined slots are required to have their types annotated, we do not need to perform this enumeration. Instead, now we use the type supplied by the user  and see if the template evaluates to a boolean type.

Note: Typed slots can only be instantiated with value types. In the implementation this corresponds to the ```RestrictedExpression``` type. 

### Users of Cedar that do not use a Schema
For users that don't provide a schema, generalized templates will support optional typed slots with link time type checking. Here, it is up to the user to provide correct types. Note that without schemas there are no guarantees made about the runtime behavior of your program. Policies such as the following, where ```?bound1``` is provided a substitution of ```true``` will still be able to be expressed and an error will be thrown at runtime. The only guarantee that is provided when you do not use a schema with generalized templates is that if you annotate the slot with a type, the value you substitute in for ```?bound1``` is indeed of the type that you had specified, in this case ```Bool```.

``` 
template(?bound1: Bool) => 
permit (
    principal, 
    action, 
    resource,
) when {
    1 + ?bound1
};
```

In addition, there is some subtlety involved when handling type declarations involving primitive types. The main issue stems from entity types being allowed to shadow primitive type. Without a schema to distinguish whether or not this is the case, we opt to be more permissive. We interpret primitive types as both entity types and Cedar primitive types and typechecking passes if one of the cases typechecks. 

### Syntax 
The proposed syntax looks as follows ```template(?bound1: type1, ?bound2: type2) =>``` and types specified must be valid schema types. Schema types are chosen over AST types because they allow us to more precisely specify the type for sets and records. Each new typed slot requires a distinct variable name. However, within the ```when/unless``` clause the same typed slot can be used multiple times. The grammar of template declarations is as follows. ```Type``` is taken directly from the Cedar documentation for schema types. The template syntax (```template(?bound1: type1, ?bound2: type2) =>```) must go after all the declarations. 

```
Template := 'template' '(' ( TypeAnnotation { ',' TypeAnnotation } ) ')' '=>'

TypeAnnotation := ‘?’ IDENT ‘:’ Type

Type := Path | SetType | RecType
```

### JSON Policy Format 
The changes to the JSON policy format would include another attribute ```typed_slots``` and would look as follows: 
```
"typed_slots": [
    { "type": "University::Department", "id": "?department1" }, 
    { "type": "University::Department", "id": "?department2" }, 
]
```

In the JSON policy format, typed slots can be referred to with the same syntax as what is done for ```?principal``` and ```?resource```, except with the identifier being replaced. It would look as follows: 
```
"slot": "?department1"
``` 


### ```?principal``` and ```?resource``` Slots

```?principal``` and ```?resource``` can optionally have their types annotated in ```template()```. A similiar effect can be achieved using the ```is``` operator in the condition. However, this would allow templates to be instantiated with slots that always evaluate to false. By having an explicit type annotation we prevent these instantiations from being linked in the first place. 

Aside from the optional type annotation for ```?principal``` and ```?resource``` slots, there are some other differences between them and user defined slots. For one, ```?principal``` and ```?resource``` slots must appear in the scope of the template and can optionally be in the condition of the template, however user defined slots can only appear in the condition clause. Because of this difference ```?principal``` and ```?resource``` slots can only be filled in with entity types and user defined slots can be filled in with any ```SchemaType```.

### What is allowed and not allowed?
1. Every user defined slot needs to have a type associated with it 
2. Disallow ```?action``` and ```?context``` slots
3. Annotated ```?principal``` and ```?resource``` types must be an entity type 
4. All slots within the template declaration (```template()```) must be used in the template 
5. ```?principal``` and ```?resource``` slots must appear in the scope
6. User defined slots can not appear in the scope
6. All slot names must begin with ```?```

## Drawbacks

1. Using ```?principal``` and ```?resource``` in the condition clause can cause confusion because it looks similiar to ```principal``` and ```resource```. 
2. Type declarations for slots can be a user burden.    

## Alternatives

### Type Inference
We would perform type inference by considering the valid types of the slots that allow for Cedar templates to evaluate to a boolean. 

Any slot on the left or the right of a ```==, <, <=, !=``` would have the same type as the opposite side. Two slots cannot be compared using ```==, <, <=, !=```.

Any slot that is being compared using ```.lessThan()``` would have ```decimal``` type.

Any slot that is used with ```&&, ||, !``` has boolean type.

Any slot that is used with ```if <boolean> then <T> else <U>``` must have boolean type if it appears in the guard and can have AnyType

Slots can only appear on the left hand side of a ```has``` and must be a type of an entity that has this attribute. 

... 

Downsides: 
1. It could result in analysis being overly general, since it would now have to consider all possible combinations of the types of the slots that will allow for link time validation to succeed.
2. It is possible that the inferred possible types is different from what the user expects.
3. There would need to be some restrictions on where slots can appear which can be unintuitive for users. (```?slot1 == ?slot2```, would result in us only being able to infer the type of the slot as AnyType) 

### Moving the type declarations to the Schema file rather than having them defined in the template. 

By moving the type declarations to the Schema file we can keep the notion of types all in one place and also not have to deal with the duplication of code to parse types. 

Downsides: 
1. By moving types into the Schema file we would not be able to have slots that are localized per template since there is no way to reference a specific template in the Schema. Instead we will have to declare all the slot names and their associated types in the global namespace. 
2. It is awkward to have type declarations in the Schema since when writing the Schema we have no foresight about what slots we will need in the template. 
3. It would prevent you from using link time type checking for generalized templates if you do not use a schema.

## Unresolved questions

