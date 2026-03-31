# Changelog for Django Glue

## v1.0.0-a1

### Breaking

- This version of Django Glue is not compatible with any past version. All public APIs have been updated and WILL require changes in your code. Details of the changes are listed below.

### Features

- 


### Changes + Migration

#### In Views

- There is now a central `Glue` class that provides access to all shortcuts and other relevant functionality.
  - It can be imported via `from django_glue import Glue` (instead of `import django as dg`)
  - Shortcut names have been changed:
    - `dg.glue_model_object` -> `Glue.model`  
    - `dg.glue_queryset` -> `Glue.queryset`
  - The kwarg for the object passed to each glue shortcut has been uniformly renamed to `target`

#### In Templates
- The installation process has been slightly changed.
  - The `{% glue_init %}` template tag has been renamed to `{% django_glue_init %}` to be slightly more descriptive.
- 

### Fixes


### Other Notes