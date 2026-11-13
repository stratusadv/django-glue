import GlueValueAttribute from "./base"
import type {GlueValueAttributeOptions} from "./base"
import GlueChoiceAttribute from "./choice"
import GlueManyChoiceAttribute from "./manyChoice"
import GlueRelationAttribute from "./relation"
import GlueManyRelationAttribute from "./manyRelation"

function createValueAttribute({owner, name, fieldPath = name, stateKey, presentation = {}, existingAttribute = null}: GlueValueAttributeOptions & {
    stateKey: string
    existingAttribute?: GlueValueAttribute | null
}): GlueValueAttribute {
    if (existingAttribute?.__glue__isValueAttribute) {
        existingAttribute.updatePresentation(presentation)
        existingAttribute.name = name
        existingAttribute.fieldPath = fieldPath
        existingAttribute.stateKey = stateKey
        return existingAttribute
    }

    const options = {owner, name, fieldPath, stateKey, presentation}
    if (presentation.choice_model_path && ['ManyToManyField', 'ModelMultipleChoiceField'].includes(presentation.type ?? '')) {
        return new GlueManyRelationAttribute(options)
    }
    if (presentation.choice_model_path) {
        return new GlueRelationAttribute(options)
    }
    if (Array.isArray(presentation.choices)) {
        const stateValue = owner._record.getValue(stateKey)
        const multipleChoiceTypes = ['MultipleChoiceField', 'TypedMultipleChoiceField']
        const multipleChoiceWidgets = ['CheckboxSelectMultiple', 'SelectMultiple']
        if (
            Array.isArray(stateValue)
            || multipleChoiceTypes.includes(presentation.type ?? '')
            || multipleChoiceWidgets.includes(presentation.widget ?? '')
        ) {
            return new GlueManyChoiceAttribute(options)
        }
        return new GlueChoiceAttribute(options)
    }

    return new GlueValueAttribute(options)
}

export {
    GlueValueAttribute,
    GlueChoiceAttribute,
    GlueManyChoiceAttribute,
    GlueRelationAttribute,
    GlueManyRelationAttribute,
    createValueAttribute,
}
