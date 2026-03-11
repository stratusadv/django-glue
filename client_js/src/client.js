import {sendKeepLiveRequest} from "./http";
import {SUBJECT_TYPE_TO_PROXY_CLASS} from "./proxies";
import {setConfig} from "./config";

// TODO: This is becoming a god class and needs to be broken down
class GlueClient {
    static proxyClassesForSubjectTypes = {}
    static contextData = {}
    static proxyRegistry = {}

    #keepLiveIntervalHandle = null
    #activeProxies = {}
    #config = {}

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

    #initializeKeepLivePulse() {
        const raiseDisconnectAlert = () => {
            clearInterval(this.#keepLiveIntervalHandle)

            let confirmation = confirm(this.#config.sessionExpiryMessage)
            if (confirmation) {
                window.location.reload()
            }
        }

        this.#keepLiveIntervalHandle = setInterval(() => {
            const keepLiveNames = Object.keys(this.#activeProxies)
            sendKeepLiveRequest(keepLiveNames).then(response => {
                if (!response.ok) {
                    raiseDisconnectAlert()
                }
            }).catch(err => {
                console.log(err)
                raiseDisconnectAlert()
            })
        }, this.#config.keepLiveIntervalSeconds * 1000)
    }

    init({
        proxyRegistryFromSession,
        contextDataForProxies,
        config = {},
    }) {
        GlueClient.proxyRegistry = proxyRegistryFromSession
        GlueClient.contextData = contextDataForProxies

        this.#config = setConfig(config)

        this.#defineProxyUniqueNamesAsProperties()
        this.#initializeKeepLivePulse()
    }
}

export default GlueClient