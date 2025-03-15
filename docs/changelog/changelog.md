# Changelog for Django Glue

## v0.8.0

### Breaking

- Refactored `glue_model` function to `glue_model_object` to be more clear on the functionality.

### Features

- Added initial documentation for the project, check it out at (https://django-glue.stratusadv.com).

### Changes

- Project internals have been completely refactored to improve project maintainability.
- New recommended way of using glue is to `import django_glue as dg` which won't work with current implementations.
	- Usage changes from `glue_model_object` to `dg.glue_model_object`.
- Testing has been completely refactored to match the new project layout.

### Fixes

- Corrected & updated all the testing functionality for this project.

## v0.7.10

### Bugs

- Fix select_field.html and search_and_select_field.html to watch for choices to be loaded, which will allow us to display the selected option correctly.

## v0.7.9

### Bugs

- Fix CSS of the search_and_select_field to be less jarring when focus is shifted from the button to the search input
  field.
- Add a watcher to the select_field and search_and_select_field so the value can be changed/displayed
  dynamically/programatically.

### Changes

- Use $nextTick to decide when to focus on search, instead of using setTimeout.

## v0.7.8

### Bugs

- The use of x-trap, focus_input() and click.outside seem to cause issues when the user is on mobile, and a keyboard is
  present.
- On mobile, the search input field is not focused upon opening the dropdown.

## v0.7.7

### Bugs

- Simplify how multi-select field binds value & choices.
- X-effect to parse value into proper array and bind to hidden input field.
- Close missing div on select field.

## v0.7.6

### Changes

- Blocks to extend / override select choice items.
- Glue custom css file to look nice out of the box.

## v0.7.5

### Bug Fix

- Dynamic Glue Field Indexing

## v0.7.4

### Features

- Multi-Select Field

## v0.7.3

### Features

- Search & Select Field
- Alpine focus added into alpine js requirements and init for field keyboard shortcuts.
- Glue Field Error Messages
    - Glue fields show html validation errors by default.
    - Will have to update how errors disappear and improve error functionality in the future.

### Changes

- Updated select to use alpine js dropdown for consistency between search and the search & select fields.
- Glue field factory updated to use setters and getters for specific attribute methods.
- When select fields are not required, it automatically adds a '----------' option.

## v0.7.2

### Bugs

- Added endpoint to retrieve glue session data.
- JS function to retrieve glue session data to update window variable and keep live.
- Gluing Templates and Views now fetches and updates the session data to initialize glue objects properly.

## v0.7.1

### Changes

- glue_fetch refactored to be more extendable.
- glue_view uses glue_fetch with shortcut functions for both get and post requests.
    - glue view _render refactored to _fetch_view
- GlueView's will have to be refactored to use the new parameter passing and methods.

## v0.7.0

### Changes

- Extra data used for glue configuration has moved to _meta on objects.
    - Shortcuts have been written for glue functionality to access metadata.
- JS files have been refactored to match python directory structure.
- Attr factories refactored into specific directory.
- Glue form field entity and js objects to match backend entities.
- Glue form fields require base information that surround the field and attrs are now specific to field attrs.
- Removed binder js and constructed fields with alpine js.
- Enhanced how glue form fields and glue model fields pass data to templates.
- Factories to create all objects.
- Simplified how glue form fields can be constructed.

## v0.6.3

### Features

- Glue Query Set entities now can return themselves as choices for a select field.

### Bugs

- Correct form key naming on relational model fields

## v0.6.2

### Features

- Added a glue_fetch function for a quick an easy shortcut for making a fetch.

## v0.6.1

### Bugs

- Fixed the template tags for bootstrap and alpine
- Fixed bug with using UUID primary keys

## v0.6.0

### Changes

- System to build form field attributes from model fields.
- HTML form fields (input, select, check radio).
- Glue js field objects bind to HTML form fields to set attributes and expose values.
- Ability to have full control over reactivity in forms in js that work with or without glue model objects.

## v0.5.3

### Changes

- Created an extendable structure using glue entities as the base objects.
- Removed meta and context keys from session data.
- Handler map based on action called from glue js objects to process response.
- Dataclass structure for Response, Session and Post data.

### Bugs

- Corrected issue on glue views that glue models. Encoded unique name is based on path the user requests the view from.

## v0.5.2.3

### Changes

- Glue model object returns a null object if we try to find a id that does not exist.
- Updated html attributes on glue model objects and added attributes to js model objects.

## v0.5.2.2

### Changes

- Render functions on the GlueView object now await the response

## v0.5.2.1

### Bugs

- Fixed issue with templates and function not being added properly to th keep live session.

## v0.5.2.0

### Changes

- Internal Unique Name now allows for unique names to be duplicated in separate views but must remain unique in the same
  view.
- Added keep live reload warning if keep live pulse fails

### Bugs

- Fixed glued functions having invalid comparison and did not work unless unique name matched function name.

## v0.5.1.0

### Features

- Can now glue functions using glue_function function.

### Changes

- Added front end error handling for ajax requests.

## v0.5.0.0

### Changes

- Remove Add because of foreign key and key complications for security.
- Separate add_glue function into multiple functions (glue_view, glue_model etc).
