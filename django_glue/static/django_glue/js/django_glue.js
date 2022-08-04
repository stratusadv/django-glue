document.addEventListener('alpine:init', () => {
    Alpine.store('glue', DJANGO_GLUE_DATA)
})

console.log(DJANGO_GLUE_DATA)