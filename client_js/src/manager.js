import { BaseGlue } from "./glue-types/base";
import { ModelGlue } from "./glue-types/model";


// TODO: remove this and use the constants defined in django_glue.html
const DEFAULT_GLUE_TYPE_CONSTRUCTORS = {
    Model: ModelGlue
}

class GlueManager {
    #glueTypes = {}
    #glueInstances = {}

    type(typeName, typeClass) {
        if (!(typeClass.prototype instanceof BaseGlue)) {
            throw Error(`The class registered ('${typeClass}') for the glue type '${typeName}' does not extend BaseGlue.`)
        }

        this.#glueTypes[typeName] = typeClass
    }

    #registerGlueTypes(types, includeDefaultGlueTypes) {
        this.#glueTypes = {}

        if (includeDefaultGlueTypes) {
            Object.entries(DEFAULT_GLUE_TYPE_CONSTRUCTORS).forEach(([target, instanceClass]) => {
                this.type(target, instanceClass)
            })
        }

        Object.entries(types).forEach(([type, instanceClass]) => {
            this.type(type, instanceClass)
        })
    }

    #createGlue(glueUniqueName, glueTargetClass) {
        return new this.#glueTypes[glueTargetClass](glueUniqueName)
    }

    #defineGlueUniqueNameAsProperty(glueSessionData) {
        Object.defineProperty(this, glueSessionData.unique_name, {
            get: function() {
                if (!(glueSessionData.unique_name in this.#glueInstances)) {
                    this.#glueInstances[glueSessionData.unique_name] = this.#createGlue(
                        glueSessionData.unique_name,
                        glueSessionData.target_class
                    )
                }

                return this.#glueInstances[glueSessionData.unique_name]
            },
        })
    }

    #loadSession() {
        for (const glueSessionData of Object.values(glueServerData.session)) {
            this.#defineGlueUniqueNameAsProperty(glueSessionData)
        }
    }

    init(
        types = {},
        options = {
            includeDefaultGlueTypes: true
        }
    ) {
        this.#registerGlueTypes(types, options.includeDefaultGlueTypes)
        this.#loadSession()
    }
}

export default GlueManager