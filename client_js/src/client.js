import { BaseGlueProxy } from "./proxies/base";
import {sendKeepLiveRequest} from "./http";

// TODO: This is becoming a god class and needs to be broken down
class GlueClient {
    #proxyClassesForSubjectTypes = {}
    #activeProxies = {}
    #contextData = {}

    registerProxyClassForSubjectType(subjectTypeName, proxyClass) {
        this.#validateProxyClass(proxyClass)
        this.#proxyClassesForSubjectTypes[subjectTypeName] = proxyClass
    }

    #loadProxyClassFromConfigurationByName(name, configuredProxyClassNamesForSubjectTypes){
        if (name.match(/^[a-zA-Z0-9_]+$/) && Object.values(configuredProxyClassNamesForSubjectTypes).includes(name)) {
          // proceed only if the name is a single word string and is in adapterTypeConfig
            return eval?.(`"use strict";(${name})`)
        } else {
          // arbitrary code is detected
          throw new Error(`ALERT: DANGEROUS STRING PASSED INTO 'getClassByName': '${name}'`);
        }
    }

    #loadProxyClasses(configuredProxyClassNamesForSubjectTypes) {
        for (const [subjectType, proxyClassName] of Object.entries(configuredProxyClassNamesForSubjectTypes)) {
            this.#proxyClassesForSubjectTypes[subjectType] = this.#loadProxyClassFromConfigurationByName(
                proxyClassName,
                configuredProxyClassNamesForSubjectTypes
            )
        }
        this.#validateRegisteredProxyClasses()
    }

    #validateProxyClass(proxyClass) {
        if (!(proxyClass.prototype instanceof BaseGlueProxy)) {
            throw Error(`The proxy class ('${proxyClass}') does not extend BaseGlueProxy.`)
        }
    }

    #validateRegisteredProxyClasses() {
        Object.values(this.#proxyClassesForSubjectTypes).forEach(proxyClass => {
            this.#validateProxyClass(proxyClass)
        })
    }

    #assembleProxyFromRegistryData(proxyInstanceRegistryData) {
        const { unique_name: uniqueName, subject_type: subjectType } = proxyInstanceRegistryData

        const ProxyClass = this.#proxyClassesForSubjectTypes[subjectType]
        this.#activeProxies[uniqueName] = new ProxyClass(
            proxyInstanceRegistryData,
            this.#contextData[uniqueName]
        )


        return this.#activeProxies[uniqueName]
    }

    #defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy(proxyInstanceRegistryData) {
        const {unique_name: proxyUniqueName} = proxyInstanceRegistryData
        Object.defineProperty(this, proxyUniqueName, {
            get: function() {
                return this.#activeProxies?.[proxyUniqueName] ?? this.#assembleProxyFromRegistryData(proxyInstanceRegistryData)
            },
        })
    }

    #defineProxyUniqueNamesAsProperties(proxyRegistryFromSession) {
        for (const proxyInstanceRegistryData of Object.values(proxyRegistryFromSession)) {
            this.#defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy(proxyInstanceRegistryData)
        }
    }

    #initializeKeepLivePulse(keepLiveInterval) {
        setInterval(() => {
            const keepLiveNames = Object.keys(this.#activeProxies)
            sendKeepLiveRequest(keepLiveNames).then(response => {
                if (!response.ok) {
                    let confirmation = confirm('Session expired. Do you want to reload the page?')

                    if (confirmation) {
                        window.location.reload()
                    }
                }
            })
        }, keepLiveInterval)
    }

    init({
        proxyRegistryFromSession,
        contextDataForProxies,
        configuredProxyClassNamesForSubjectTypes,
        keepLiveInterval
    }) {
        this.#loadProxyClasses(configuredProxyClassNamesForSubjectTypes)
        this.#defineProxyUniqueNamesAsProperties(proxyRegistryFromSession)
        this.#contextData = contextDataForProxies

        this.#initializeKeepLivePulse(keepLiveInterval)
    }
}

export default GlueClient