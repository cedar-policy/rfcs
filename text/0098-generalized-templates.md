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

Cedar templates are quite restrictive. There are only two slots provided (```?principal``` and ```?resource```) and they are limited to appearing in the scope of the policy. This results in users' of Cedar needing to come up with their own [solution](https://github.com/cedar-policy/rfcs/pull/3#issuecomment-1632645305) to handling templates that can not be expressed in Cedar currently. In this RFC, we propose to generalize Cedar templates to support: 

1. Allowing ```?principal``` and ```?resource``` in the condition of the policy only if they also appear in the scope as well.  
2. Allowing for an arbitrary number of user defined slots to appear in the ```when/unless``` clause of the template contingent on the type being explicitly annotated. This would also include slots that are not entity types. 

Both of these additions, do not seem to require substiantial changes to the existing type checking code. However, that may change upon diving deeper into the implementation. 

For policies without schemas generalized templates will be supported. Correct type annotations will need to be supplied by a user of Cedar and a link time check will be performed to make sure that instantiations of the template are values of that type. However, note that without a schema it is still possible for a program that passes the link time type check to exhibit runtime errors. 

## Basic example

### Example 1 

By allowing ```?principal``` and ```?resource``` in the condition of the policy if it also appears in the scope, it allows us to express templates where we want to access attributes of a slot. In this example since we are able to allow ```?resource``` in the condition of the policy we are able to express the constraint that we can only view resource's who's owner is the same as the owner of the resource that we instantiate for the typed hole. 

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

In this example suppose that a company only wants to provide access to it's internal services only when the employee starts working. A user of Cedar trying to implement this policy might implement it as follows with our generalized templates. 

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

Suppose there are certain professors with dual appointments under two different departments. You want to give students of their group access to both the resources in the first department and the resources in their second department. 

