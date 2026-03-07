import {sendKeepLiveRequest} from "./http";
import {SUBJECT_TYPE_TO_PROXY_CLASS} from "./proxies";
import {setConfig} from "./config";

// TODO: This is becoming a god class and needs to be broken down
class GlueClient {
    static proxyClassesForSubjectTypes = {}
    static contextData = {}
    static proxyRegistry = {}
    #activeProxies = {}

    #assembleProxyFromContextData(proxyUniqueName) {
        const { subject_type: subjectType } = GlueClient.contextData[proxyUniqueName]

        const ProxyClass = SUBJECT_TYPE_TO_PROXY_CLASS[subjectType]
        this.#activeProxies[proxyUniqueName] = new ProxyClass({
            proxyUniqueName: proxyUniqueName,
            contextData: GlueClient.contextData[proxyUniqueName],
        })

        return this.#activeProxies[proxyUniqueName]
    }

    #defineLazyPropertyFromUniqueName(proxyUniqueName) {
        Object.defineProperty(this, proxyUniqueName, {
            get: function() {
                return this.#activeProxies?.[proxyUniqueName] ?? this.#assembleProxyFromContextData(proxyUniqueName)
            },
        })
    }

    #defineProxyUniqueNamesAsProperties() {
        for (const proxyUniqueName of Object.keys(GlueClient.proxyRegistry)) {
            this.#defineLazyPropertyFromUniqueName(proxyUniqueName)
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
        keepLiveInterval,
        config = {},
    }) {
        if (config) {
            setConfig(config);
        }

        GlueClient.proxyRegistry = proxyRegistryFromSession
        GlueClient.contextData = contextDataForProxies

        this.#defineProxyUniqueNamesAsProperties()

        this.#initializeKeepLivePulse(keepLiveInterval)
    }
}

export default GlueClient