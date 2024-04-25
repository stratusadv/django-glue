# Changelog for Django Glue


## 0.5.3
### Changes
- Created an extendable structure using glue entities as the base objects.
- Removed meta and context keys from session data. 
- Handler map based on action called from glue js objects to process response.
- Dataclass structure for Response, Session and Post data. 

### Bugs
- Corrected issue on glue views that glue models. Encoded unique name is based on path the user requests the view from. 
 


## 0.5.2.3
### Changes
- Glue model object returns a null object if we try to find a id that does not exist.
- Updated html attributes on glue model objects and added attributes to js model objects. 


## 0.5.2.2

### Changes
- Render functions on the GlueView object now await the response

## 0.5.2.1

### Bugs
- Fixed issue with templates and function not being added properly to th keep live session.

## 0.5.2.0

### Changes
- Internal Unique Name now allows for unique names to be duplicated in separate views but must remain unique in the same view.
- Added keep live reload warning if keep live pulse fails

### Bugs
- Fixed glued functions having invalid comparison and did not work unless unique name matched function name.


## 0.5.1.0

### Features
- Can now glue functions using glue_function function.

### Changes
- Added front end error handling for ajax requests.


## 0.5.0.0

### Changes
- Remove Add because of foreign key and key complications for security.
- Separate add_glue function into multiple functions (glue_view, glue_model etc).

## 0.4.2.5

### Changes
- Change to POST Requests for all ajax calls. 


## 0.4.2.4

### Changes
- Versions fix. 


## 0.4.2.3

### Changes
- Improve field logic for many-to-many and one-to-one relationships. 

## 0.4.2.2

### Changes
- Foreign Key fields now work with glue.
- Move validation logic from Glue Request Handler to View.  

## 0.4.2.1

### Changes
- Model default values now work with glue.

## 0.4.2

### Changes
- Context data to construct model object fields in js
- Session data updated inside of keep live ajax
- Cleaning js functions (more needed)

## 0.4.1

#### Features
- Event system implement for responses.

#### Changes
- Keep live system update to work with template and view loading.
- Context removed from Javascript

## 0.4.0

#### Features
- You can now glue templates by submitting a full template path as a string to add_glue function call.
- You can now use the experimental load views in your templates with GlueView.

#### Changes
- All validation moved to server side.
- Base level of benchmarks complete test at roughly 1ms to run add_glue function.

## 0.3.0

#### Features
- You can now glue django model methods (this works on both model objects and query sets).
- Now works with all javascript not just alpine.

#### Changes
- Clean up internal functions to more efficient and secure.
- Remove Alpine.js and return to vanilla so that people can use their own libraries.
- Complete overhaul of the server side and front end code.

## 0.2.6

#### Bugs
- Fixed issue with building context dictionaries on non glue views.

## 0.2.5

#### Bugs
- Fixed issue with overwriting unique_names

## 0.2.4

#### Bugs
- Fixed a session data saving issues to make sure when using new keep life it saves all session data.

## 0.2.3

#### Features
- Can handle multiple tabs or webpages open at the same time.

## 0.2.2

#### Changes
- Removed css files for old messaging system.
- Added glue_init_core to allow people to include their own alpine and axios files.

## 0.2.1

#### Changes
- Updated middleware to use settings glue name.

#### Bugs
- Fixed context processor key error.
- Fixed templates and static package error.
