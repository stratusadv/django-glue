import FieldGlue from "./base"
import ChoiceFieldGlue from "./choice"
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
    if (metadata.choice_model_path && metadata.type === 'ManyToManyField') {
        return new ManyRelationFieldGlue(options).asProxy()
    }
    if (metadata.choice_model_path) {
        return new RelationFieldGlue(options).asProxy()
    }
    if (Array.isArray(metadata.choices)) {
        return new ChoiceFieldGlue(options).asProxy()
    }

    return new FieldGlue(options).asProxy()
}

export {
    FieldGlue,
    ChoiceFieldGlue,
    RelationFieldGlue,
    ManyRelationFieldGlue,
    createFieldGlue,
}
