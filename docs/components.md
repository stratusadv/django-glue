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

### Services -> Process and return the data
- Function
- Model Object
- Query Sets
- Template 
- Services 


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
- The object should be able to initialize itself depending on the session data. 
- The object can be passes to a handler that knows how to process it depending on what has been called.
- The handler would return a JSON Response to the template. 
- Objects would need a function that would be called by the handlers?
- Objects can convert themselves back to session data.
- Objects would have fields 
- Move handler into core and it is a base class. Each entity would have its own handler and would be able to process itself that way.

### Questions
- What do we actually need for the field data? On the JS side we want to be able to access the properties. 
This can all be done by the context on fields... Type and Value