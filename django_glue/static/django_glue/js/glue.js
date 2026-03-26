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
      body: JSON.stringify(data ?? {}),
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
    return await sendJsonPostRequest(url, { post_data: payload, context_data: contextData });
  }
  async function sendKeepLiveRequest(uniqueNames) {
    return await sendJsonPostRequest(keepLiveUrl, { unique_names: uniqueNames });
  }

  // client_js/src/proxies/base.js
  class BaseGlueProxy {
    constructor({ proxyUniqueName, contextData, actions = null }) {
      this.$uniqueName = proxyUniqueName;
      this.$contextData = contextData;
      this.$actions = actions ? actions : contextData.actions;
      this.$listeners = {
        before: {},
        after: {},
        error: {}
      };
    }
    addListener(actionName, callback, type = "after") {
      if (!this.$listeners[type]) {
        throw new Error(`Invalid listener type: ${type}. Use 'before', 'after', or 'error'.`);
      }
      if (!this.$listeners[type][actionName]) {
        this.$listeners[type][actionName] = [];
      }
      this.$listeners[type][actionName].push(callback);
      return this;
    }
    removeListener(actionName, callback, type = "after") {
      const listeners = this.$listeners[type]?.[actionName];
      if (listeners) {
        const index = listeners.indexOf(callback);
        if (index > -1) {
          listeners.splice(index, 1);
        }
      }
      return this;
    }
    clearListeners() {
      this.$listeners = {};
      return this;
    }
    async emitListeners(type, actionName, event) {
      const listeners = this.$listeners[type]?.[actionName] || [];
      for (const callback of listeners) {
        await callback(event);
      }
    }
    async $processAction(actionName, data = null) {
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
          uniqueName: this.$uniqueName,
          action: actionName,
          payload: data,
          contextData: this.$contextData
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

  // client_js/src/utils.js
  var snakeToPascal = (string) => {
    return string.split("/").map((snake) => snake.split("_").map((substr) => substr.charAt(0).toUpperCase() + substr.slice(1)).join("")).join("/");
  };

  // client_js/src/proxies/form.js
  class GlueFormProxy extends BaseGlueProxy {
    constructor({ proxyUniqueName, contextData, actions = null }) {
      super({ proxyUniqueName, contextData, actions });
      this.$values = { ...this.$contextData.initial || {} };
      this.$errors = {};
      this.$defineFields();
    }
    __defineModelChoiceField(fieldName, fieldData) {
      if (!fieldData.hasOwnProperty("__choicesCache")) {
        fieldData.__glue__choicesCache = [];
        fieldData.__glue__choicesLoaded = false;
        fieldData.__glue__loadingChoices = false;
        fieldData.__glue__choicesPromise = null;
      }
      const choicesAction = async function() {
        if (fieldData.__glue__choicesPromise) {
          return fieldData.__glue__choicesPromise;
        }
        fieldData.__glue__loadingChoices = true;
        fieldData.__glue__choicesPromise = this.$processAction("foreign_key_choices", {
          field_definition: [
            fieldName,
            fieldData
          ]
        }).then((data) => {
          fieldData.__glue__choicesCache = data;
          fieldData._choicesLoaded = true;
          return data;
        }).finally(() => {
          fieldData.__glue__loadingChoices = false;
        });
        return fieldData.__glue__choicesPromise;
      }.bind(this);
      this[`${fieldName}Choices`] = async function() {
        if (!fieldData._choicesLoaded) {
          await choicesAction();
        }
        return fieldData.__glue__choicesCache;
      };
      return fieldData;
    }
    $defineFields() {
      this.$fields = {};
      Object.entries(this.$contextData.fields).forEach(([fieldName, fieldData]) => {
        Object.defineProperty(this, fieldName, {
          get: function() {
            if (!this.$loaded && !this.$values) {
              if (!this.$loading) {
                this.$loading = true;
                this.get();
              }
            }
            return this.$values?.[fieldName];
          },
          set: function(value) {
            if (!this.$values) {
              this.$values = {};
            }
            this.$values[fieldName] = value;
          }
        });
        if (["ModelChoiceField", "ModelMultipleChoiceField"].includes(fieldData.type)) {
          fieldData = this.__defineModelChoiceField(fieldName, fieldData);
        }
        this.$fields[fieldName] = fieldData;
        Object.keys(this.$fields[fieldName]).forEach((attributeName) => {
          this[`${fieldName}${snakeToPascal(attributeName)}`] = this.$fields?.[fieldName]?.[attributeName];
          this.$updateErrorAttributesForField(fieldName);
        });
      });
    }
    get(pk = null) {
      this.$processAction("get").then((data) => {
        this.$values = data;
      }).finally(() => {
        this.$loading = false;
        this.$loaded = true;
      });
    }
    $updateErrorAttributesForField(fieldName) {
      this[`${fieldName}HasErrors`] = this.$errors[fieldName]?.length > 0;
      this[`${fieldName}ErrorText`] = this.$errors[fieldName]?.join(", ");
    }
    $updateErrors(errors) {
      this.$errors = errors || {};
      Object.keys(this.$fields).forEach((fieldName) => {
        this.$updateErrorAttributesForField(fieldName);
      });
    }
    $updateValues(values) {
      this.$values = values || {};
      Object.entries(this.$fields).forEach(([fieldName, field]) => {
        field.value = this.$values[fieldName];
      });
    }
    $getFormData() {
      const formData = new FormData;
      Object.entries(this.$values).forEach(([fieldName, value]) => {
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
    async validate() {
      const result = await this.$processAction("validate", this.$values);
      this.$errors = result.errors || {};
      return result;
    }
    async save() {
      const result = await this.$processAction("save", this.$getFormData());
      this.$updateErrors(result.errors);
      if (result.success) {
        this.$clearErrors();
        this.get(this.$values.id);
      }
      return result;
    }
    hasErrors(fieldName) {
      if (fieldName) {
        return this.$errors[fieldName] && this.$errors[fieldName].length > 0;
      }
      return Object.keys(this.$errors).length > 0;
    }
    $clearErrors() {
      this.$errors = {};
    }
  }

  // client_js/src/proxies/model.js
  var $keyCounter = 0;

  class GlueModelProxy extends GlueFormProxy {
    constructor({
      proxyUniqueName,
      contextData,
      actions = null,
      autoFetch = false,
      values = null,
      parentQuerySet = null
    }) {
      super({ proxyUniqueName, contextData, actions, autoFetch });
      this.$values = values;
      this.$key = `glue_${++$keyCounter}`;
      this.$parent = parentQuerySet;
    }
    get $isNew() {
      return !this.$values?.id;
    }
    async get(pk = null) {
      let data;
      if (this.$parent) {
        data = await this.$parent.$processAction("get", { id: pk });
      } else {
        data = await this.$processAction("get");
      }
      this.$updateValues(data);
      this.$loading = false;
      this.$loaded = true;
    }
    async delete() {
      if (this.$isNew && this.$parent) {
        await this.$parent.refresh();
        return { success: true };
      }
      const result = await this.$processAction("delete", { id: this.$values.id });
      if (this.$parent) {
        await this.$parent.refresh();
      }
      return result;
    }
  }

  // client_js/src/client.js
  class GlueClient {
    static proxyClassesForSubjectTypes = {};
    static contextData = {};
    static proxyRegistry = {};
    #keepLiveIntervalHandle = null;
    #config = {};
    $activeProxies = {};
    #defineProxyUniqueNamesAsProperties() {
      for (const [proxyUniqueName, contextData] of Object.entries(GlueClient.contextData)) {
        const { subject_type: subjectType } = contextData;
        this.$activeProxies[proxyUniqueName] = new SUBJECT_TYPE_TO_PROXY_CLASS[subjectType]({
          proxyUniqueName,
          contextData: GlueClient.contextData[proxyUniqueName]
        });
        Object.defineProperty(this, proxyUniqueName, {
          get: () => this.$activeProxies[proxyUniqueName]
        });
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
        const keepLiveNames = Object.keys(this.$activeProxies);
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
    $items = [];
    $loaded = false;
    $loading = false;
    $queryParams = {};
    $prevQueryParams = {};
    constructor(options) {
      super(options);
    }
    *[Symbol.iterator]() {
      yield* this.$items;
    }
    buildChildModelProxy(item) {
      const proxy = new GlueModelProxy({
        proxyUniqueName: this.$uniqueName,
        contextData: client_default.contextData[this.$uniqueName],
        values: { ...item },
        parentQuerySet: this
      });
      const querysetProxy = this;
      Object.keys(proxy.$actions).forEach((actionName) => {
        ["before", "after", "error"].forEach((type) => {
          proxy.addListener(actionName, (event) => {
            querysetProxy.emitListeners(type, actionName, event);
          }, type);
        });
      });
      return proxy;
    }
    async all(queryParams = null) {
      if (queryParams) {
        this.$queryParams = queryParams;
      }
      if (!this.$loaded || !this.$isEqual(this.$prevQueryParams, this.$queryParams)) {
        this.$loading = true;
        const data = await this.$processAction("all", this.$queryParams);
        this.$items = data.map((item) => this.buildChildModelProxy(item));
        this.$prevQueryParams = this.$queryParams;
        this.$loaded = true;
        this.$loading = false;
      }
      return this.$items;
    }
    filter(filterParams) {
      return this.addQueryParam("filter", filterParams);
    }
    orderBy(orderParams) {
      return this.addQueryParam("order_by", orderParams);
    }
    sliceStart(idx) {
      return this.addQueryParam("slice", { start: idx });
    }
    sliceEnd(idx) {
      return this.addQueryParam("slice", { end: idx });
    }
    slice(start = 0, stop = null) {
      return this.addQueryParam("slice", { start, stop });
    }
    addQueryParam(type, params) {
      this.$queryParams[type] = params;
      return this;
    }
    $isEqual(a, b) {
      return JSON.stringify(a) === JSON.stringify(b);
    }
    async refresh() {
      this.$items = [];
      this.$loaded = false;
      return this.all();
    }
    get isEmpty() {
      return this.$loaded && this.$items.length === 0;
    }
    get isLoaded() {
      return this.$loaded;
    }
    async prependNew() {
      return this.pushNew("start");
    }
    async appendNew() {
      return this.pushNew("end");
    }
    async pushNew(location = "start") {
      const defaults = await this.$processAction("new");
      const newObj = this.buildChildModelProxy(defaults);
      if (location == "end") {
        this.$items = [...this.$items, newObj];
      } else if (location == "start") {
        this.$items = [newObj, ...this.$items];
      } else {
        throw new Error('Invalid location. Use "start" or "end".');
      }
      return this.$items;
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
