import {sendKeepLiveRequest} from "./http";
import {SUBJECT_TYPE_TO_PROXY_CLASS} from "./proxies";

// TODO: This is becoming a god class and needs to be broken down
class GlueClient {
    static proxyClassesForSubjectTypes = {}
    static contextData = {}
    #activeProxies = {}

    #assembleProxyFromRegistryData(proxyInstanceRegistryData) {
        const { unique_name: uniqueName, subject_type: subjectType } = proxyInstanceRegistryData

        const ProxyClass = SUBJECT_TYPE_TO_PROXY_CLASS[subjectType]
        this.#activeProxies[uniqueName] = new ProxyClass({
            proxyUniqueName: proxyInstanceRegistryData.unique_name,
            contextData: GlueClient.contextData[uniqueName],
        })


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
        keepLiveInterval
    }) {
        this.#defineProxyUniqueNamesAsProperties(proxyRegistryFromSession)
        GlueClient.contextData = contextDataForProxies

        this.#initializeKeepLivePulse(keepLiveInterval)
    }
}

export default GlueClient