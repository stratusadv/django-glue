class GlueField {
    constructor(glue_field) {
        this.name = glue_field.name
        this.value = glue_field.value
        this.field_attrs = glue_field.field_attrs
    }

    set_label(element) {
        console.log(this.field_attrs)
        element.setAttribute('for', this.field_attrs.id.value)
        element.innerText = this.field_attrs.label.value

        if(this.field_attrs.required) {
            element.innerText = element.innerText + '*'
        }
    }
    set_html_attrs(element) {
        for (const [name, attr_obj] of Object.entries(this.field_attrs)) {
            if (attr_obj.attr_type === 'html') {
                element.setAttribute(name, attr_obj.value)
            }
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
                // Todo: This logic needs to be smarter and not set fields that are already set?
                glueField.set_label(this.$refs.label)
                glueField.set_html_attrs(this.$refs.field)
            })
        },
        glue_field: null
    }));
});
