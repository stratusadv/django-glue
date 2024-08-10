# Changelog for Django Glue

## 0.7.1
### Changes 
- glue_fetch refactored to be more extendable.
- glue_view uses glue_fetch with shortcut functions for both get and post requests.
  - glue view _render refactored to _fetch_view
- GlueView's will have to be refactored to use the new parameter passing. 
```js
    // Old Method
    view_card: new GlueView('{% url "view_card" %}?tacos=hello')
    view_card._render({'page': 2}, 'POST')
    
    // Refactored Method
    view_card: new GlueView('{% url "view_card" %}?tacos=hello')
    view_card.post({'page': 2})
    view_card.get({'page': 2})
```


## 0.7.0
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

```js
    let person = new GlueModelObject('person')
    await person.get()
    
    // Old Method
    person.fields.first_name  // Returns glue field data

    // Refactored Method
    person.glue_fields.first_name  // Returns glue field object

```

```html
    // Old Method
    {% include 'django_glue/form/glue_field/char_field.html' with glue_field='person.fields.first_name' x_model_value='person.first_name' %}
    {% include 'django_glue/form/glue_field/char_field.html' with glue_field='best_friend' x_model_value='best_friend.value' %}
    
    // Refactored Method
    {% include 'django_glue/form/glue_field/char_field.html' with glue_model_field='person.first_name' %}
    {% include 'django_glue/form/glue_field/char_field.html' with glue_field='best_friend' %}
```


## 0.6.3
### Features
- Glue Query Set entities now can return themselves as choices for a select field.
### Bugs
- Correct form key naming on relational model fields 


## 0.6.2
### Features
- Added a glue_fetch function for a quick an easy shortcut for making a fetch.



## 0.6.1
### Bugs
- Fixed the template tags for bootstrap and alpine
- Fixed bug with using UUID primary keys



## 0.6.0
### Changes
- System to build form field attributes from model fields. 
- HTML form fields (input, select, check radio).
- Glue js field objects bind to HTML form fields to set attributes and expose values.
- Ability to have full control over reactivity in forms in js that work with or without glue model objects.
 


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
