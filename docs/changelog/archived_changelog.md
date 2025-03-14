# Archived Changelog

## v0.4.2.5

### Changes
- Change to POST Requests for all ajax calls. 


## v0.4.2.4

### Changes
- Versions fix. 


## v0.4.2.3

### Changes
- Improve field logic for many-to-many and one-to-one relationships. 

## v0.4.2.2

### Changes
- Foreign Key fields now work with glue.
- Move validation logic from Glue Request Handler to View.  

## v0.4.2.1

### Changes
- Model default values now work with glue.

## v0.4.2

### Changes
- Context data to construct model object fields in js
- Session data updated inside of keep live ajax
- Cleaning js functions (more needed)

## v0.4.1

#### Features
- Event system implement for responses.

#### Changes
- Keep live system update to work with template and view loading.
- Context removed from Javascript

## v0.4.0

#### Features
- You can now glue templates by submitting a full template path as a string to add_glue function call.
- You can now use the experimental load views in your templates with GlueView.

#### Changes
- All validation moved to server side.
- Base level of benchmarks complete test at roughly 1ms to run add_glue function.

## v0.3.0

#### Features
- You can now glue django model methods (this works on both model objects and query sets).
- Now works with all javascript not just alpine.

#### Changes
- Clean up internal functions to more efficient and secure.
- Remove Alpine.js and return to vanilla so that people can use their own libraries.
- Complete overhaul of the server side and front end code.

## v0.2.6

#### Bugs
- Fixed issue with building context dictionaries on non glue views.

## v0.2.5

#### Bugs
- Fixed issue with overwriting unique_names

## v0.2.4

#### Bugs
- Fixed a session data saving issues to make sure when using new keep life it saves all session data.

## v0.2.3

#### Features
- Can handle multiple tabs or webpages open at the same time.

## v0.2.2

#### Changes
- Removed css files for old messaging system.
- Added glue_init_core to allow people to include their own alpine and axios files.

## v0.2.1

#### Changes
- Updated middleware to use settings glue name.

#### Bugs
- Fixed context processor key error.
- Fixed templates and static package error.