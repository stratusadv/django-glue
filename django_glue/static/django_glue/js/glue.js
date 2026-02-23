(() => {
  var __defProp = Object.defineProperty;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __publicField = (obj, key, value) => {
    __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
    return value;
  };
  var __accessCheck = (obj, member, msg) => {
    if (!member.has(obj))
      throw TypeError("Cannot " + msg);
  };
  var __privateGet = (obj, member, getter) => {
    __accessCheck(obj, member, "read from private field");
    return getter ? getter.call(obj) : member.get(obj);
  };
  var __privateAdd = (obj, member, value) => {
    if (member.has(obj))
      throw TypeError("Cannot add the same private member more than once");
    member instanceof WeakSet ? member.add(obj) : member.set(obj, value);
  };
  var __privateMethod = (obj, member, method) => {
    __accessCheck(obj, member, "access private method");
    return method;
  };

  // client_js/src/constants.js
  var baseUrlPath = "django_glue";
  var actionUrl = `/${baseUrlPath}/`;
  var keepLiveUrl = `/${baseUrlPath}/keep_live/`;

  // client_js/src/config.js
  var DEFAULT_CONFIG = {
    requestTimeoutMs: 3e4
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
    const controller = new AbortController();
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
    constructor({ proxyUniqueName, contextData, actions = null, autoFetch = false }) {
      this.uniqueName = proxyUniqueName;
      this.contextData = contextData;
      this.actions = !!actions ? actions : contextData.actions;
      this.autoFetch = autoFetch;
      this.defineActionsAsProperties();
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
      return response.data;
    }
    defineActionsAsProperties() {
      Object.keys(this.actions).forEach((actionName) => {
        if (typeof this[actionName] === "function") {
          return;
        }
        this[actionName] = (payload) => this.processAction(actionName, payload);
      });
    }
    postInit() {
    }
  };

  // client_js/src/proxies/model.js
  var GlueModelProxy = class extends BaseGlueProxy {
    constructor({
      proxyUniqueName,
      contextData,
      actions = null,
      autoFetch = false,
      values = null
    }) {
      super({ proxyUniqueName, contextData, actions, autoFetch });
      this.values = values;
    }
    postInit() {
      if (this.autoFetch && !this.values) {
        this.loadData();
      }
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
      return await this.processAction("delete");
    }
  };

  // client_js/src/client.js
  var _activeProxies, _assembleProxyFromRegistryData, assembleProxyFromRegistryData_fn, _defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy, defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy_fn, _defineProxyUniqueNamesAsProperties, defineProxyUniqueNamesAsProperties_fn, _initializeKeepLivePulse, initializeKeepLivePulse_fn;
  var _GlueClient = class {
    constructor() {
      __privateAdd(this, _assembleProxyFromRegistryData);
      __privateAdd(this, _defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy);
      __privateAdd(this, _defineProxyUniqueNamesAsProperties);
      __privateAdd(this, _initializeKeepLivePulse);
      __privateAdd(this, _activeProxies, {});
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
      __privateMethod(this, _defineProxyUniqueNamesAsProperties, defineProxyUniqueNamesAsProperties_fn).call(this, proxyRegistryFromSession);
      _GlueClient.contextData = contextDataForProxies;
      __privateMethod(this, _initializeKeepLivePulse, initializeKeepLivePulse_fn).call(this, keepLiveInterval);
    }
  };
  var GlueClient = _GlueClient;
  _activeProxies = new WeakMap();
  _assembleProxyFromRegistryData = new WeakSet();
  assembleProxyFromRegistryData_fn = function(proxyInstanceRegistryData) {
    const { unique_name: uniqueName, subject_type: subjectType } = proxyInstanceRegistryData;
    const ProxyClass = SUBJECT_TYPE_TO_PROXY_CLASS[subjectType];
    __privateGet(this, _activeProxies)[uniqueName] = new ProxyClass({
      proxyUniqueName: proxyInstanceRegistryData.unique_name,
      contextData: _GlueClient.contextData[uniqueName]
    });
    return __privateGet(this, _activeProxies)[uniqueName];
  };
  _defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy = new WeakSet();
  defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy_fn = function(proxyInstanceRegistryData) {
    const { unique_name: proxyUniqueName } = proxyInstanceRegistryData;
    Object.defineProperty(this, proxyUniqueName, {
      get: function() {
        return __privateGet(this, _activeProxies)?.[proxyUniqueName] ?? __privateMethod(this, _assembleProxyFromRegistryData, assembleProxyFromRegistryData_fn).call(this, proxyInstanceRegistryData);
      }
    });
  };
  _defineProxyUniqueNamesAsProperties = new WeakSet();
  defineProxyUniqueNamesAsProperties_fn = function(proxyRegistryFromSession) {
    for (const proxyInstanceRegistryData of Object.values(proxyRegistryFromSession)) {
      __privateMethod(this, _defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy, defineProxyUniqueNameAsPropertyThatLazilyAssemblesAndReturnsProxy_fn).call(this, proxyInstanceRegistryData);
    }
  };
  _initializeKeepLivePulse = new WeakSet();
  initializeKeepLivePulse_fn = function(keepLiveInterval) {
    setInterval(() => {
      const keepLiveNames = Object.keys(__privateGet(this, _activeProxies));
      sendKeepLiveRequest(keepLiveNames).then((response) => {
        if (!response.ok) {
          let confirmation = confirm("Session expired. Do you want to reload the page?");
          if (confirmation) {
            window.location.reload();
          }
        }
      });
    }, keepLiveInterval);
  };
  __publicField(GlueClient, "proxyClassesForSubjectTypes", {});
  __publicField(GlueClient, "contextData", {});
  var client_default = GlueClient;

  // client_js/src/proxies/queryset.js
  var GlueQuerySetProxy = class extends BaseGlueProxy {
    postInit() {
      const baseAll = this.all.bind(this);
      this.all = async () => {
        const data = await baseAll();
        this.items = data.map((item) => this.buildQuerySetItem(item));
        return this.items;
      };
      const baseFilter = this.filter.bind(this);
      this.filter = async (filterParams) => {
        const data = await baseFilter(filterParams);
        this.items = data.map((item) => this.buildQuerySetItem(item));
        return this.items;
      };
    }
    *[Symbol.iterator]() {
      yield* this.items;
    }
    buildQuerySetItem(item) {
      return new GlueModelProxy({
        proxyUniqueName: this.uniqueName,
        contextData: client_default.contextData[this.uniqueName],
        actions: {
          save: { payload: { id: item.id } },
          delete: { payload: { id: item.id } }
        },
        values: { ...item }
      });
    }
  };

  // client_js/src/proxies/form.js
  var GlueFormProxy = class extends BaseGlueProxy {
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
  };

  // client_js/src/proxies/index.js
  var SUBJECT_TYPE_TO_PROXY_CLASS = {
    "Model": GlueModelProxy,
    "QuerySet": GlueQuerySetProxy,
    "BaseForm": GlueFormProxy
  };
  window.BaseGlueProxy = BaseGlueProxy;
  window.GlueModelProxy = GlueModelProxy;
  window.GlueQuerySetProxy = GlueQuerySetProxy;
  window.GlueFormProxy = GlueFormProxy;

  // client_js/glue.js
  var Glue = new client_default();
  window.Glue = Glue;
})();
