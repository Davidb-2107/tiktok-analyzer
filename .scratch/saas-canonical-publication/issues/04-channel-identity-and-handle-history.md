# Decide channel identity and handle history

Status: open
Type: grilling
Blocked by: none (01 resolved)

## Question

How is the durable `channel_id` issued at publication, and how does it relate
to mutable channel handles over time?

The decision must define whether the ID is a slug or opaque value, who assigns
it, its collision scope, when it becomes immutable, how handle renames and
historical provenance are represented, and how existing sub-formula IDs,
channel-scoped artifact names, and `(project_id, channel_id, subformula_id)`
uniqueness behave during migration. A handle-derived ID may be convenient at
creation, but a later rename must not change identity or published references.
