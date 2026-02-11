class ModelObjectGlueFieldMeta {
    constructor(type, name, glue_field) {
        this.type = type
        this.name = name
        this.glue_field = glue_field
    }
}


class ModelObjectGlueField {
    constructor(name, value, meta) {
        this.name = name
        this.value = value
        this._meta = meta
    }
}