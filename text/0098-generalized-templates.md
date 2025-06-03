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

Cedar templates are quite restrictive. There are only two slots provided (```?principal``` and ```?resource```) and they are limited to appearing in the scope of the policy. This results in users of Cedar needing to come up with their own [solution](https://github.com/cedar-policy/rfcs/pull/3#issuecomment-1632645305) to handling templates that can not be expressed in Cedar currently. In this RFC, we propose to generalize Cedar templates in two different ways: 

1. We want to relax the restriction on the two slots (```?principal``` and ```?resource```) that Cedar currently provides to allow them to appear in the condition of the template if they also appear in the scope.

2. We want to allow for an arbitrary number of user defined slots to appear in the condition (```when/unless```) clause of the template if the type is explicitly annotated. User defined slots are different from the slots in Cedar currently because they can be instantiated with values that are not entity types and also can not appear in the scope. 

These two additions to generalize Cedar templates will not require substiantial changes to the existing type checking code. 

Generalized templates will be supported for users of Cedar that do not use a schema. Without a schema, type annotations for generalized templates are optional. Templates will not be validated, but type checking will be performed during link-time. While this ensures that the provided values match the type of slot they are filling, it does not ensure that the policy won't experience a run-time type error.

## Basic example

### Example 1 

By allowing ```?principal``` and ```?resource``` in the condition of the policy if they also appear in the scope, we can write templates that access attributes of a ```?principal``` or ```?resource slot```. In this example, since we are able to allow ```?resource``` in the condition of the policy, we are able to express the constraint that we can only view resources whose owner is the same as the owner of the entity that we instantiate for the typed hole. 

#### Schema 
```
namespace FS {
    entity Disk = {
        owner: String, 
    };
    entity Folder in Disk = {
        owner: String,
    };
    entity Document in Folder = {
        owner: String,
    };
    entity Person;
}

action Navigate appliesTo {
    principal: FS::Person,
    resource: [FS::Disk, FS::Folder, FS::Document],
};

action Write appliesTo {
    principal: FS::Person,
    resource: [FS::Disk, FS::Folder, FS::Document],
};
```

#### Cedar Template 
```
permit(
  principal == ?principal,
  action,
  resource in ?resource)
when {
    ?resource.owner == resource.owner 
};
```

### Example 2 
By allowing generalized typed slots we are able to express the following Cedar template. This example was taken directly from a user of Cedar in [#7](https://github.com/cedar-policy/rfcs/pull/7) and was what initially motivated generalized templates. 

#### Schema 
```
namespace FS {
    entity Disk;
    entity Folder in Disk;
    entity Document in Folder;
    entity Person;
}

action Navigate appliesTo {
    principal: FS::Person,
    resource: [FS::Disk, FS::Folder, FS::Document],
};

action Write appliesTo {
    principal: FS::Person,
    resource: [FS::Disk, FS::Folder, FS::Document],
};
```

#### Cedar Template 
```
template(?folder: FS::Folder) =>
permit(
  principal == ?principal,
  action,
  resource in ?resource)
when {
    // take any action in the scope that you're admin on
    resource in ?folder
        
    // allow access up the tree for navigation
    || (action == Action::Navigate && ?folder in resource)
};
```

### Example 3

In this example, suppose that a company only wants to provide access to it's internal services only when the employee starts working. Using generalized templates, a user of Cedar might implement it as follows: 

#### Schema 
```
namespace Company {
    entity Employee;
    entity InternalServices;
}
    
action Access appliesTo {
    principal: Company::Employee,
    resource: Company::InternalServices,
    context: { date: datetime }
}
```

#### Template 
```
template(?date: datetime) => 
permit(
  principal == ?principal, 
  action == Action::"Access",
  resource is Company::InternalServices
) when {
    context.date > ?date 
};
```

### Example 4

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

Templates offer a way to change a group of policies overtime and to prevent against injection attacks that can occur when creating policies at runtime. However, there are policies that users of Cedar want to create at runtime that can't be expressed with templates today. By generalizing Cedar templates, we hope to allow for more users of Cedar to take advantage of these benefits while still balancing Cedar's core features: validation, analysis, and performance. 

In it's previous form, generalized templates were proposed to only allow ```?principal``` and ```?resource``` slots in the condition if they also appear in the scope. However, with only this addition we would not be able to express the use cases of examples #2, #3, and #4. 

In this proposal, we add on to the previous one to also allow an arbitrary number of user defined slots to appear in the condition clause of the template if the type is explicitly annotated. 

By having the Cedar user explicitly supply types for slots that are not ```?principal``` and ```?resource``` we are able to express examples #2, #3, and #4 while still supporting validation and analysis on templates. Link time validation is also more performant because we can just check that the types of the supplied values are the same as the type annotations provided rather than running the type checker on the instantiated template. This is important since link time validation occurs during runtime. Types are also a form of documentation that can help with reviewing your templates in the future. 

## Detailed design
### Implementation 
The implementation of (1) Allowing ```?principal``` and ```?resource``` in the condition of the policy if they also appear in the scope will not require any changes to the typechecker code. 

Consider this schema and template:

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

permit (principal == ?principal, action == Action::"Navigate", resource in ?resource) 
when { 
  ?resource has storage && ?resource.storage == 5 
};
```
Currently, how Cedar's typechecker works is by enumerating all possible request environments for a particular action. In this case the possible ```principal``` and ```resource``` pairs would be ```(FS::Person, FS::Disk)```, ```(FS::Person, FS::Folder)```, ```(FS::Person, FS::Document)```. Then under these individual request environments we generate the possible slot types for principal and resource. 
| Request Environment | Principal Slot Types | Resource Slot Types
| -------- | ------- | ------- |
| ```(FS::Person, FS::Disk)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk``` | 
| ```(FS::Person, FS::Folder)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder``` | 
| ```(FS::Person, FS::Document)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder```, ```?resource: FS::Document``` | 

With this, we check to see if for all request environments any combination of their respective ```?principal``` and ```?resource``` slot types evaluates to a boolean. If they do, then our typechecker passes otherwise it fails. 

With this extension, we would now need to check if for all combinations of valid types for ```principal```, ```resource```, ```?principal```, and ```?resource``` our template including the condition evaluates to a boolean. Cedar's validator already handles this case and the only change that would need to be made is to check for whether or not ```?principal``` or ```?resource``` appears in the scope of the template. 

The implementation of (2) Allowing for an arbitrary number of user defined slots to appear in the condition of the policy if the type is annotated would involve modifying Cedar's AST to include generalized slots that also store types and modifying the associated type checking code to use the type associated with it. This will not involve any major changes to the typechecker and typechecking can proceed as described above. 

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

### Syntax 
The proposed syntax looks as follows ```template(?bound1: type1, ?bound2: type2) =>``` and types specified must be valid schema types. Schema types are chosen over AST types because they allow us to more precisely specify the type for sets and records. Each new typed slot requires a distinct variable name. However, within the when/unless clause the same typed slot can be used multiple times. The grammar of template annotations is as follows. ```Type``` is taken directly from the Cedar documentation for schema types. The template syntax (```template(?bound1: type1, ?bound2: type2) =>```) must go after all the annotations. 

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

```?principal``` and ```?resource``` can optionally have their types annotated in ```template()```. A similiar effect can be achieved using the ```is``` operator in the condition. However, this would allow templates to be instantiated with slots that always evaluate to false. By having an explicit type annotation, we prevent these instantiations from being linked in the first place. 

Aside from the optional type annotation for ```?principal``` and ```?resource``` slots, there are some other differences between them and user defined slots. For one, ```?principal``` and ```?resource``` slots must appear in the scope of the template and can optionally be in the condition of the template, however user defined slots can only appear in the condition clause. Because of this difference ```?principal``` and ```?resource``` slots can only be filled in with entity types and user defined slots can be filled in with any ```SchemaType```.

Currently, there is no good way forward to unify the behavior between these two kinds of slots.

### What is allowed and not allowed?
1. Every slot not ```?principal``` and ```?resource``` needs to have a type associated with it 
2. Disallow ```?action``` and ```?context``` slots
3. Annotated ```?principal``` and ```?resource``` types must be an entity type 
4. All slots within the template annotation (```template()```) must be used in the template 
5. ```?principal``` and ```?resource``` slots must appear in the scope
6. User defined slots can not appear in the scope
6. All slot names must beigin with ```?```

## Drawbacks

1. Using ```?principal``` and ```?resource``` in the condition clause can cause confusion because it looks similiar to ```principal``` and ```resource```. 
2. Type annotations for slots can be a user burden.    

## Alternatives

### Type Inference
We would perform type inference by considering the valid types of the slots that allow for Cedar templates to evaluate to a boolean. 

Any slot on the left or the right of a ```==, <, <=, !=``` would have type as the opposite side. Two slots cannot be compared using ```==, <, <=, !=```.

Any slot that is being compared using ```.lessThan()``` would have ```decimal``` type.

Any slot that is used with ```&&, ||, !``` has boolean type.

Any slot that is used with ```if <boolean> then <T> else <U>``` must have boolean type if it appears in the guard and can have AnyType

Slots can only appear on the left hand side of a ```has``` and must be a type of an entity that has this attribute. 

... 

Downsides: 
1. It could result in analysis being overly general, since it would now have to consider all possible combinations of the types of the slots that will allow for link time validation to succeed.
2. It is possible that the inferred possible types is different from what the user expects.
3. There would need to be some restrictions on where slots can appear which can be unintuitive for users. (```?slot1 == ?slot2```, would result in us only being able to infer the type of the slot as AnyType) 

### Moving the type annotations to the Schema file rather than having them defined in the template. 

By moving the type annotations to the Schema file we can keep the notion of types all in one place.

Downsides: 
1. By moving types into the Schema file we would not be able to have slots that are localized per template since there is no way to reference a specific template in the Schema. Instead we will have to declare all the slot names and their associated types in the global namespace. 
2. It is awkward to have type annotations in the Schema since when writing the Schema we have no foresight about what slots we will need in the policy. 
3. It would prevent you from using link time type checking for generalized templates if you do not use a schema.

## Unresolved questions

1. What should the syntax be for supplying aribtrary bound variables be. There was some discussion of it [here](https://github.com/cedar-policy/rfcs/pull/3#issuecomment-1611845728). Initial thoughts are to ensure that the user supplies a map so there is no confusion with regards to ordering. 


