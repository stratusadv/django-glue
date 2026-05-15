(() => {
  // client_js/src/proxies/base.js
  class BaseGlueProxy {
    static name = "baseGlueProxy";
    constructor({ http, proxyUniqueName, contextData, actions = null }) {
      this.http = http;
      this._uniqueName = proxyUniqueName;
      this._contextData = contextData;
      this._actions = actions ? actions : contextData.actions;
      this._listeners = {
        before: {},
        after: {},
        error: {}
      };
    }
    addListener(actionName, callback, type = "after") {
      if (!this._listeners[type]) {
        throw new Error(`Invalid listener type: _${type}. Use 'before', 'after', or 'error'.`);
      }
      if (!this._listeners[type][actionName]) {
        this._listeners[type][actionName] = [];
      }
      this._listeners[type][actionName].push(callback);
      return this;
    }
    removeListener(actionName, callback, type = "after") {
      const listeners = this._listeners[type]?.[actionName];
      if (listeners) {
        const index = listeners.indexOf(callback);
        if (index > -1) {
          listeners.splice(index, 1);
        }
      }
      return this;
    }
    clearListeners() {
      this._listeners = {};
      return this;
    }
    async emitListeners(type, actionName, event) {
      const listeners = this._listeners[type]?.[actionName] || [];
      for (const callback of listeners) {
        await callback(event);
      }
    }
    async _processAction(actionName, data = null) {
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
        const response = await this.http.sendActionRequest({
          uniqueName: this._uniqueName,
          action: actionName,
          payload: data,
          contextData: this._contextData
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
    static name = "form";
    constructor({ http, proxyUniqueName, contextData, actions = null }) {
      super({ http, proxyUniqueName, contextData, actions });
      this._values = { ...this._contextData.initial || {} };
      this._errors = {};
      this._defineFields();
      Object.defineProperty(this, "$fields", {
        get: () => {
          return this._fields;
        },
        set: (value) => {
          this._fields = value;
        }
      });
    }
    _defineModelChoiceField(fieldName, fieldData) {
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
        fieldData.__glue__choicesPromise = this._processAction("foreign_key_choices", {
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
    _defineFieldNameProperty(fieldName) {
      Object.defineProperty(this, fieldName, {
        get: function() {
          if (!this._loaded && !this._values) {
            if (!this._loading) {
              this._loading = true;
              this.get();
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
    }
    _defineFields() {
      this._fields = {};
      Object.entries(this._contextData.fields).forEach(([fieldName, fieldData]) => {
        this._defineFieldNameProperty(fieldName);
        if (["ModelChoiceField", "ModelMultipleChoiceField"].includes(fieldData.type)) {
          fieldData = this._defineModelChoiceField(fieldName, fieldData);
        }
        this._fields[fieldName] = fieldData;
        Object.keys(this._fields[fieldName]).forEach((attributeName) => {
          this[`${fieldName}${snakeToPascal(attributeName)}`] = this._fields?.[fieldName]?.[attributeName];
          this._updateErrorAttributesForField(fieldName);
        });
      });
    }
    get(pk = null) {
      this._processAction("get").then((data) => {
        this._values = data;
      }).finally(() => {
        this._loading = false;
        this._loaded = true;
      });
    }
    _updateErrorAttributesForField(fieldName) {
      this[`${fieldName}HasErrors`] = this._errors[fieldName]?.length > 0;
      this[`${fieldName}ErrorText`] = this._errors[fieldName]?.join(", ");
    }
    _updateErrors(errors) {
      this._errors = errors || {};
      Object.keys(this._fields).forEach((fieldName) => {
        this._updateErrorAttributesForField(fieldName);
      });
    }
    _getFormData() {
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
    async validate() {
      const result = await this._processAction("validate", this._values);
      this._errors = result.errors || {};
      return result;
    }
    async save() {
      const result = await this._processAction("save", this._getFormData());
      this._updateErrors(result.errors);
      if (result.success) {
        this._clearErrors();
        this.get(this._values.id);
      }
      return result;
    }
    hasErrors(fieldName) {
      if (fieldName) {
        return this._errors[fieldName] && this._errors[fieldName].length > 0;
      }
      return Object.keys(this._errors).length > 0;
    }
    _clearErrors() {
      this._errors = {};
    }
  }

  // client_js/src/proxies/model.js
  var _keyCounter = 0;

  class GlueModelProxy extends GlueFormProxy {
    static name = "model";
    constructor({
      http,
      proxyUniqueName,
      contextData,
      actions = null,
      autoFetch = false,
      values = null,
      parentQuerySet = null
    }) {
      super({ http, proxyUniqueName, contextData, actions, autoFetch });
      this._values = values;
      if (values) {
        this._defineExtraFields();
      }
      this.$key = `django-glue-${++_keyCounter}`;
      this._parent = parentQuerySet;
      this.$form = {};
      Object.defineProperty(this.$form, "$fields", {
        get: () => {
          return this._fields;
        },
        set: (value) => {
          this._fields = value;
        }
      });
    }
    _defineExtraFields() {
      Object.keys(this._values).forEach((fieldName) => {
        if (!(fieldName in this)) {
          this._defineFieldNameProperty(fieldName);
        }
      });
    }
    get _isNew() {
      return !this._values?.id;
    }
    async get(pk = null) {
      let data;
      if (this._parent) {
        data = await this._parent._processAction("get", { id: pk });
      } else {
        data = await this._processAction("get");
      }
      this._values = data;
      this._loading = false;
      this._loaded = true;
    }
    async delete() {
      if (this._isNew && this._parent) {
        await this._parent.refresh();
        return { success: true };
      }
      const result = await this._processAction("delete", { id: this._values.id });
      if (this._parent) {
        await this._parent.refresh();
      }
      return result;
    }
  }

  // client_js/src/http.js
  class GlueHttp {
    constructor(config) {
      this._config = config;
    }
    getCookie(name) {
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
    async sendRequest(url, requestOptions = {
      body: "",
      method: "GET",
      contentType: "application/json",
      csrfProtected: true,
      timeoutSeconds: null
    }) {
      const timeoutSeconds = requestOptions.timeoutSeconds ?? this._config.requestTimeoutSeconds;
      const controller = new AbortController;
      const timeoutId = setTimeout(() => controller.abort(), timeoutSeconds * 1000);
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
        options.headers["X-CSRFToken"] = this.getCookie("csrftoken");
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
    async sendJsonGetRequest(url, data) {
      return await this.sendRequest(url, {
        body: JSON.stringify(data ?? {}),
        method: "GET",
        contentType: "application/json"
      });
    }
    async sendJsonPostRequest(url, data, csrfProtected = true) {
      return await this.sendRequest(url, {
        body: JSON.stringify(data ?? {}),
        method: "POST",
        contentType: "application/json",
        csrfProtected
      });
    }
    async sendFormPostRequest(url, data, csrfProtected = true) {
      return await this.sendRequest(url, {
        body: data,
        method: "POST",
        contentType: "multipart/form-data",
        csrfProtected
      });
    }
    async sendActionRequest({ uniqueName, action, payload, contextData }) {
      const url = `${this._config.actionUrlPath}/${uniqueName}/${action}/`;
      if (payload instanceof FormData) {
        payload.append("context_data", JSON.stringify(contextData));
        return await this.sendFormPostRequest(url, payload);
      }
      return await this.sendJsonPostRequest(url, { post_data: payload, context_data: contextData });
    }
    async sendKeepLiveRequest(uniqueNames) {
      return await this.sendJsonPostRequest(this._config.keepLiveUrlPath, { unique_names: uniqueNames });
    }
  }
  var http_default = GlueHttp;

  // client_js/src/view.js
  class GlueView {
    constructor(http, url, shared_payload = {}, skipEncodePath = true) {
      let config_url = new URL(window.location.origin + url);
      if (!skipEncodePath) {
        config_url.searchParams.append("glue_encode_path", window.location.pathname);
      }
      this.http = http;
      this.url = config_url.pathname + config_url.search;
      this.shared_payload = shared_payload;
    }
    async get(payload = {}) {
      return await this._fetchView(payload, "GET");
    }
    async post(payload = {}) {
      return await this._fetchView(payload);
    }
    async _fetchView(payload = {}, method = "POST") {
      let viewResponse = await this.http.sendHttpRequest(this.http._config.glueViewUrlPath, {
        method: "POST",
        body: JSON.stringify({
          url_path: this.url,
          method,
          view_payload: {
            ...this.shared_payload,
            ...payload
          }
        }),
        csrfProtected: true
      });
      window.Glue.initializeProxies(viewResponse.data.proxy_registry_data, viewResponse.data.proxy_context_data);
      return viewResponse.data.html;
    }
    async renderInnerHtml(target_element, payload = {}) {
      target_element.innerHTML = await this._fetchView(payload);
    }
    async _renderInsertAdjacentHtml(target_element, position, payload = {}) {
      const html = await this._fetchView(payload);
      target_element.insertAdjacentHTML(position, html);
    }
    async renderInsertAdjacentHtmlBeforeEnd(target_element, payload = {}) {
      await this._renderInsertAdjacentHtml(target_element, "beforeend", payload);
    }
    async renderInsertAdjacentHtmlAfterEnd(target_element, payload = {}) {
      await this._renderInsertAdjacentHtml(target_element, "afterend", payload);
    }
    async renderInsertAdjacentHtmlBeforeBegin(target_element, payload = {}) {
      await this._renderInsertAdjacentHtml(target_element, "beforebegin", payload);
    }
    async renderInsertAdjacentHtmlAfterBegin(target_element, payload = {}) {
      await this._renderInsertAdjacentHtml(target_element, "afterbegin", payload);
    }
    async renderOuterHtml(target_element, payload = {}) {
      target_element.outerHTML = await this._fetchView(payload);
    }
  }
  var view_default = GlueView;

  // client_js/src/client.js
  class GlueClient {
    static contextData = {};
    static proxyClassesForSubjectTypes = {};
    static proxyRegistry = {};
    model = {};
    querySet = {};
    form = {};
    _keepLiveIntervalHandle = null;
    _defineProxyUniqueNameAsPropertyFromContextData(proxyUniqueName, contextData) {
      const { subject_type: subjectType } = contextData;
      let proxyClass = SUBJECT_TYPE_TO_PROXY_CLASS[subjectType];
      if (!(proxyClass.name in this)) {
        this[proxyClass.name] = {};
      }
      this[proxyClass.name][proxyUniqueName] = new proxyClass({
        http: this.http,
        proxyUniqueName,
        contextData
      });
    }
    async fetch(url, requestOptions = {
      body: "",
      method: "GET",
      contentType: "application/json",
      csrfProtected: true,
      timeout: null
    }) {
      return await this.http.sendRequest(url, requestOptions);
    }
    _initializeKeepLivePulse() {
      if (this._keepLiveIntervalHandle) {
        clearInterval(this._keepLiveIntervalHandle);
      }
      const raiseDisconnectAlert = () => {
        clearInterval(this._keepLiveIntervalHandle);
        let confirmation = confirm(this._config.sessionExpiryMessage);
        if (confirmation) {
          window.location.reload();
        }
      };
      const correctedKeepLiveIntervalSeconds = Math.max(this._config.keepLiveIntervalSeconds, this._config.minimumKeepLiveIntervalSeconds);
      this._keepLiveIntervalHandle = setInterval(() => {
        const keepLiveNames = Object.keys({
          ...this.model,
          ...this.querySet,
          ...this.form
        });
        this.http.sendKeepLiveRequest(keepLiveNames).then((response) => {
          if (!response.ok) {
            raiseDisconnectAlert();
          }
        }).catch((err) => {
          console.log(err);
          raiseDisconnectAlert();
        });
      }, correctedKeepLiveIntervalSeconds * 1000);
    }
    init({
      proxyRegistryFromSession,
      contextDataForProxies,
      config = {}
    }) {
      this._config = config;
      this.http = new http_default(this._config);
      this.initializeProxies(proxyRegistryFromSession, contextDataForProxies);
    }
    initializeProxies(proxyRegistryFromSession, contextDataForProxies) {
      for (const [proxyUniqueName, contextData] of Object.entries(contextDataForProxies)) {
        this._defineProxyUniqueNameAsPropertyFromContextData(proxyUniqueName, contextData);
      }
      Object.assign(GlueClient.proxyRegistry, proxyRegistryFromSession);
      Object.assign(GlueClient.contextData, contextDataForProxies);
      this._initializeKeepLivePulse();
    }
    view(url, shared_payload = {}) {
      return new view_default(this.http, url, shared_payload);
    }
  }
  var client_default = GlueClient;

  // client_js/src/proxies/queryset.js
  class GlueQuerySetProxy extends BaseGlueProxy {
    static name = "querySet";
    _items = [];
    _loaded = false;
    _loading = false;
    _queryParams = {};
    _prevQueryParams = {};
    constructor(options) {
      super(options);
    }
    *[Symbol.iterator]() {
      yield* this._items;
    }
    buildChildModelProxy(item) {
      const proxy = new GlueModelProxy({
        http: this.http,
        proxyUniqueName: this._uniqueName,
        contextData: client_default.contextData[this._uniqueName],
        values: { ...item },
        parentQuerySet: this
      });
      const querysetProxy = this;
      Object.keys(proxy._actions).forEach((actionName) => {
        ["before", "after", "error"].forEach((type) => {
          proxy.addListener(actionName, (event) => {
            querysetProxy.emitListeners(type, actionName, event);
          }, type);
        });
      });
      return proxy;
    }
    async queryWithParams(queryParams = null) {
      if (queryParams) {
        this._queryParams = queryParams;
      }
      if (!this._loaded || !this._isEqual(this._prevQueryParams, this._queryParams)) {
        this._loading = true;
        const data = await this._processAction("query_with_params", this._queryParams);
        this._items = data.map((item) => this.buildChildModelProxy(item));
        this._prevQueryParams = this._queryParams;
        this._loaded = true;
        this._loading = false;
      }
      return this._items;
    }
    async all() {
      return await this.queryWithParams();
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
      this._queryParams[type] = params;
      return this;
    }
    _isEqual(a, b) {
      return JSON.stringify(a) === JSON.stringify(b);
    }
    async refresh() {
      this._items = [];
      this._loaded = false;
      return this.queryWithParams();
    }
    get isEmpty() {
      return this._loaded && this._items.length === 0;
    }
    get isLoaded() {
      return this._loaded;
    }
    async prependNew() {
      return this.pushNew("start");
    }
    async appendNew() {
      return this.pushNew("end");
    }
    async pushNew(location = "start") {
      const defaults = await this._processAction("new");
      const newObj = this.buildChildModelProxy(defaults);
      if (location == "end") {
        this._items = [...this._items, newObj];
      } else if (location == "start") {
        this._items = [newObj, ...this._items];
      } else {
        throw new Error('Invalid location. Use "start" or "end".');
      }
      return this._items;
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

  // client_js/src/config.js
  class GlueConfig {
    constructor({
      requestTimeoutSeconds = 30,
      sessionExpiryMessage = "Session expired. Do you want to reload the page?",
      keepLiveIntervalSeconds = 600,
      actionUrlPath,
      keepLiveUrlPath,
      glueViewUrlPath
    }) {
      this.requestTimeoutSeconds = requestTimeoutSeconds;
      this.sessionExpiryMessage = sessionExpiryMessage;
      this.keepLiveIntervalSeconds = keepLiveIntervalSeconds;
      this.actionUrlPath = actionUrlPath;
      this.keepLiveUrlPath = keepLiveUrlPath;
      this.glueViewUrlPath = glueViewUrlPath;
      this.minimumKeepLiveIntervalSeconds = 120;
    }
  }
  var config_default = GlueConfig;

  // client_js/django_glue.js
  var Glue = new client_default;
  window.Glue = Glue;
  window.GlueConfig = config_default;
  window.GlueHttp = http_default;
})();
