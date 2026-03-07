(() => {
  // client_js/src/constants.js
  var baseUrlPath = "django_glue";
  var actionUrlPath = `/${baseUrlPath}`;
  var keepLiveUrl = `/${baseUrlPath}/keep_live/`;

  // client_js/src/config.js
  var DEFAULT_CONFIG = {
    requestTimeoutMs: 30000
  };
  var config = { ...DEFAULT_CONFIG };
  function getConfig() {
    return config;
  }
  function setConfig(newConfig) {
    config = { ...config, ...newConfig };
  }

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
    csrfProtected: true,
    timeout: null
  }) {
    const timeoutMs = requestOptions.timeout ?? getConfig().requestTimeoutMs;
    const controller = new AbortController;
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    const options = {
      method: requestOptions.method,
      headers: {
        "Content-Type": requestOptions.contentType
      },
      signal: controller.signal
    };
    if (options.method === "POST") {
      options.body = requestOptions.body;
    }
    if (requestOptions.csrfProtected) {
      options.headers["X-CSRFToken"] = getHttpCookie("csrftoken");
    }
    try {
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
    } finally {
      clearTimeout(timeoutId);
    }
  }
  async function sendJsonPostRequest(url, data, csrfProtected = true) {
    return await sendHttpRequest(url, {
      body: JSON.stringify(data ? data : {}),
      method: "POST",
      contentType: "application/json",
      csrfProtected
    });
  }
  async function sendActionRequest({ uniqueName, action, payload, contextData }) {
    const url = `${actionUrlPath}/${uniqueName}/${action}/`;
    const data = { payload, context_data: contextData };
    return await sendJsonPostRequest(url, data);
  }
  async function sendKeepLiveRequest(uniqueNames) {
    return await sendJsonPostRequest(keepLiveUrl, { unique_names: uniqueNames });
  }

  // client_js/src/proxies/base.js
  class BaseGlueProxy {
    constructor({ proxyUniqueName, contextData, actions = null }) {
      this.uniqueName = proxyUniqueName;
      this.contextData = contextData;
      this.actions = actions ? actions : contextData.actions;
      this.listeners = {
        before: {},
        after: {},
        error: {}
      };
    }
    setActionPayload(actionName, payload) {
      this.actions[actionName].payload = payload;
    }
    getActionPayload(actionName) {
      return this.actions[actionName].payload;
    }
    addListener(actionName, callback, type = "after") {
      if (!this.listeners[type]) {
        throw new Error(`Invalid listener type: ${type}. Use 'before', 'after', or 'error'.`);
      }
      if (!this.listeners[type][actionName]) {
        this.listeners[type][actionName] = [];
      }
      this.listeners[type][actionName].push(callback);
      return this;
    }
    removeListener(actionName, callback, type = "after") {
      const listeners = this.listeners[type]?.[actionName];
      if (listeners) {
        const index = listeners.indexOf(callback);
        if (index > -1) {
          listeners.splice(index, 1);
        }
      }
      return this;
    }
    async emitListeners(type, actionName, event) {
      const listeners = this.listeners[type]?.[actionName] || [];
      for (const callback of listeners) {
        await callback(event);
      }
    }
    async processAction(actionName, payload = null) {
      payload = payload ?? this.getActionPayload(actionName);
      const event = {
        action: actionName,
        proxy: this,
        payload
      };
      await this.emitListeners("before", actionName, event);
      try {
        const response = await sendActionRequest({
          uniqueName: this.uniqueName,
          action: actionName,
          payload: payload ?? this.getActionPayload(actionName),
          contextData: this.contextData
        });
        event.result = response.data;
        await this.emitListeners("after", actionName, event);
        return response.data;
      } catch (err) {
        event.error = err;
        await this.emitListeners("error", actionName, event);
        throw err;
      }
    }
  }

  // client_js/src/proxies/model.js
  class GlueModelProxy extends BaseGlueProxy {
    constructor({
      proxyUniqueName,
      contextData,
      actions = null,
      autoFetch = false,
      values = null
    }) {
      super({ proxyUniqueName, contextData, actions, autoFetch });
      this.values = values;
      this.#defineFieldsMeta();
      if (this.autoFetch && !this.values) {
        this.loadData();
      }
      this.#defineFieldsAsProperties();
    }
    #defineFieldsMeta() {
      this.fields = {};
      Object.entries(this.contextData.fields).forEach(([fieldName, fieldData]) => {
        const field = { ...fieldData };
        if (field.type === "ForeignKey") {
          if (!fieldData.hasOwnProperty("_choicesCache")) {
            fieldData._choicesCache = [];
            fieldData._choicesLoaded = false;
            fieldData._loadingChoices = false;
            fieldData._choicesPromise = null;
          }
          const _choicesAction = async function() {
            if (fieldData._choicesPromise) {
              return fieldData._choicesPromise;
            }
            fieldData._loadingChoices = true;
            fieldData._choicesPromise = this.processAction("foreign_key_choices", {
              field_definition: [
                fieldName,
                fieldData
              ]
            }).then((data) => {
              fieldData._choicesCache = data;
              fieldData._choicesLoaded = true;
              return data;
            }).finally(() => {
              fieldData._loadingChoices = false;
            });
            return fieldData._choicesPromise;
          }.bind(this);
          field.choices = async function() {
            if (!fieldData._choicesLoaded) {
              await _choicesAction();
            }
            return fieldData._choicesCache;
          };
        }
        this.fields[fieldName] = field;
      });
    }
    #defineFieldsAsProperties() {
      Object.keys(this.contextData.fields).forEach((fieldName) => {
        Object.defineProperty(this, fieldName, {
          get: function() {
            if (!this.loaded && !this.autoFetch && !this.values) {
              if (!this.loading) {
                this.loading = true;
                this.loadData();
              }
            }
            return this.values?.[fieldName];
          },
          set: function(value) {
            if (!this.values) {
              this.values = {};
            }
            this.values[fieldName] = value;
          }
        });
      });
    }
    loadData() {
      this.processAction("get").then((data) => {
        this.values = data;
      }).finally(() => {
        this.loading = false;
        this.loaded = true;
      });
    }
    async save() {
      const result = await this.processAction("save", this.values);
      this.values = result;
      return result;
    }
    async delete() {
      return await this.processAction("delete", { id: this.values.id });
    }
  }

  // client_js/src/client.js
  class GlueClient {
    static proxyClassesForSubjectTypes = {};
    static contextData = {};
    static proxyRegistry = {};
    #activeProxies = {};
    #assembleProxyFromContextData(proxyUniqueName) {
      const { subject_type: subjectType } = GlueClient.contextData[proxyUniqueName];
      const ProxyClass = SUBJECT_TYPE_TO_PROXY_CLASS[subjectType];
      this.#activeProxies[proxyUniqueName] = new ProxyClass({
        proxyUniqueName,
        contextData: GlueClient.contextData[proxyUniqueName]
      });
      return this.#activeProxies[proxyUniqueName];
    }
    #defineLazyPropertyFromUniqueName(proxyUniqueName) {
      Object.defineProperty(this, proxyUniqueName, {
        get: function() {
          return this.#activeProxies?.[proxyUniqueName] ?? this.#assembleProxyFromContextData(proxyUniqueName);
        }
      });
    }
    #defineProxyUniqueNamesAsProperties() {
      for (const proxyUniqueName of Object.keys(GlueClient.proxyRegistry)) {
        this.#defineLazyPropertyFromUniqueName(proxyUniqueName);
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
      keepLiveInterval,
      config: config2 = {}
    }) {
      if (config2) {
        setConfig(config2);
      }
      GlueClient.proxyRegistry = proxyRegistryFromSession;
      GlueClient.contextData = contextDataForProxies;
      this.#defineProxyUniqueNamesAsProperties();
      this.#initializeKeepLivePulse(keepLiveInterval);
    }
  }
  var client_default = GlueClient;

  // client_js/src/proxies/queryset.js
  class GlueQuerySetProxy extends BaseGlueProxy {
    items = [];
    lastQuery = { method: "all", params: null };
    loaded = false;
    loading = false;
    constructor(options) {
      super(options);
    }
    *[Symbol.iterator]() {
      yield* this.items;
    }
    buildChildGlueModelProxy(item) {
      const proxy = new GlueModelProxy({
        proxyUniqueName: this.uniqueName,
        contextData: client_default.contextData[this.uniqueName],
        values: { ...item }
      });
      const querysetProxy = this;
      Object.keys(proxy.actions).forEach((actionName) => {
        ["before", "after", "error"].forEach((type) => {
          proxy.addListener(actionName, (event) => {
            querysetProxy.emitListeners(type, actionName, event);
          }, type);
        });
      });
      proxy.addListener("delete", () => querysetProxy.refresh());
      return proxy;
    }
    async all() {
      this.loading = true;
      debugger;
      if (this.items.length === 0 || this.lastQuery?.method !== "all") {
        const data = await this.processAction("all");
        this.items = data.map((item) => this.buildChildGlueModelProxy(item));
        this.lastQuery = { method: "all", params: null };
      }
      this.loaded = true;
      this.loading = false;
      return this.items;
    }
    async filter(filterParams) {
      this.loading = true;
      if (this.items.length === 0 || !this.isEqual(filterParams, this.lastQuery?.params)) {
        const data = await this.processAction("filter", filterParams);
        this.items = data.map((item) => this.buildChildGlueModelProxy(item));
        this.lastQuery = { method: "filter", params: filterParams };
      }
      this.loaded = true;
      this.loading = false;
      return this.items;
    }
    isEqual(a, b) {
      if (a === b)
        return true;
      if (a == null || b == null)
        return false;
      if (Array.isArray(a) && Array.isArray(b)) {
        if (a.length !== b.length)
          return false;
        return a.every((val, i) => this.isEqual(val, b[i]));
      }
      if (typeof a === "object" && typeof b === "object") {
        const keysA = Object.keys(a);
        const keysB = Object.keys(b);
        if (keysA.length !== keysB.length)
          return false;
        return keysA.every((key) => keysB.includes(key) && this.isEqual(a[key], b[key]));
      }
      return false;
    }
    async refresh() {
      this.items = [];
      const { method, params } = this.lastQuery;
      return this[method](params);
    }
  }

  // client_js/src/proxies/form.js
  class GlueFormProxy extends BaseGlueProxy {
    constructor({ proxyUniqueName, contextData, actions = null }) {
      super({ proxyUniqueName, contextData, actions });
    }
    postInit() {
      this.fields = this.contextData.fields;
      this.values = { ...this.contextData.initial };
      this.errors = {};
      Object.keys(this.fields).forEach((fieldName) => {
        Object.defineProperty(this, fieldName, {
          get: () => this.values[fieldName],
          set: (value) => {
            this.values[fieldName] = value;
          }
        });
      });
    }
    async validate() {
      const result = await this.processAction("validate", this.values);
      this.errors = result.errors || {};
      return result;
    }
    async submit() {
      const result = await this.processAction("submit", this.values);
      this.errors = result.errors || {};
      return result;
    }
    getFieldDefinition(fieldName) {
      return this.fields[fieldName] || null;
    }
    getFieldError(fieldName) {
      return this.errors[fieldName] || [];
    }
    hasErrors() {
      return Object.keys(this.errors).length > 0;
    }
    clearErrors() {
      this.errors = {};
    }
  }

  // client_js/src/proxies/index.js
  var SUBJECT_TYPE_TO_PROXY_CLASS = {
    Model: GlueModelProxy,
    QuerySet: GlueQuerySetProxy,
    BaseForm: GlueFormProxy
  };
  window.BaseGlueProxy = BaseGlueProxy;
  window.GlueModelProxy = GlueModelProxy;
  window.GlueQuerySetProxy = GlueQuerySetProxy;
  window.GlueFormProxy = GlueFormProxy;

  // client_js/glue.js
  var Glue = new client_default;
  window.Glue = Glue;
})();
