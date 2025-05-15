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

Cedar templates are quite restrictive. There are only two slots provided (```?principal``` and ```?resource```) and they are limited to appearing in the scope of the policy. This results in users of Cedar needing to come up with their own [solution](https://github.com/cedar-policy/rfcs/pull/3#issuecomment-1632645305) to handling templates that can not be expressed in Cedar currently. In this RFC, we propose to generalize Cedar templates to support: 

1. Allowing ```?principal``` and ```?resource``` in the condition of the policy only if they also appear in the scope as well.  
2. Allowing for an arbitrary number of user defined slots to appear in the ```when/unless``` clause of the policy contingent on the type being explicitly annotated. This would also include slots that are not entity types. 

Both of these additions, do not seem to require substiantial changes to the existing type checking code. However, that may change upon diving deeper into the implementation. 

Generalized templates should only be used when provided a schema and strict validation mode. 

## Basic example

### Example 1 

By allowing ```?principal``` and ```?resource``` in the condition of the policy we are able to express the following Cedar template. This example was taken directly from a user of Cedar in [#7](https://github.com/cedar-policy/rfcs/pull/7). 

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

action "Navigate" appliesTo {
    principal: FS::Person,
    resource: [FS::Disk, FS::Folder, FS::Document],
};

action "Write" appliesTo {
    principal: FS::Person,
    resource: [FS::Disk, FS::Folder, FS::Document],
};
```

#### Cedar Template 
```
@id("Admin")
permit(
  principal == ?principal,
  action,
  resource in ?resource)
when {
    // take any action in the scope that you're admin on
    resource in ?resource
        
    // allow access up the tree for navigation
    || (action == Action::"Navigate" && ?resource in resource)
};
```

### Example 2 

In this example suppose that a company only wants to provide access to it's internal services only when the employee starts working and has finished all of their security training. A user of Cedar trying to implement this policy might implement it as follows with our generalized templates. 

#### Schema 
```
namespace Company {
    entity Employee = {
        startDate: dateTime 
    }; 
    entity InternalServices;
}
    
action "Access" appliesTo {
    principal: Company::Employee,
    resource: Company::InternalServices,
    context: {"date": datetime }
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
 context.date > employee.startDate && context.date > ?date 
};
```

### Example 3 

Suppose there are certain professors with dual appointments under two different departments. You want to give students of their group access to both the resources in the first department and the resources in their second department. 

Note: Although we can create two seperate templates and instantiate them individually, by using generalized templates we are able to make sure that these two templates stay in sync. Error states where only one part of the template is applied but not the other would not occur. Generalized templates subsumes the functionality described in [#7](https://github.com/cedar-policy/rfcs/pull/7).

#### Schema 
```
namespace University {
    entity Person = {
        graduationDate: dateTime
    };
    entity Department;
    entity InternalDoc in Department;
}
    
action "View" appliesTo {
    principal: University::Person,
    resource: University::InternalDoc,
    context: {"date": dateTime }
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

In it's previous form, generalized templates were proposed to allow ```?principal``` and ```?resource``` in the condition if it was in the scope and disallowing arbitrary slots. However, this would only be useful when we are using the ```is``` or ```in``` constraint. Since when we have ```==``` we can just directly use the variables ```principal``` for ```?principal``` and ```resource``` for ```?resource``` directly. This did not seem to have any direct use cases so the proposal was eventually rejected. 

In this proposal, by having the Cedar user explicitly supply types we solve 2 main problems:

1. We can support analysis on templates 

2. Link time validation would be more performant (we can just check that the supplied values are inhabitants of the types of the slots rather than running the type checker on the policy when the slots are filled in)

## Detailed design

The implementation of (1) Allowing ```?principal``` and ```?resource``` in the condition of the policy only if they also appear in the scope as well would not change any of the existing validator code. 

For example, consider this schema and policy. 

```
namespace FS {
    entity Disk = {
        storage: Long, 
    };
    entity Folder in Disk;
    entity Document in Folder;
    entity Person;
}

action "Navigate" appliesTo {
    principal: FS::Person,
    resource: [FS::Disk, FS::Folder, FS::Document],
};

permit (principal, action == Action::"Navigate", resource in ?resource) 
when { 
  ?resource has storage && ?resource.storage == 5 
};
```
Currently, how Cedar's typechecker works for templates is by enumerating all possible valid request environments for a particular action. Take for example, in this case the possible ```principal``` and ```resource``` pairs would be ```(FS::Person, FS::Disk)```, ```(FS::Person, FS::Folder)```, ```(FS::Person, FS::Document)```. Then under these individual request environments we generate the possible slot types for principal and resource. 
| Request Environment | Principal Slot Types | Resource Slot Types
| -------- | ------- | ------- |
| ```(FS::Person, FS::Disk)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk``` | 
| ```(FS::Person, FS::Folder)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder``` | 
| ```(FS::Person, FS::Document)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder```, ```?resource: FS::Document``` | 

With this, we check to see if, for any combination of valid request environment and their corresponding ```principal``` and ```resource``` slot types, our policy evaluates to a boolean. 

Since ```?resource``` and ```?principal``` can now appear in the condition of the template we now have to also ensure that for all valid request environments, principal slot type, and resource slot type combinations our template will always evaluate to a boolean. This change would just involve performing a substitution of the appropriate type for each case in the condition in addition to the scope. 

The implementation of (2) Allowing for an arbitrary number of user defined slots to appear in the condition of the policy contingent on the type being explicitly annotated would involve adding a map to store slot variables that are not in the scope with their corresponding types. 

This proposal will have to touch Cedar's AST, typechecker, parser and introduce validation while linking with Cedar templates. 

The proposed syntax looks as follows template(?bound1: type1, ?bound2: type2) =>. 

<!-- This is the bulk of the RFC. Explain the design in enough detail for somebody familiar with Cedar to understand, and for somebody familiar with the implementation to implement. This should get into specifics and corner-cases, and include examples of how the feature is used. Any new terminology should be defined here. -->

## Drawbacks

Type annotations for slots can be a user burden.    

## Alternatives

1. Type inference. We would perform type inference by considering the valid types of the slots that allow for Cedar templates to be well typed (evaluate to a boolean). 

Any slot on the left or the right of a ```==, <, <=, !=``` would have type as the opposite side. Two slots cannot be compared using ```==, <, <=, !=```.

Any slot that is being compared using ```.lessThan()``` would have ```decimal``` type.

Any slot that is used with ```&&, ||, !``` has boolean type.

Any slot that is used with ```if <boolean> then <T> else <U>``` must have boolean type if it appears in the guard and can have AnyType

Slots can only appear on the left hand side of a ```has``` and must be a type of an entity that has this attribute. 

... 

Downsides: 
1. It is possible that the inferred possible types is different from what the user expects and annotation isn't a large burden.  
2. It is unclear how this would work with analysis of templates. We can enumerate the valid types that can appear but this can be a very large set. 
3. There would need to be some restrictions on where slots can appear that can be unintuitive for users. 

## Unresolved questions

1. What should the syntax be for supplying aribtrary bound variables be. There was some discussion of it (here)[https://github.com/cedar-policy/rfcs/pull/3#issuecomment-1611845728]. Initial thoughts are to ensure that the user supplies a map 

2. Would we want to generalize the action clause. This can support even more general templates. However, it becomes less clear what the connection of each template is with each other if we support a ```?action``` slot. This would also likely result in difficulty with analysis of templates since now ```?principal``` and ```?resource``` would have no constraints on them until link time. This would also involve some changes in the validator code since we would not be able to 
