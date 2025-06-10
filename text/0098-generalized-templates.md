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

Cedar templates are quite restrictive. There are only two slots provided (```?principal``` and ```?resource```) and they are limited to appearing in the scope of the policy. This results in users of Cedar needing to come up with their own [solution](https://github.com/cedar-policy/rfcs/pull/3#issuecomment-1632645305) to handling templates that can not be expressed in Cedar currently. In this RFC, we propose to generalize Cedar templates by allowing for an arbitrary number of user defined slots. User defined slots have different rules depending on whether or not they appear in the scope. If the user defined slot appears in the scope then it's type annotations are optional. Note that user defined slots that appear in the scope can only appear on the right-hand side of the ```==``` or ```in``` operators. This includes in operators when appearing together with an is operator, but excludes solitary is operators. User defined slots that appear in the scope can also be used in the condition as well. If the user defined slot appears in the condition of the template, then it must have it's type annotated and the type can be of any valid Cedar Schema Type including common types. 

In order to eliminate confusion, if using ```?principal``` and ```?resource``` slots they must be used exactly the same way as how they are being used currently. 

For users of Cedar who do not use a schmea, type annotations for generalized templates are optional. Templates will not be validated, but type checking will be performed during link-time. While this ensures that the provided values match the type of slot they are filling, it does not ensure that the policy won't experience a run-time type error.

## Basic example

### Example 1 

By allowing user defined slots that appear in the scope to also appear in the condition of the template, we are able to access attributes of that slot. In this example, this allows us to express the constraint that we can only access resources whose owner is the same as the owner of the entity that we instantiate for the ```?fs``` slot. 

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
  principal == ?person,
  action,
  resource in ?fs)
when {
    ?fs.owner == resource.owner 
};
```

### Example 2 

By allowing arbitrary user defined slots, we are able to express the following Cedar template. This example was taken directly from a user of Cedar in [#7](https://github.com/cedar-policy/rfcs/pull/7). 

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
    || (action == Action::"Navigate" && ?folder in resource)
};
```

### Example 3

Suppose that a company only wants to provide access to it's internal services only when the employee starts working. We can now use Generalized Cedar templates to define it as follows:

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

