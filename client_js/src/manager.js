import { BaseGlueAdapter } from "./adapters/base";
import {getClassByName} from "./utils";


class GlueAdapterManager {
    #adapterTypeRegistry = {}
    #adapterInstances = {}

    addAdapter(typeName, typeClass) {
        if (!(typeClass.prototype instanceof BaseGlueAdapter)) {
            throw Error(`The class registered ('${typeClass}') for the adapter type '${typeName}' does not extend BaseGlueAdapter.`)
        }

        this.#adapterTypeRegistry[typeName] = typeClass
    }

    #registerAdapterTypes() {
        this.#adapterTypeRegistry = {}

        Object.entries(adapterTypeConfig).forEach(([typeName, typeClass]) => {
            this.addAdapter(typeName, getClassByName(typeClass))
        })
    }

    #createAdapterInstance(adapterUniqueName, adapterType) {
        return new this.#adapterTypeRegistry[adapterType](adapterUniqueName)
    }

    #defineAdapterUniqueNameAsProperty(glueSessionData) {
        Object.defineProperty(this, glueSessionData.unique_name, {
            get: function() {
                if (!(glueSessionData.unique_name in this.#adapterInstances)) {
                    this.#adapterInstances[glueSessionData.unique_name] = this.#createAdapterInstance(
                        glueSessionData.unique_name,
                        glueSessionData.target_class
                    )
                }

                return this.#adapterInstances[glueSessionData.unique_name]
            },
        })
    }

    #loadSession() {
        for (const glueSessionData of Object.values(glueServerData.session)) {
            this.#defineAdapterUniqueNameAsProperty(glueSessionData)
        }
    }

    // TODO: pass data and type config from global scope as parameters to make this more
    // explicitly defined
    init() {
        this.#registerAdapterTypes()
        this.#loadSession()
    }
}

export default GlueAdapterManager