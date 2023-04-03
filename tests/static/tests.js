function getDjangoGlueProcessedData() {
    return DJANGO_GLUE_PROCESSED_DATA
}

document.addEventListener('alpine:init', () => {
    let data = getDjangoGlueProcessedData()
    for (let key in data){
        Alpine.data(key, () => (data[key]))
    }
})