(() => {
  // client_js/src/constants.js
  var baseUrlPath = "django_glue";
  var actionUrl = `/${baseUrlPath}/`;
  var keepLiveUrl = `/${baseUrlPath}/keep_live/`;

  // client_js/src/http.js
  function getHttpCookie(name) {
    if (document?.cookie !== "") {
      const cookies = document.cookie.split(";").map((cookie) => cookie.trim());
      for (const cookie of cookies) {
        if (cookie.substring(0, name.length + 1) === name + "=") {
          return decodeURIComponent(cookie.substring(name.length + 1));
        }
      }
    }
    return null;
  }
  async function sendHttpRequest(url, requestOptions = {
    body: "",
    method: "GET",
    contentType: "application/json",
    csrfProtected: true
  }) {
    const options = {
      method: requestOptions.method,
      headers: {
        "Content-Type": requestOptions.contentType
      }
    };
    if (options.method === "POST") {
      options.body = requestOptions.body;
    }
    if (requestOptions.csrfProtected) {
      options.headers["X-CSRFToken"] = getHttpCookie("csrftoken");
    }
    const actionResponse = await fetch(url, options);
    if (!actionResponse.ok) {
      throw Error(`An error occurred when sending a glue http request: ${await actionResponse.text()}`);
    }
    return {
      ok: actionResponse.ok,
      body: await actionResponse.clone().text(),
      httpResponse: actionResponse,
      data: actionResponse.ok ? await actionResponse.json() : null
    };
  }
  async function sendJsonPostRequest(url, data, csrfProtected = true) {
    return await sendHttpRequest(url, {
      body: JSON.stringify(!!data ? data : {}),
      method: "POST",
      contentType: "application/json",
      csrfProtected
    });
  }
  async function sendActionRequest(payload = {}) {
    return await sendJsonPostRequest(actionUrl, payload);
  }
  async function sendKeepLiveRequest(uniqueNames) {
    return await sendJsonPostRequest(keepLiveUrl, { "unique_names": uniqueNames });
  }

  // client_js/src/proxies/base.js
  var BaseGlueProxy = class {
    constructor(proxyRegistryData, contextData) {
      this.uniqueName = proxyRegistryData.unique_name;
      this.contextData = contextData;
      this.actions = contextData.actions;
      this.#defineActionsAsProperties();
      this.postInit();
    }
    setActionPayload(actionName, payload) {
      this.actions[actionName].payload = payload;
    }
    getActionPayload(actionName) {
      return this.actions[actionName].payload;
    }
    async processAction(actionName, payload = null) {
      const requestData = {
        unique_name: this.uniqueName,
        action: actionName,
        payload: payload ?? this.getActionPayload(actionName)
      };
      const response = await sendActionRequest(requestData);
      if (response.ok) {
        return response.data;
      } else {
        console.error(`An error occurred when performing ${actionName} on target ${this.uniqueName}: ${response}`);
        return null;
      }
    }
    #defineActionsAsProperties() {
      Object.keys(this.actions).forEach((actionName) => this.defineActionAsProperty(actionName));
    }
    defineActionAsProperty(actionName) {
      Object.defineProperty(this, actionName, {
        value: (payload) => this.processAction(actionName, payload)
      });
    }
    postInit() {
    }
  };

  // client_js/src/proxies/model.js
  var GlueModelProxy = class extends BaseGlueProxy {
    // TODO: Clean this up
    postInit() {
      Object.keys(this.contextData.fields).forEach((fieldName) => {
        Object.defineProperty(this, fieldName, {
          get: function() {
            if (!this.loaded) {
              if (!this.loading) {
                this.loading = true;
                this.get().then((data) => {
                  this.values = data;
                }).finally(() => {
                  this.loading = false;
                  this.loaded = true;
                });
              }
            }
            return this.values?.[fieldName];
          },
          set: function(value) {
            if (!this.values) {
              this.values = {};
            }
            this.values[fieldName] = value;
            this.setActionPayload("save", this.values);
          }
        });
      });
    }
  };

  // client_js/src/proxies/index.js
  window.GlueModelProxy = GlueModelProxy;

  // client_js/src/client.js
  var GlueClient = class {
    #proxyClassesForSubjectTypes = {};
    #activeProxies = {};
    #contextData = {};
    registerProxyClassForSubjectType(subjectTypeName, proxyClass) {
      this.#validateProxyClass(proxyClass);
      this.#proxyClassesForSubjectTypes[subjectTypeName] = proxyClass;
    }
    #loadProxyClassFromConfigurationByName(name, configuredProxyClassNamesForSubjectTypes) {
      if (name.match(/^[a-zA-Z0-9_]+$/) && Object.values(configuredProxyClassNamesForSubjectTypes).includes(name)) {
        return eval?.(`"use strict";(${name})`);
      } else {
        throw new Error(`ALERT: DANGEROUS STRING PASSED INTO 'getClassByName': '${name}'`);
      }
    }
    #loadProxyClasses(configuredProxyClassNamesForSubjectTypes) {
      for (const [subjectType, proxyClassName] of Object.entries(configuredProxyClassNamesForSubjectTypes)) {
        this.#proxyClassesForSubjectTypes[subjectType] = this.#loadProxyClassFromConfigurationByName(
          proxyClassName,
          configuredProxyClassNamesForSubjectTypes
        );
      }
      this.#validateRegisteredProxyClasses();
    }
    #validateProxyClass(proxyClass) {
      if (!(proxyClass.prototype instanceof BaseGlueProxy)) {
        throw Error(`The proxy class ('${proxyClass}') does not extend BaseGlueProxy.`);
      }
    }
    #validateRegisteredProxyClasses() {
      Object.values(this.#proxyClassesForSubjectTypes).forEach((proxyClass) => {
        this.#validateProxyClass(proxyClass);
      });
    }
    #assembleProxyFromRegistryData(proxyInstanceRegistryData) {
      const { unique_name: uniqueName, subject_type: subjectType } = proxyInstanceRegistryData;
      const ProxyClass = this.#proxyClassesForSubjectTypes[subjectType];
      this.#activeProxies[uniqueName] = new ProxyClass(
        proxyInstanceRegistryData,
        this.#contextData[uniqueName]
      );
      return this.#activeProxies[uniqueName];
    }
    #defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy(proxyInstanceRegistryData) {
      const { unique_name: proxyUniqueName } = proxyInstanceRegistryData;
      Object.defineProperty(this, proxyUniqueName, {
        get: function() {
          return this.#activeProxies?.[proxyUniqueName] ?? this.#assembleProxyFromRegistryData(proxyInstanceRegistryData);
        }
      });
    }
    #defineProxyUniqueNamesAsProperties(proxyRegistryFromSession) {
      for (const proxyInstanceRegistryData of Object.values(proxyRegistryFromSession)) {
        this.#defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy(proxyInstanceRegistryData);
      }
    }
    #initializeKeepLivePulse(keepLiveInterval) {
      setInterval(() => {
        const keepLiveNames = Object.keys(this.#activeProxies);
        sendKeepLiveRequest(keepLiveNames).then((response) => {
          if (!response.ok) {
            let confirmation = confirm("Session expired. Do you want to reload the page?");
            if (confirmation) {
              window.location.reload();
            }
          }
        });
      }, keepLiveInterval);
    }
    init({
      proxyRegistryFromSession,
      contextDataForProxies,
      configuredProxyClassNamesForSubjectTypes,
      keepLiveInterval
    }) {
      this.#loadProxyClasses(configuredProxyClassNamesForSubjectTypes);
      this.#defineProxyUniqueNamesAsProperties(proxyRegistryFromSession);
      this.#contextData = contextDataForProxies;
      this.#initializeKeepLivePulse(keepLiveInterval);
    }
  };
  var client_default = GlueClient;

  // client_js/glue.js
  var Glue = new client_default();
  window.Glue = Glue;
})();
