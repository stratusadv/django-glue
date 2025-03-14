### Glue-able Components
- Model Object
- Queryset 
- Function 
- Template

### Configuration 
- Django Glue Settings
- settings.py
- context_processor.py -> Change function name? 

### Processing Glue
- Glue Request Handler -> Processes the response depending on the Glue Connection Type. Use a map
- Glue Session - > Builds glue object from session. -> This should pass the session not he request variable?
- Glue Body Data -> Data & a glue action. This could be more structured. It is being used a lot.
- Glue Context Data -> Connection, Access, Fields & Methods. Seems like this is data related to the Glue Call
- Glue Meta Data -> Meta Data - Extra data about the glue call. Is this being used anywhere?
- Glue Model Field Data
- Glue JSON Data -> Used to provide a consistent structure for our glue objects. I dont like this naming. 
- Glue Json Response Data -> Provides the actual json response 
- Glue Middleware -> Updates the session on click.

### Keep Live
- Glue Keep Live Session

### Enums
- Glue Access
- Glue Action 
- Glue Connection 
- Glue Json Response Type
- Glue Json Response Status


## Processes
- User Adds Glue in View
  - Updates the session data. Session data needs to store what?
- Initializes glue in template.
  - Glue js objects new how to handle and create themselves. 
  - Access to functionally in js
- Glue front end makes requests to backend. Back end needs to know how to initialize itself and perform functions depending on type.
- Glue Keep Live to update the session expiry

Main components would be Session Updating, JS Objects, Request, Processing, Response.

### Changes
- Glue model objects and glue querysets need to use the same post data.

### Questions
- What do we actually need for the field data? On the JS side we want to be able to access the properties. 
This can all be done by the context on fields... Type and Value

### Fields 
- html_attr -> Information that needs to be sent to the frontend to validate and configure fields.
- Field Type ->  Matches django model fields. 

### Field Types
- Option Field 