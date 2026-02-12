import { BaseGlueProxy } from "./proxies/base";
import {getClassByName} from "./utils";


class GlueProxyManager {
    #proxyProviders = {}
    #proxies = {}

    addProxyProvider(typeName, typeClass) {
        if (!(typeClass.prototype instanceof BaseGlueProxy)) {
            throw Error(`The class registered ('${typeClass}') for the adapter type '${typeName}' does not extend BaseGlueProxy.`)
        }

        this.#proxyProviders[typeName] = typeClass
    }

    #registerProxyProviders() {
        this.#proxyProviders = {}

        Object.entries(proxyTypeConfig).forEach(([typeName, typeClass]) => {
            this.addProxyProvider(typeName, getClassByName(typeClass))
        })
    }

    #createProxy(adapterUniqueName, adapterType) {
        return new this.#proxyProviders[adapterType](adapterUniqueName)
    }

    #defineProxyUniqueNameAsProperty(glueSessionData) {
        Object.defineProperty(this, glueSessionData.unique_name, {
            get: function() {
                if (!(glueSessionData.unique_name in this.#proxies)) {
                    this.#proxies[glueSessionData.unique_name] = this.#createProxy(
                        glueSessionData.unique_name,
                        glueSessionData.target_class
                    )
                }

                return this.#proxies[glueSessionData.unique_name]
            },
        })
    }

    #loadSession() {
        for (const glueSessionData of Object.values(glueServerData.session)) {
            this.#defineProxyUniqueNameAsProperty(glueSessionData)
        }
    }

    // TODO: pass data and type config from global scope as parameters to make this more
    // explicitly defined
    init() {
        this.#registerProxyProviders()
        this.#loadSession()
    }
}

export default GlueProxyManager