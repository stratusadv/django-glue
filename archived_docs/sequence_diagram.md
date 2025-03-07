```mermaid
sequenceDiagram
    participant View
    participant Session
    
    View->>Session: Glue's Model Object
    Session->>Session: Adds Data to Session
    Session -->>View: Returns Glue Data
```

