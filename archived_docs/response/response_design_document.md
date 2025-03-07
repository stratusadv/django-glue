# Response Design Document 
Last Updated: Wesley Howery 2024-06-29

# Overview
### Purpose of Component 
Responses provide a consistent structure that returns data to the glue ajax call.  

### Definitions, Acronyms and Abbreviations
- Serialize - Processes python response data into JSON objects expected by our front end.     

### Reason To Change
To provide more response choices. 

## Actor Diagram
### Handler Returning a Response
```mermaid
sequenceDiagram
    actor js_glue_entity as JS Glue Entity
    participant handler_view as Handler View
    participant handler_map as Handler Map
    participant request_handler as Request Handler
    participant entity_response_data as Entity Response Data
    participant glue_json_response as Glue Json Response
    
    js_glue_entity ->> handler_view: Submits Request
    handler_view ->> handler_map: Finds Handler from Action Type 
    handler_map -->> handler_view: Handler Class
    handler_view ->> request_handler: Calls Action
    request_handler ->> entity_response_data: Performs Action
    entity_response_data -->> request_handler: Assembled Data
    request_handler -->> glue_json_response: Assemble Data to Json Response
    glue_json_response -->> request_handler: Formatted Response
    request_handler -->> handler_view: Formatted Response
    handler_view -->> js_glue_entity: Formatted Response
```

## Class Diagram
### Responses 
- **Response Types** and **Statuses** provide consistent options for our front end to be able to process a response. 
- **Json Response Data** is a consistent structure to return response data and messages. Each request responds with the same format. 
- **Glue Json Data** is a stable class used for inheritance. It allows our entities to define how they will structure the 
response data from the action called. 
- Glue request handlers returns Json Response Data. Inside of that response, data is formatted according to the entity's Glue Json Data.

```mermaid
classDiagram
    direction BT
    
    class GlueJsonData { 
        <<abstract>>
        to_dict()
        to_json()
    }
    
    class GlueJsonResponseData { 
        Message Title
        Message Body
        Data: GlueJsonData
        Optional Message Data
        Response Type
        Response Status
    }
    
    class GlueJsonResponseType {
        <<enumeration>>
        SUCCESS
        INFO
        WARNING
        ERROR
        DEBUG
    }
    
    class GlueJsonResponseStatus {
        <<enumeration>>
        Success: 200
        Silent Success: 204
        Error: 404
    }
    
    class GlueRequestHandler { 
        process_response_data()
    }
    class GlueEntityActionJsonData { }
    
    GlueJsonResponseData --|> GlueJsonData :implements
    GlueJsonResponseData --|> GlueJsonResponseStatus :implements
    GlueJsonResponseData --|> GlueJsonResponseType :implements
    GlueRequestHandler --|> GlueJsonResponseData :returns
    GlueEntityActionJsonData --> GlueJsonData :inherits
```

## Improvements
- Naming could be improved?
- Serialization needs to be more consistent.
  - Create serialization app. This interface should be used in one location. It is currently spread throughout the app.