Note: Although we can create two seperate templates and instantiate them individually, by using generalized templates we are able to make sure that these two templates stay in sync. Error states where only one part of the template is applied but not the other would not occur. Generalized templates allows us to subsume the functionality described in [#7](https://github.com/cedar-policy/rfcs/pull/7) and with typed slots we can for the most part express the motivating example for template-groups.

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

The main motivation to support generalized templates is to allow users to take advantages of templates: (1) prevention against injection attacks (2) ability to change a group of policies overtime. At the same time however, we still want to balance validation, and analysis on templates. 

In it's previous form, generalized templates were proposed to allow ```?principal``` and ```?resource``` in the condition if it was in the scope and disallowing arbitrary slots. However, this addition would not be able to capture the use cases of examples #2, #3, and #4. 

In this proposal, by having the Cedar user explicitly supply types for slots that are not ```?principal``` and ```?resource``` we are able to express all of the examples listed above while still supporting analysis on templates and allowing for link time validation to be more performant (we can just check that the supplied values are inhabitants of the types of the slots rather than running the type checker on the instantiated template when the slots are filled in). Types are also a form of documentation that can help with reading templates in the future. 

## Detailed design

The implementation of (1) Allowing ```?principal``` and ```?resource``` in the condition of the policy only if they also appear in the scope as well will not require changes to the typechecker code. 

For example, consider this schema and template:

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

permit (principal, action == Action::Navigate, resource in ?resource) 
when { 
  ?resource has storage && ?resource.storage == 5 
};
```
Currently, how Cedar's typechecker works for templates is by enumerating all possible request environments for a particular action. Take for example, in this case the possible ```principal``` and ```resource``` pairs would be ```(FS::Person, FS::Disk)```, ```(FS::Person, FS::Folder)```, ```(FS::Person, FS::Document)```. Then under these individual request environments we generate the possible slot types for principal and resource. 
| Request Environment | Principal Slot Types | Resource Slot Types
| -------- | ------- | ------- |
| ```(FS::Person, FS::Disk)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk``` | 
| ```(FS::Person, FS::Folder)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder``` | 
| ```(FS::Person, FS::Document)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder```, ```?resource: FS::Document``` | 

With this, we check to see if for all request environments any combination of their respective ```?principal``` and ```?resource``` slot types evaluates to a boolean. If they do, then our typechecker passes otherwise it fails. 

With this extension, we would now need to check if for all combinations of valid types for ```principal```, ```resource```, ```?principal```, and ```?resource``` our template including the condition evaluates to a boolean. Cedar's validator already handles this case and the only change that would need to made is to check whether or not ```?principal``` or ```?resource``` appears in the scope of the template. 

The implementation of (2) Allowing for an arbitrary number of user defined slots to appear in the condition of the policy contingent on the type being explicitly annotated would involve adding an additional map to store slot variables with their corresponding types. This will likely not involve any changes to the typechecker and typechecking can proceed as described above. 

For users that don't provide a schema, generalized templates will support typed slots with link time checking of types. Here, it is up to the user to provide correct types. Note that without schemas there are no guarantees made about the runtime behavior of your program. Policies such as the following, where ```?bound1``` is provided a substitution of ```true``` will still be able to be expressed and an error will be thrown at runtime. The only check that is provided when you do not use a schema with generalized templates is that the value you substitute in for ```?bound1``` is indeed of the type that you had specified, in this case ```Bool```.

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

```?principal``` and ```?resource``` can optionally have their types annotated in ```template()```. A similiar effect can be done using the ```is``` operator in the condition. However, this would allow templates to be instantiated with slots always evaluate to false. By having an explicit type annotation, we prevent these instantiations from being linked in the first place. 

The proposed syntax looks as follows ```template(?bound1: type1, ?bound2: type2) =>``` and types specified must be valid schema types. Schema types are chosen over AST types because they allow us to more precisely specify the type for sets and records. Each new typed slot requires a distinct variable name. However, within the when/unless clause the same typed slot can be used multiple times. The grammar of template annotations is as follows. ```Type``` is taken directly from the Cedar documentation for schema types.

```
Template := 'template' '(' ( TypeAnnotation { ',' TypeAnnotation } ) ')' '=>'

TypeAnnotation := ‘?’ IDENT ‘:’ Type

Type := Path | SetType | RecType
```

Typed slots can only be instantiated with value types. In the implementation this corresponds to the ```RestrictedExpression``` type. 

This proposal will have to touch Cedar's AST, typechecker, parser and introduce type checking when linking with templates. In addition to maintain backwards compatability with the current API, interacting with generalized templates will have to be treated under a seperate set of API functions. 

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

## Drawbacks

Type annotations for slots can be a user burden.    

## Alternatives

1. Type inference. We would perform type inference by considering the valid types of the slots that allow for Cedar templates to evaluate to a boolean. 

Any slot on the left or the right of a ```==, <, <=, !=``` would have type as the opposite side. Two slots cannot be compared using ```==, <, <=, !=```.

Any slot that is being compared using ```.lessThan()``` would have ```decimal``` type.

Any slot that is used with ```&&, ||, !``` has boolean type.

Any slot that is used with ```if <boolean> then <T> else <U>``` must have boolean type if it appears in the guard and can have AnyType

Slots can only appear on the left hand side of a ```has``` and must be a type of an entity that has this attribute. 

Downsides: 
1. It could result in analysis being overly general, since it would now have to consider all possible combinations of the types of the slots that will allow for link time validation to succeed.
2. Type annotation is not much overhead.
3. It is possible that the inferred possible types is different from what the user expects.
4. There would need to be some restrictions on where slots can appear which can be unintuitive for users. (```?slot1 == ?slot2```, would result in us only being able to infer the type of the slot as AnyType) 

## Unresolved questions

1. What should the syntax be for supplying aribtrary bound variables be. There was some discussion of it [here](https://github.com/cedar-policy/rfcs/pull/3#issuecomment-1611845728). Initial thoughts are to ensure that the user supplies a map so there is no confusion with regards to ordering. 

2. Would we want to generalize the action clause. This can support even more general templates. However, it becomes less clear what the connection of each template is with each other if we support a ```?action``` slot. This would also likely result in difficulty with analysis of templates since now ```?principal``` and ```?resource``` would have no constraints on them. 

3. Will it be confusing for users' of Cedar that even though we perform a type check when we don't use a schema that there can still be runtime errors?

4. Currently, there will be no reserved keywords for typed slots. Should there be any? 