Suppose there are professors with dual appointments under two different departments who want to give students of their group access to both the resources in the first department and the resources in the second department. We can implement this template currently in Cedar by creating two seperate templates and instantiating them individually. The downside of this is that it would be up to the user of Cedar to ensure that they have made sure to instantiate both templates. Previously, [template groups](https://github.com/cedar-policy/rfcs/pull/7) was proposed as a solution to the problem mentioned above. However, with Generalized Cedar templates, we can solve this problem as follows: 

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

Cedar templates offer a way to change a group of policies overtime and to prevent against injection attacks that can occur when creating policies at runtime. However, there are policies that users of Cedar want to create at runtime that can't be expressed using templates today. By generalizing Cedar templates, we hope to allow for more users to be able to use templates while still balancing Cedar's core features: validation, analysis, and performance. 

While annotating the types of user defined slots inccurs some user burden, it allows us to express examples #2, #3, and #4 while still supporting validation and analysis. It also allows us to keep Cedar performant. With types, link time validation only requires checking that the supplied values have the same type as what is annotated, the alternative being running the type checker everytime you instantiate your template. Types also serve as a form of documentation that can help you remember what your templates are able to be linked against. 

## Detailed design

### Details 
We restrict the usage of ```?principal``` and ```?resource``` to the current implementation of templates in Cedar. Although, it would have been possible to allow for ```?principal``` and ```?resource``` to appear in the condition of the template, it can be confusing to distinguish between slots and variables. Therefore, only user defined slots that appear in the scope are allowed to be in the condition of the template. Note that just like in a typical programming language, nothing prevents you from coming up with confusing slot names, but ultimately this is up to the user's discretion. A template such as the following can be expressed: 

```
permit(principal == ?resources, action == Action::"Navigate", resource == ?principals)
```

User defined slots that appear in the scope of the template will only be allowed to link with entity types. User defined slots that appear only in the condition of the template will only be allowed to be linked with values, this corresponds with the ```RestrictedExpression``` type in ```cedar-policy-core```. 

For users that do not use a schema, there is no notion of common types as common types only appear when using a schema. 

### Implementation 

To allow for the arbitrary user defined slots, we will need to modify the parser, type checker, AST. The modfications needed for the typechecker will not be signficant. 

Below I provide a brief explanation of how Cedar's typechecker will work for user defined slots that appear in the scope: 

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

permit (principal == ?person, action == Action::"Navigate", resource in ?fs)  
when { 
  ?fs has storage && ?fs.storage == 5 
};
```

Cedar's typechecker works by enumerating all possible request environments for a particular action. For the action ```Navigate```, the possible ```principal``` and ```resource``` pairs would be ```(FS::Person, FS::Disk)```, ```(FS::Person, FS::Folder)```, ```(FS::Person, FS::Document)```. Under these individual request environments, we then generate the possible slot types for ```?person``` and ```?fs```. So far, this proceeds exactly as it would with Cedar templates currently, the only difference being a change in the slot names. 

| Request Environment | Principal Slot Types | Resource Slot Types
| -------- | ------- | ------- |
| ```(FS::Person, FS::Disk)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk``` | 
| ```(FS::Person, FS::Folder)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder``` | 
| ```(FS::Person, FS::Document)``` | ```?principal: FS::Person``` | ```?resource: FS::Disk```, ```?resource: FS::Folder```, ```?resource: FS::Document``` | 

Under each individual enumeration, we now check to see if these respective assignment of types to variables and user defined slots evaluates to a boolean. If every enumeration does, then our template passes the typechecker, otherwise it fails. With this extension, we would just need to ensure that for all enumerations, the condition of the policy also evaluates to a boolean. 

Since user defined slots that only appear in the condition of the template are required to have their types annotated, we do not need to perform this enumeration. Instead, now we use the type supplied by the user for the user defined slots and see if the template evaluates to a boolean type. 

### Users of Cedar that do not use a Schema

For users that do not use a schema, the user defined slots can be optionally annotated with types. If the types are annotated, generalized templates link time type checking will be performed. Here, it is up to the user to provide the correct types as without a schema. Note that even if types are supplied, there are no guarantees made about the runtime behavior of your program. Policies such as the following, where ```?bound1``` is provided a substitution of ```true``` will still be able to be expressed and an error will be thrown at runtime. The only guarantee provided when you do not use a schema is if you annotate a user defined slot with a type, the value you instatiate the slot with is of the type that you had supplied.

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

The proposed syntax for generalized templates looks as follows ```template(?bound1: type1, ?bound2: type2) =>``` and must come after all annotations. 
Each new user defined requires a distinct variable name. User defined slots in the scope must be unique. However, within the condition clause the same user defined slot can be used multiple times. The grammar of template annotations is as follows: 

```
Template := 'template' '(' ( TypeAnnotation { ',' TypeAnnotation } ) ')' '=>'

TypeAnnotation := ‘?’ IDENT ‘:’ Type

Type := Path | SetType | RecType
```

### What is allowed and not allowed?

1. Every slot in the condition of the template must have a type annotation
2. ```?action``` and ```?context``` are reserved names
3. Slots that appear in the scope can only be of Entity type
4. ```?principal``` and ```?resource``` can only be used as how they are currently 
5. All slot names must begin with ```?```
6. All slots within the template annotation (```template()```) must be used in the template 
5. ```?principal``` and ```?resource``` slots must appear in the scope

## Drawbacks

1. Type annotations for user defined slots can be a user burden.    

## Alternatives

### Performing type inference 
Type inference would work by coming up with the valid types of user defined slots that result in the templates to evaluating to a boolean. 

#### Pros:
Eliminates the user burden of providing type annotations

#### Downsides: 
1. It could result in analysis being overly general, since it would now have to consider all possible enumerations of the types of the slots that will allow for link time validation to succeed.
2. There would need to be some restrictions on how these slots can be used which can be unintuitive for users. (```?slot1 == ?slot2```)
3. It is possible that the inferred possible types is different from what the user expects.
4. The performance of the algorthim will be worse. 

### Moving type annotations to the Schema file 

#### Pros: 
By moving the type annotations to the Schema file, the notion of types can all be kept in one place. 

#### Downsides: 
1. We would not be able to have user defined slots per template since we do not have a way of referencing particular templates from the schema. Therefore, we would have to declare user defined slots globally for all templates. 
2. It may be confusing for users to need to define slots in the Schema file, as you would need to have foresight about what templates you want to design.
3. Link time type checking would not be able to be done for users that do not use schemas. 

## Unresolved questions

1. What should the syntax be for supplying aribtrary bound variables be. There was some discussion of it [here](https://github.com/cedar-policy/rfcs/pull/3#issuecomment-1611845728). Initial thoughts are to ensure that the user supplies a map so there is no confusion with regards to ordering. 

# Changelog since 6/2
## Letting users define slots in the scope if they are used in the same way as how ```?principal``` and ```?resource``` are used today. 
Pros: 
1. Allows for users to define more suggestive names rather than using ```?principal``` and ```?resource```. 
2. Gives a solution to the problem of confusing ```?principal``` and ```?resource``` when used in the condition of the template.  
3. Makes clearer the distinction between ```?principal``` and ```?resource``` vs. user defined slots. 
Cons:
1. It might be confusing why ```?principal``` and ```?resource``` aren't treated the same as user defined slots. 