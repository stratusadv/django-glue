// loaded automatically and is constructed from the context data?

window.document.dg = DjangoGlueInit()

let Glue = window.document.dg

// using in Javascript File

let first_name = Glue.the_unique_name.first_name
// Lazy loads the object on the first_name attribute access

// Using in a function


