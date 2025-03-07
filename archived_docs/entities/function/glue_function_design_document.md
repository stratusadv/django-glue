# Glue Model Object Design Document 
Last Updated: Wesley Howery 2024-06-29

# Overview
### Purpose of Component 
The Glue Request Handler is responsible for processing actions from Glue Entities. It provides a consistent and
extendable way to add and maintain processing glue entity requests from JS objects.

### Definitions, Acronyms and Abbreviations
- Handler - Handles the steps to receive, process and respond a Djagno Glue Request.    

### Reason To Change
The handler would change if we need to manipulate how we are processing data from the body or glue session.

## Actor Diagram
### Handler Processing  a Request
```mermaid
sequenceDiagram
    actor js_glue_entity as JS Glue Entity
    participant handler_view as Handler View
    participant handler_map as Handler Map
    participant request_handler as Request Handler
    participant glue_session_data as Glue Session Data
    participant glue_entity as Glue Entity
        
    js_glue_entity ->> handler_view: Post Request
    handler_view ->> handler_map: Finds Handler from Action Type 
    handler_map -->> handler_view: Handler Class
    handler_view ->> request_handler: Process Response Data
    request_handler ->> glue_session_data: Collects Session Data
    glue_session_data -->> request_handler: Entity Session Data
    request_handler ->> glue_entity: Constructs Entity
    glue_entity -->> request_handler: Glue Entity
    request_handler -->> handler_view: Response Data
    handler_view -->> js_glue_entity: Seralized Data
    
    
    
```

## Class Diagram
### Glue Request Handler
The Glue Request Handler is a stable abstract class that is inherited to provide action functionality on glue entities. 
- Inherit the Glue Request Handler to process new glue entities. 
- Add actions to inherited handlers to provide unique functionality. 
- **Handler Map** is responsible for returning the correct handler class based on connection and action. 
- Add connections and actions to maps that allows the glue to return the correct handler. 
- **Glue Body Data** defines what the handler expects from JS Objects to be able to correctly process the request. 

```mermaid
classDiagram
    direction LR
    namespace ActionComponent {
        class GlueAction { 
            Get
            Update Delete
        }
    }
    
    namespace GlueEntityComponent {
        class GlueModelObjectEntity { }
        class GlueQuerySetEntity { }
        class GlueFunctionEntity { }
        class GlueTemplateEntity { }
    }
    
    namespace HandlerComponent {
        class GlueRequestHandler {
            <<abstract>>
            Action 
            Session Data 
            Post Data
            process_response_data()
        }
        class ModelObjectRequestHandler { }
        class QuerySetObjectRequestHandler { }
        class FunctionObjectRequestHandler { }
        class TemplateObjectRequestHandler { }
     
        class GlueConnection {
            Model Object
            Query Set 
            Template
            Function
        }
        class HandlerMap { }
        class GlueBodyData { } 
    }
    
    GlueRequestHandler <-- ModelObjectRequestHandler :inherits
    GlueRequestHandler <-- QuerySetObjectRequestHandler :inherits
    GlueRequestHandler <-- FunctionObjectRequestHandler :inherits
    GlueRequestHandler <-- TemplateObjectRequestHandler :inherits
    HandlerMap --|> GlueConnection :uses
    HandlerMap --|> GlueRequestHandler :uses
    
    GlueRequestHandler --|> GlueBodyData :uses
    GlueRequestHandler --|> GlueAction :uses
    
    ModelObjectRequestHandler --|> GlueModelObjectEntity :uses
    QuerySetObjectRequestHandler --|> GlueQuerySetEntity :uses
    FunctionObjectRequestHandler --|> GlueFunctionEntity :uses
    TemplateObjectRequestHandler --|> GlueTemplateEntity :uses
    
```