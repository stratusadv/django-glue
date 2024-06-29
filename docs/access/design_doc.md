# Access Design Document 
Last Updated: Wesley Howery 2024-06-29

# Overview
### Purpose of Component 
Access provides controls to be able to regulate who has privileges to manipulate entities.  

### Definitions, Acronyms and Abbreviations
- View - Only can view the data. 
- Change - Ability to manipulate the data on the object and in the database.
- Delete - Can delete objects inside of the database.

### Reason To Change
If we need to provide more granular or special access to entities this component would have to change. 

## Actor Diagram
### Handler Checking Access
```mermaid
sequenceDiagram
    actor js_glue_entity as JS Glue Entity
    participant request_handler as Request Handler
    participant access as Access
    js_glue_entity ->> request_handler: Submits Request
    request_handler ->> access: Access Check Decorator
    access -->> request_handler: Has Access 
    request_handler -->> js_glue_entity: Serialized Response Data
    access -->> request_handler: Access Denied
    request_handler -->> js_glue_entity: 404 Error
```

## Class Diagram
### Access
- The Glue Request Handler assembles the session data and check to see if the access provided in the session data matches
the access required on the action in the handler.
- Access is provided to the Glue JS Object through gluing in the view. This allows us to control the access level on the server side.  
```python
def task_form_view(request, pk):
    task = get_object_or_404(Task, pk=pk)
    glue_model(request, 'task', task, 'change') # Adds glue object to session data with access provided. 
```
```mermaid
classDiagram
    direction TB
    
    
    class GlueSessionData {
        Access
    }
    
    class GlueRequestHandler {
        Action
    }
    
    namespace GlueActionComponent {
        class GlueAccess {
            <<enumeration>>
            View
            Change
            Delete
            has_access()
        }
        class GlueAction { 
            <<abstract>>
            Get
            Update
            ...
            required_access()
        }
    }
    
    GlueRequestHandler --|> GlueSessionData
    GlueRequestHandler --|> GlueAccess
    GlueRequestHandler --|> GlueAction
```

### Check Access Decorator
Check access decorator lives on all handler process_response_data methods. It uses the action on the method to check if
the glue session data has the correct access level to perform the request. 
```python
class GetGlueModelObjectHandler(GlueRequestHandler):
    action = GlueModelObjectAction.GET
    _session_data_class = GlueModelObjectSessionData

    @check_access
    def process_response_data(self) -> GlueJsonResponseData:
        glue_model_object = glue_model_object_from_glue_session(self.session_data)
        return generate_json_200_response_data(
            message_title='Success',
            message_body='Successfully retrieved model object!',
            data=GlueModelObjectJsonData(glue_model_object.fields)
    )
```