# Django Glue Naming Conventions

## Connect

Used in: Template

What type of connection the glue is making on the template end.

## Field

Used in: View, Template

Determines which field you are making connections for or to.

#### Type

#### Value

## ID

Used in: Template

This is used to affect a specific object in templates and query handling.

## Input

Used in: Template

This controls how the glue connects back to the model object or query set.

#### Live

#### Form

## Method

Used in: View, Template

Determines the level of access the glue has to the given model object or query set.

#### View

#### Create

#### Update

#### Delete

## Response

Used in: Model

Sets the type of message that can be returned after a success event.

## Target

Used in: Model

the model object or query set being used in the glue.

#### Model Object

#### Query Set

## Type

Used in: View, Template

Determines what type of connection is being used with glue

#### Model Object

#### Query Set

## Unique Name

Used in: View, Template

Used to identify this object throughout all layers of the view.
There can only be one instance of a unique name per view attached to either a model object or query set.
Unique names cannot be shared between model objects and query sets.

