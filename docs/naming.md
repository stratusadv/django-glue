# Django Glue Naming Conventions

## Action
Used in: Template

Determines the type of action the glue tag is performing.

## Event
Used in: Template

Determines the type of event required for triggering.

## Fields
Used in: View, Template

Determines which fields you are making connections for or to.

#### Type
the type of field

#### Value
the value contained with in that field on that object.

## ID
Used in: Template

This is used to affect a specific object in templates and query handling.

## Access
Used in: View, Template

Determines the level of access the glue has to the given model object or query set.

#### View
Allows you to only read data from the targets.

#### Add
Allows you to read and create data in the targets.

#### Change
Allows you to read, create and change the data in the targets.

#### Delete
Allows you to manipulate the targets in any way possible.

## Method
Used in: View, Template

The action to be used on events or requests.

#### View
Allows you to only read data from the targets.

#### Create
Allows you to read and create data in the targets.

#### Update
Allows you to read, create and change the data in the targets.

#### Delete
Allows you to manipulate the targets in any way possible.

## Request
Used in: Views, Model

Used to control the requests and information required for django to operate..

## Response
Used in: Model

Sets the type of message that can be returned after a success event.

## Target
Used in: Model

the model object or query set being used in the glue.

#### Model Object

#### Query Set

## Connection
Used in: View, Template

Determines what category of connection is being used with glue

#### Model Object

#### Query Set

## Unique Name
Used in: View, Template

Used to identify this object throughout all layers of the view.
There can only be one instance of a unique name per view attached to either a model object or query set.
Unique names cannot be shared between model objects and query sets.

