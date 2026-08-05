import FieldGlue from "./base"
import ChoiceFieldGlue from "./choice"
import ManyChoiceFieldGlue from "./manyChoice"
import RelationFieldGlue from "./relation"
import ManyRelationFieldGlue from "./manyRelation"

function createFieldGlue({owner, name, stateKey, metadata = {}, existingField = null}) {
    if (existingField?.__glue__isFieldProxy) {
        existingField.updateMetadata(metadata)
        existingField.name = name
        existingField.stateKey = stateKey
        return existingField
    }

    const options = {owner, name, stateKey, metadata}
    if (metadata.choice_model_path && ['ManyToManyField', 'ModelMultipleChoiceField'].includes(metadata.type)) {
        return new ManyRelationFieldGlue(options)
    }
    if (metadata.choice_model_path) {
        return new RelationFieldGlue(options)
    }
    if (Array.isArray(metadata.choices)) {
        const stateValue = owner._state?.[stateKey]?.value
        const multipleChoiceTypes = ['MultipleChoiceField', 'TypedMultipleChoiceField']
        const multipleChoiceWidgets = ['CheckboxSelectMultiple', 'SelectMultiple']
        if (
            Array.isArray(stateValue)
            || multipleChoiceTypes.includes(metadata.type)
            || multipleChoiceWidgets.includes(metadata.widget)
        ) {
            return new ManyChoiceFieldGlue(options)
        }
        return new ChoiceFieldGlue(options)
    }

    return new FieldGlue(options)
}

export {
    FieldGlue,
    ChoiceFieldGlue,
    ManyChoiceFieldGlue,
    RelationFieldGlue,
    ManyRelationFieldGlue,
    createFieldGlue,
}
