# Borrowed generic input (entities and context)

## Related issues and PRs

- Reference Issues:
  - It provides an alternative foundation to https://github.com/cedar-policy/rfcs/pull/72, https://github.com/cedar-policy/cedar/issues/986
  - It provides a potentially better way of achieveing https://github.com/cedar-policy/cedar/issues/1066
- Implementation PR(s):

## Timeline

- Started: 2024-12-26
- Accepted: TBD
- Stabilized: TBD

## Summary

- Declare some traits like `AsSet`, `AsRecord` and `AsEntity`
- If an user-provided type implements the trait, the evaluator can view it as a value or an entity, without needing to convert it upfront into an owned cedar_policy::Entity
- Provide a version of `Entities` that is generic over some `E: AsEntity`
- If macros for converting to entities are ever stabilized, they should derive these traits, not `Into<Entity>`

## Basic example

```rust
    impl<'entity> AsEntity<'entity> for User {
        type EI = Never;
        type S = &'entity HashSet<TeamUid>;
        type R = Never;

        fn attr(
            &'entity self,
            attr: &str,
        ) -> Option<BorrowedValue<'entity, Self::EI, Self::S, Self::R>> {
            match attr {
                "joblevel" => Some(BorrowedValue::Long(self.joblevel)),
                "location" => Some(BorrowedValue::String(&self.location)),
                "parents" => Some(BorrowedValue::Set(&self.parents)),
                _ => None,
            }
        }
    }
```

## Motivation

Currently, the `Entities` type used to pass a collection of entities to the authorizer stores owned entities in a concrete structure of cedar's own structs and enums (such as `Entity` and `RestrictedExpression`).

