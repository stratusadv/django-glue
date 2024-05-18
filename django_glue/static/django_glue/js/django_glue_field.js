class GlueField {
    constructor(glue_field) {
        this.name = glue_field.name
        this.value = glue_field.value
        this.html_attrs = glue_field.html_attrs
        this.field_attrs = glue_field.field_attrs
    }

    set_label(element) {
        element.setAttribute('for', this.html_attrs.id)
        element.innerText = this.field_attrs.label

        if(this.html_attrs.required) {
            element.innerText = element.innerText + '*'
        }
    }

    set_html_attrs(element) {
        for (const [key, value] of Object.entries(this.html_attrs)) {
            element.setAttribute(key, value)
        }
    }
}


class GlueSelectField extends GlueField {
    set_html_attr() {}
}


document.addEventListener('alpine:init', () => {
    Alpine.data('alpineGlueField', () => ({
        init() {
            this.$watch('glue_field', value => {
                let glueField = new GlueField(value)
                glueField.set_label(this.$refs.label)
                glueField.set_html_attrs(this.$refs.field)
            })
        },
        glue_field: null
    }));
});
