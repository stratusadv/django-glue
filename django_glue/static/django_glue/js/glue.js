(() => {
  // client_js/src/constants.js
  var baseUrlPath = "django_glue";
  var actionUrlPath = `/${baseUrlPath}`;
  var keepLiveUrl = `/${baseUrlPath}/keep_live/`;

  // client_js/src/config.js
  var DEFAULT_CONFIG = {
    requestTimeoutMs: 30000,
    sessionExpiryMessage: "Django Glue Session expired. Do you want to reload the page?",
    keepLiveIntervalSeconds: 120
  };
  var config = { ...DEFAULT_CONFIG };
  function getConfig() {
    return config;
  }
  function setConfig(newConfig = {}) {
    config = { ...config, ...newConfig };
    return config;
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
    if (requestOptions.contentType === "multipart/form-data") {
      delete options.headers["Content-Type"];
    }
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        throw Error(`An error occurred when sending a glue http request: ${await response.text()}`);
      }
      return {
        ok: response.ok,
        body: await response.clone().text(),
        httpResponse: response,
        data: response.ok ? await response.json() : null
      };
    } catch (e) {
      throw e;
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
  async function sendFormPostRequest(url, data, csrfProtected = true) {
    return await sendHttpRequest(url, {
      body: data,
      method: "POST",
      contentType: "multipart/form-data",
      csrfProtected
    });
  }
  async function sendActionRequest({ uniqueName, action, payload, contextData }) {
    const url = `${actionUrlPath}/${uniqueName}/${action}/`;
    if (payload instanceof FormData) {
      payload.append("context_data", JSON.stringify(contextData));
      return await sendFormPostRequest(url, payload);
    }
    return await sendJsonPostRequest(url, { payload, context_data: contextData });
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
    async processAction(actionName, data = null) {
      const eventData = data instanceof FormData ? Object.fromEntries(Array.from(data.keys()).map((key) => [
        key,
        data.getAll(key).length > 1 ? data.getAll(key) : data.get(key)
      ])) : data;
      const event = {
        action: actionName,
        proxy: this,
        payload: eventData
      };
      await this.emitListeners("before", actionName, event);
      try {
        const response = await sendActionRequest({
          uniqueName: this.uniqueName,
          action: actionName,
          payload: data,
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

  // client_js/src/proxies/form.js
  class GlueFormProxy extends BaseGlueProxy {
    constructor({ proxyUniqueName, contextData, actions = null }) {
      super({ proxyUniqueName, contextData, actions });
      this._values = { ...this.contextData.initial || {} };
      this._errors = {};
      this.#defineFields();
    }
    defineModelChoiceField(fieldName, fieldData) {
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
      fieldData.choices = async function() {
        if (!fieldData._choicesLoaded) {
          await _choicesAction();
        }
        return fieldData._choicesCache;
      };
      return fieldData;
    }
    #defineFields() {
      const proxy = this;
      this.fields = {};
      Object.entries(this.contextData.fields).forEach(([fieldName, fieldData]) => {
        Object.defineProperty(this, fieldName, {
          get: function() {
            if (!this.loaded && !this.autoFetch && !this._values) {
              if (!this.loading) {
                this.loading = true;
                this.loadData();
              }
            }
            return this._values?.[fieldName];
          },
          set: function(value) {
            if (!this._values) {
              this._values = {};
            }
            this._values[fieldName] = value;
          }
        });
        if (fieldData.type === "ModelChoiceField") {
          fieldData = this.defineModelChoiceField(fieldName, fieldData);
        }
        this.fields[fieldName] = {
          ...fieldData,
          get value() {
            return proxy._values[fieldName];
          },
          set value(val) {
            proxy._values[fieldName] = val;
          },
          get errors() {
            return proxy._errors[fieldName] || [];
          }
        };
      });
    }
    loadData() {
      this.processAction("get").then((data) => {
        this._values = data;
      }).finally(() => {
        this.loading = false;
        this.loaded = true;
      });
    }
    get values() {
      return { ...this._values };
    }
    get formData() {
      const formData = new FormData;
      Object.entries(this._values).forEach(([fieldName, value]) => {
        if (Array.isArray(value)) {
          value.forEach((item) => formData.append(fieldName, item));
        } else if (value instanceof File || value instanceof Blob) {
          formData.append(fieldName, value);
        } else if (value instanceof FileList) {
          Array.from(value).forEach((file) => formData.append(fieldName, file));
        } else {
          formData.append(fieldName, value === null || value === undefined ? "" : value);
        }
      });
      return formData;
    }
    get errors() {
      return { ...this._errors };
    }
    _updateErrors(errors) {
      this._errors = errors || {};
    }
    async validate() {
      const result = await this.processAction("validate", this._values);
      this._updateErrors(result.errors);
      return result;
    }
    async save() {
      const result = await this.processAction("save", this.formData);
      this._errors = result.errors || {};
      if (result.success) {
        this._values = result.cleaned_data;
      }
      return result;
    }
    hasErrors() {
      return Object.keys(this._errors).length > 0;
    }
    clearErrors() {
      this._errors = {};
    }
  }

  // client_js/src/proxies/model.js
  class GlueModelProxy extends GlueFormProxy {
    constructor({
      proxyUniqueName,
      contextData,
      actions = null,
      autoFetch = false,
      values = null
    }) {
      super({ proxyUniqueName, contextData, actions, autoFetch });
      this._values = values;
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
    #keepLiveIntervalHandle = null;
    #activeProxies = {};
    #config = {};
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
    #initializeKeepLivePulse() {
      const raiseDisconnectAlert = () => {
        clearInterval(this.#keepLiveIntervalHandle);
        let confirmation = confirm(this.#config.sessionExpiryMessage);
        if (confirmation) {
          window.location.reload();
        }
      };
      this.#keepLiveIntervalHandle = setInterval(() => {
        const keepLiveNames = Object.keys(this.#activeProxies);
        sendKeepLiveRequest(keepLiveNames).then((response) => {
          if (!response.ok) {
            raiseDisconnectAlert();
          }
        }).catch((err) => {
          console.log(err);
          raiseDisconnectAlert();
        });
      }, this.#config.keepLiveIntervalSeconds * 1000);
    }
    init({
      proxyRegistryFromSession,
      contextDataForProxies,
      config: config2 = {}
    }) {
      GlueClient.proxyRegistry = proxyRegistryFromSession;
      GlueClient.contextData = contextDataForProxies;
      this.#config = setConfig(config2);
      this.#defineProxyUniqueNamesAsProperties();
      this.#initializeKeepLivePulse();
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
      if (!this.loaded || this.lastQuery?.method !== "all") {
        this.loading = true;
        const data = await this.processAction("all");
        this.items = data.map((item) => this.buildChildGlueModelProxy(item));
        this.lastQuery = { method: "all", params: null };
        this.loaded = true;
        this.loading = false;
      }
      return this.items;
    }
    async filter(filterParams) {
      if (!this.loaded || !this.isEqual(filterParams, this.lastQuery?.params)) {
        this.loading = true;
        const data = await this.processAction("filter", filterParams);
        this.items = data.map((item) => this.buildChildGlueModelProxy(item));
        this.lastQuery = { method: "filter", params: filterParams };
        this.loaded = true;
        this.loading = false;
      }
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
      this.loaded = false;
      const { method, params } = this.lastQuery;
      return this[method](params);
    }
    get empty() {
      return this.loaded && this.items.length === 0;
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