If the user has certain type `T` which represents an entity in the domain of the application, the recommended way seems to be, based on this code example in [tiny-todo]
(https://github.com/cedar-policy/cedar-examples/blob/5a29a3899aed8cecaabebc504ce1ab30a23aaaec/tinytodo/src/objects.rs#L86)
to implement `From<T> for Entity`, eg:

```rust
impl From<User> for Entity {
    fn from(value: User) -> Entity {
        let attrs = [
            ("joblevel", RestrictedExpression::new_long(value.joblevel)),
            ("location", RestrictedExpression::new_string(value.location)),
        ]
        .into_iter()
        .map(|(x, v)| (x.into(), v))
        .collect();

        let euid: EntityUid = value.euid.into();
        Entity::new(
            euid.into(),
            attrs,
            value.parents.into_iter().map(|euid| euid.into()).collect(),
        )
        .unwrap()
    }
}
```

This is essentially boilerplate, that was already proposed to be macro-generated: https://github.com/cedar-policy/cedar/issues/986

However, it also has a performance cost:

The `User` struct in the example already aggregates all the relevant attributes (the id, joblevel, location and parents of the user), but we are forced to perform a bunch of new allocations to get the data into the format Cedar expects, constructing SmolStr-s, a hashmap and a hashset.

Depending on the policies, the evaluator might not even request some of the attributes, yet we are eagerly constructing the full entity.

## Detailed design

Since sets and records can contain values, which again can contain sets and records, one option is to end up with a lot of associated types like these:

```rust
pub trait AsRecord<'entity> {
    type EI: AsEntityUID;
    type S: AsSet<'entity>;
    type R: AsRecord<'entity>;
    fn attr(
        &'entity self,
        attr: &str,
    ) -> Option<BorrowedValue<'entity, Self::EI, Self::S, Self::R>>;
}

pub trait AsSet<'entity> {
    type EI: AsEntityUID;
    type S: AsSet<'entity>;
    type R: AsRecord<'entity>;
    fn iterate(
        &self,
    ) -> Box<dyn Iterator<Item = BorrowedValue<'entity, Self::EI, Self::S, Self::R>> + 'entity>;

    // And probably other methods for containment checking, etc
}

pub trait AsEntityUID {
    /// The type of the entity.
    fn entity_type(&self) -> &EntityType;
    fn entity_id(&self) -> &str;
}

#[derive(Debug, PartialEq, Eq)]
pub enum BorrowedValue<'entity, EI, S, R> {
    Bool(bool),
    Long(Integer),
    String(&'entity str),
    EntityUID(&'entity EI),
    Record(R),
    Set(S),
    // We ignore residuals and extension values for now
}

pub trait AsEntity<'entity> {
    type EI: AsEntityUID;
    type S: AsSet<'entity>;
    type R: AsRecord<'entity>;
    fn attr(
        &'entity self,
        attr: &str,
    ) -> Option<BorrowedValue<'entity, Self::EI, Self::S, Self::R>>;

    // And other methods to get tags and parents
}
```

This set of traits can be implemented for the normal ast::Entity:

```rust
type Record = Arc<BTreeMap<SmolStr, Value>>;

impl<'entity> AsEntity<'entity> for Entity {
    fn attr(
        &'entity self,
        attr: &str,
    ) -> Option<BorrowedValue<'entity, Self::EI, Self::S, Self::R>> {
        self.get(attr).and_then(|v| match v {
            PartialValue::Value(value) => value_to_borrowed_value(value),
            PartialValue::Residual(_) => None,
        })
    }

    type EI = EntityUID;

    type S = &'entity Set;

    type R = &'entity Record;
}

impl<'entity> AsSet<'entity> for &'entity Set {
    type EI = EntityUID;
    type S = &'entity Set;
    type R = &'entity Record;

    fn iterate(
        &self,
    ) -> Box<dyn Iterator<Item = BorrowedValue<'entity, Self::EI, Self::S, Self::R>> + 'entity>
    {
        Box::new(
            self.authoritative
                .iter()
                .filter_map(value_to_borrowed_value),
        )
    }
}

impl<'entity> AsRecord<'entity> for &'entity Record {
    fn attr(
        &'entity self,
        attr: &str,
    ) -> Option<BorrowedValue<'entity, Self::EI, Self::S, Self::R>> {
        self.get(attr).and_then(value_to_borrowed_value)
    }

    type EI = EntityUID;

    type S = &'entity Set;

    type R = &'entity Record;
}

impl AsEntityUID for EntityUID {
    fn entity_type(&self) -> &EntityType {
        self.entity_type()
    }

    fn entity_id(&self) -> &str {
        self.eid().as_ref()
    }
}

fn value_to_borrowed_value(value: &Value) -> Option<BorrowedValue<'_, EntityUID, &Set, &Record>> {
    match value.value_kind() {
        ValueKind::Lit(Literal::Bool(bool)) => Some(BorrowedValue::Bool(*bool)),
        ValueKind::Lit(Literal::Long(long)) => Some(BorrowedValue::Long(*long)),
        ValueKind::Lit(Literal::String(string)) => Some(BorrowedValue::String(string)),
        ValueKind::Lit(Literal::EntityUID(entity_uid)) => {
            Some(BorrowedValue::EntityUID(entity_uid.as_ref()))
        }
        ValueKind::Set(set) => Some(BorrowedValue::Set(set)),
        ValueKind::Record(btree_map) => Some(BorrowedValue::Record(btree_map)),
        ValueKind::ExtensionValue(_) => None,
    }
}
```

An application that already uses some rust structs to represents domain entities could make use of them like this (most of this could also one day be generated by macro):

```rust
    /// A handcrafted never type (the real one is unstable).
    #[derive(Debug, PartialEq, Eq)]
    pub enum Never {}

    impl<'entity> AsSet<'entity> for Never {
        type EI = Never;
        type S = Never;
        type R = Never;

        fn iterate(
            &self,
        ) -> Box<dyn Iterator<Item = BorrowedValue<'entity, Self::EI, Self::S, Self::R>> + 'entity>
        {
            unimplemented!()
        }
    }

    impl AsEntityUID for Never {
        fn entity_type(&self) -> &EntityType {
            unimplemented!()
        }

        fn entity_id(&self) -> &str {
            unimplemented!()
        }
    }

    impl AsRecord<'_> for Never {
        type EI = Never;
        type S = Never;
        type R = Never;

        fn attr(&self, _: &str) -> Option<BorrowedValue<'_, Self::EI, Self::S, Self::R>> {
            unimplemented!()
        }
    }

        #[derive(Debug, Clone)]
        pub struct User {
            joblevel: i64,
            location: String,
            parents: HashSet<TeamUid>,
        }

        #[derive(Debug, Clone, PartialEq, Eq, Hash)]
        pub struct TeamUid(String);

        #[derive(Debug, Clone)]
        pub struct Team {
            parents: HashSet<TeamUid>,
        }

        use lazy_static::lazy_static;

        lazy_static! {
            static ref USER_TYPE: EntityType = EntityType::from_normalized_str("User").unwrap();
            static ref TEAM_TYPE: EntityType = EntityType::from_normalized_str("Team").unwrap();
        }

        impl<'entity> AsEntity<'entity> for User {
            type EI = Never;
            type S = &'entity HashSet<TeamUid>;
            type R = Never;

            fn attr(
                &'entity self,
                attr: &str,
            ) -> Option<BorrowedValue<'entity, Self::EI, Self::S, Self::R>> {
                match attr {
                    "joblevel" => Some(BorrowedValue::Long(self.joblevel)),
                    "location" => Some(BorrowedValue::String(&self.location)),
                    "parents" => Some(BorrowedValue::Set(&self.parents)),
                    _ => None,
                }
            }
        }

        impl AsEntityUID for TeamUid {
            fn entity_type(&self) -> &EntityType {
                &TEAM_TYPE
            }

            fn entity_id(&self) -> &str {
                self.0.as_str()
            }
        }

        impl<'entity> AsEntity<'entity> for Team {
            type EI = Never;
            type S = &'entity HashSet<TeamUid>;
            type R = Never;

            fn attr(
                &'entity self,
                attr: &str,
            ) -> Option<BorrowedValue<'entity, Self::EI, Self::S, Self::R>> {
                match attr {
                    "parents" => Some(BorrowedValue::Set(&self.parents)),
                    _ => None,
                }
            }
        }

        impl<'entity> AsSet<'entity> for &'entity HashSet<TeamUid> {
            type EI = TeamUid;

            type S = Never;

            type R = Never;

            fn iterate(
                &self,
            ) -> Box<
                dyn Iterator<Item = BorrowedValue<'entity, Self::EI, Self::S, Self::R>> + 'entity,
            > {
                Box::new(self.iter().map(BorrowedValue::EntityUID))
            }
        }

        enum DomainEntity {
            User(User),
            Team(Team),
        }

        impl<'entity> AsEntity<'entity> for DomainEntity {
            type EI = Never;
            type S = &'entity HashSet<TeamUid>;
            type R = Never;

            fn attr(
                &'entity self,
                attr: &str,
            ) -> Option<BorrowedValue<'entity, Self::EI, Self::S, Self::R>> {
                match self {
                    DomainEntity::User(user) => user.attr(attr),
                    DomainEntity::Team(team) => team.attr(attr),
                }
            }
        }

        #[test]
        fn test() {
            let entity = DomainEntity::User(User {
                joblevel: 1,
                location: "here".to_string(),
                parents: HashSet::from_iter([TeamUid("team1".to_string())]),
            });

            assert_eq!(entity.attr("joblevel"), Some(BorrowedValue::Long(1)));

            let team_type: &EntityType = &*TEAM_TYPE;

            assert_eq!(
                entity
                    .attr("parents")
                    .into_iter()
                    .filter_map(|set| match set {
                        BorrowedValue::Set(set) => Some(set),
                        _ => None,
                    })
                    .flat_map(|set| set.iterate())
                    .next()
                    .and_then(|v| match v {
                        BorrowedValue::EntityUID(id) => Some(id.entity_type()),
                        _ => None,
                    }),
                Some(team_type)
            );
        }
```

In this setup, they (or the derive macro on their behalf) has to create one enum each for containing all record types, entity types and set types used in the project.

There could be an alterative formulation, where we use dynamic dispatch instead:

```rust
trait DynEntity {
    fn attr<'entity>(&'entity self, attr: &str) -> BorrowedValue<'entity, &'entity dyn AsEntityUID, &'entity dyn DynSet, &'entity dyn DynRecord>;
}
```

## Drawbacks

This is a non-breaking change, the new APIs are strictly additional to the existing APIs, with no change to the semantics of Cedar itself.

However, to fully realize the benefits performance-wise, a significant part of the core authorizer code would need to be rewritten to be generic over the concrete type of entities. This is both non-trivial effort, and could lead to introduction of bugs, or lead to two separate copies of the code, one for the owned internal types, and one generic one.

There is also a cognitive cost to the user that there would be now two distinct ways of accepting input.

Unfortunately, in certain cases this approach can also worsen performance:

- Currently cedar has a highly specialized Set representation, with a separate 'authoritative' and 'fast' representations. If instead we would need to be using some generic traits, that can be backed by
    many concrete representations, some of these optimizations could be lost.

- More generics usually means larger code size.

- Wrapping references to parts of an owned value is comparatively cheap, but certainly not free, eg these have to do some work, comparing and 
rearranging enum discriminants:

```rust
fn value_to_borrowed_value(value: &Value) -> Option<BorrowedValue<'_, EntityUID, &Set, &Record>> {
    match value.value_kind() {
        ValueKind::Lit(Literal::Bool(bool)) => Some(BorrowedValue::Bool(*bool)),
        ValueKind::Lit(Literal::Long(long)) => Some(BorrowedValue::Long(*long)),
        ValueKind::Lit(Literal::String(string)) => Some(BorrowedValue::String(string)),
        ValueKind::Lit(Literal::EntityUID(entity_uid)) => {
            Some(BorrowedValue::EntityUID(entity_uid.as_ref()))
        }
        ValueKind::Set(set) => Some(BorrowedValue::Set(set)),
        ValueKind::Record(btree_map) => Some(BorrowedValue::Record(btree_map)),
        ValueKind::ExtensionValue(_) => None,
    }
}

match attr {
    "joblevel" => Some(BorrowedValue::Long(self.joblevel)),
    "location" => Some(BorrowedValue::String(&self.location)),
    "parents" => Some(BorrowedValue::Set(&self.parents)),
    _ => None,
}
```

If we want to evaluate thousands of policies in a PolicySet over just a few entities, it might actually be worth it to 
allocate the owned entity representation once, as it is currenly done, instead of repeating the little reference conversions thousands of times. 
Ultimately only benchmarking can determine what, if any, real gains this approach can provide.

## Alternatives

We can keep just the current way of constructing entities, which has some convenience and performance costs, but it does work.

## Unresolved questions

To know exactly what traits and methods we need, one has to have a deep understanding of how the evaluator inspects entities.
Since the proposer doesn't yet have such a deep understanding, all of the specific declarations are subject to change.
