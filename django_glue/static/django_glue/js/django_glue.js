(() => {
  // client_js/src/proxies/base.js
  class BaseGlueProxy {
    _loaded = false;
    _loading = false;
    constructor({ http, name, contract, state = null, actions = null, namespace = "base" }) {
      this.http = http;
      this._namespace = namespace;
      this._name = name;
      this._contract = contract;
      this._state = state;
      this._actions = actions ? actions : contract.actions;
      this._defineDefaultActions();
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
      const listeners = this._listeners?.[type]?.[actionName] || [];
      for (const callback of listeners) {
        await callback(event);
      }
    }
    async _processAction(actionName, actionKwargs = null) {
      const event = {
        action: actionName,
        proxy: this,
        actionKwargs
      };
      await this.emitListeners("before", actionName, event);
      this._loading = true;
      try {
        const response = await this.http.sendActionRequest({
          name: this._name,
          action: actionName,
          actionKwargs,
          contract: this._contract,
          state: this._state
        });
        const responseData = response.data;
        if (this._state) {
          Object.assign(this._state, responseData.state);
        } else {
          this._state = responseData.state;
        }
        this._handleActionResponse(actionName, actionKwargs, responseData);
        const data = responseData.data !== undefined ? responseData.data : responseData;
        event.result = data;
        await this.emitListeners("after", actionName, event);
        return data;
      } catch (err) {
        event.error = err;
        await this.emitListeners("error", actionName, event);
        throw err;
      } finally {
        this._loading = false;
      }
    }
    _handleActionResponse(actionName, actionKwargs, response) {}
    _defineDefaultActions() {
      Object.entries(this._actions).forEach(([actionKey, action]) => {
        const [actionProvider, actionName] = actionKey.split(".").slice(0, 2);
        const accessPath = action.client_proxy_access_path;
        const accessPathParts = accessPath ? [accessPath.split("."), ""] : [""];
        let propertyTarget = this;
        accessPathParts.forEach((pathPart) => {
          if (pathPart) {
            propertyTarget[pathPart] = {
              _processAction: this._processAction.bind(this)
            };
            propertyTarget = propertyTarget[pathPart];
          }
          if (!(actionName in propertyTarget)) {
            Object.defineProperty(propertyTarget, actionName, {
              get: function() {
                return async (actionKwargs = null) => {
                  debugger;
                  return await this._processAction(actionKey, actionKwargs);
                };
              },
              enumerable: true,
              configurable: true
            });
          }
        });
      });
    }
  }
  var base_default = BaseGlueProxy;

  // client_js/src/proxies/form.js
  class GlueFormProxy extends base_default {
    _values = {};
    constructor({ http, name, contract, state, actions = null, namespace = "form" }) {
      super({ http, name, contract, state, actions, namespace });
      this._defineFields();
    }
    loadInstanceData() {
      if (this._state?.instance_data) {
        this._loaded = true;
        for (const fieldName of Object.keys(this._fields)) {
          this[fieldName] = this._state.instance_data[fieldName];
          this._fields[fieldName].value = this._state.instance_data[fieldName];
        }
      }
    }
    _defineModelChoiceField(fieldName, field) {
      field.__glue__choicesLoaded = false;
      field.__glue__loadingChoices = false;
      field.__glue__choicesCache = [];
      const proxy = this;
      Object.defineProperty(field, "choices", {
        get: async function() {
          if (!field.__glue__choicesLoaded && !field.__glue__loadingChoices) {
            field.__glue__loadingChoices = true;
            const response = await proxy._processAction("GlueFormProxy.foreign_key_choices", { field_name: fieldName });
            field.choices = response.response_payload;
            field.__glue__choicesLoaded = true;
            field.__glue__loadingChoices = false;
          }
          return field.__glue__choicesCache;
        },
        set: function(value) {
          field.__glue__choicesCache = value;
          field.__glue__choicesLoaded = true;
        },
        configurable: true
      });
      return field;
    }
    _defineFieldNameProperty(fieldName, field) {
      field = { ...field };
      if (["ModelChoiceField", "ModelMultipleChoiceField"].includes(field.type)) {
        field = this._defineModelChoiceField(fieldName, field);
      }
      Object.defineProperty(this, fieldName, {
        get: function() {
          if (!this._loaded && !this._state.instance_data) {
            if (!this._loading) {
              this._loading = true;
              this.load().then(() => {
                this.loadInstanceData();
                this._loading = false;
              });
            }
          }
          return this._values[fieldName];
        },
        set: function(value) {
          this._values[fieldName] = value;
          if (!this._state.instance_data) {
            this._state.instance_data = {};
          }
          this._state.instance_data[fieldName] = value;
        }
      });
      if (!field.hasOwnProperty("value")) {
        Object.defineProperty(field, "value", {
          get: function() {
            return this._values[fieldName];
          }.bind(this),
          set: function(val) {
            this._values[fieldName] = val;
            if (!this._state.instance_data)
              this._state.instance_data = {};
            this._state.instance_data[fieldName] = val;
          }.bind(this)
        });
      }
      if (!field.hasOwnProperty("errors")) {
        Object.defineProperty(field, "errors", {
          get: function() {
            return this._state._errors?.[fieldName];
          }.bind(this)
        });
      }
      this._fields[fieldName] = field;
      this._fields[fieldName]["name"] = fieldName;
    }
    _defineFields() {
      this._fields = {};
      Object.keys(this._fields).forEach((k) => delete this._fields[k]);
      Object.entries(this._contract.custom_data.allowed_fields).forEach(([fieldName, field]) => {
        if (!this.hasOwnProperty(fieldName)) {
          this._defineFieldNameProperty(fieldName, field);
        }
        Object.keys(this._fields[fieldName]).forEach((attributeName) => {
          this._updateErrorAttributesForField(fieldName);
        });
      });
      if (!this.hasOwnProperty("$fields")) {
        Object.defineProperty(this, "$fields", {
          get: function() {
            return this._fields;
          },
          set: (value) => {
            this._fields = value;
          }
        });
      }
    }
    _updateErrorAttributesForField(fieldName) {
      this._fields[fieldName][`has_errors`] = this._state._errors?.[fieldName]?.length > 0;
      this._fields[fieldName][`error_text`] = this._state._errors?.[fieldName]?.join(", ");
    }
    hasErrors(fieldName) {
      if (fieldName) {
        return Boolean(this._errors[fieldName] && this._errors[fieldName].length > 0);
      }
      return Object.keys(this._errors).length > 0;
    }
    _handleActionResponse(actionName, actionKwargs, response) {}
  }
  var form_default = GlueFormProxy;

  // client_js/src/proxies/model.js
  var _keyCounter = 0;

  class GlueModelProxy extends form_default {
    constructor({
      http,
      name,
      contract,
      state,
      actions = null,
      autoFetch = false,
      parentQuerySet = null,
      namespace = "model"
    }) {
      super({ http, name, contract, state, actions, autoFetch, namespace });
      if (this._state.instance_data) {
        this._defineExtraFields();
        this.loadInstanceData();
      }
      this.$key = `django-glue-${++_keyCounter}`;
      this._parent = parentQuerySet;
      this._pkFieldName = contract.custom_data?.pk_field_name || "id";
    }
    get pk() {
      let pk = this._contract.custom_data.target_pk;
      if (!pk) {
        pk = this._state.instance_data?.[this._pkFieldName];
      }
      return pk;
    }
    _defineExtraFields() {
      Object.keys(this._state.instance_data).forEach((fieldName) => {
        if (!(fieldName in this)) {
          this._defineFieldNameProperty(fieldName);
        }
      });
    }
    get _isNew() {
      return !this._pk;
    }
    _handleActionResponse(actionName, actionKwargs, response) {
      super._handleActionResponse(actionName, actionKwargs, response);
      if (this._state.instance_data) {
        this._defineExtraFields();
        for (const fieldName of Object.keys(this._state.instance_data)) {
          if (!(fieldName in this._fields)) {
            this[fieldName] = this._state.instance_data[fieldName];
          }
        }
      }
      if (this._parent) {
        this._parent.refresh();
      }
    }
  }
  var model_default = GlueModelProxy;

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
    async sendActionRequest({ name, action, actionKwargs = null, contract, state = null }) {
      const url = `${this._config.actionUrlPath}${name}/${action}/`;
      const formData = new FormData;
      formData.append("contract", JSON.stringify(contract));
      if (state) {
        const { files, data } = this._extractFiles(state);
        formData.append("state", JSON.stringify(data));
        Object.entries(files).forEach(([key, value]) => {
          const fieldKey = key.replace("instance_data.", "", 1);
          if (value instanceof FileList) {
            Array.from(value).forEach((file) => formData.append(fieldKey, file));
          } else if (Array.isArray(value)) {
            value.forEach((file) => formData.append(fieldKey, file));
          } else {
            formData.append(fieldKey, value);
          }
        });
      }
      if (actionKwargs) {
        formData.append("action_kwargs", JSON.stringify(actionKwargs));
      }
      return await this.sendFormPostRequest(url, formData);
    }
    _extractFiles(obj) {
      const files = {};
      const data = {};
      const extractFromValue = (value, key) => {
        if (value instanceof File || value instanceof Blob) {
          files[key] = value;
          return;
        } else if (value instanceof FileList) {
          files[key] = value;
          return;
        } else if (Array.isArray(value)) {
          const hasFiles = value.some((v) => v instanceof File || v instanceof Blob);
          if (hasFiles) {
            files[key] = value.filter((v) => v instanceof File || v instanceof Blob);
            const nonFiles = value.filter((v) => !(v instanceof File || v instanceof Blob));
            return nonFiles.length > 0 ? nonFiles : undefined;
          }
          return value;
        } else if (value && typeof value === "object") {
          const nested = this._extractFiles(value);
          Object.entries(nested.files).forEach(([k, v]) => {
            files[`${key}.${k}`] = v;
          });
          return Object.keys(nested.data).length > 0 ? nested.data : undefined;
        }
        return value;
      };
      Object.entries(obj).forEach(([key, value]) => {
        const result = extractFromValue(value, key);
        if (result !== undefined) {
          data[key] = result;
        }
      });
      return { files, data };
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
      let viewResponse = await this.http.sendRequest(this.http._config.glueViewUrlPath, {
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
      window.Glue.initializeProxies(viewResponse.data.proxy_registry_data, viewResponse.data.proxy_definitions);
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
    static proxies = {};
    static proxyClassesForSubjectTypes = {};
    model = {};
    querySet = {};
    form = {};
    template = {};
    function = {};
    _registerProxyAsProperty(name, { contract, state }) {
      let proxyClass = SUBJECT_TYPE_TO_PROXY_CLASS[contract.namespace];
      let proxy;
      if (contract.namespace === "function") {
        proxy = proxyClass.create({
          http: this.http,
          name,
          contract
        });
      } else {
        proxy = new proxyClass({
          http: this.http,
          name,
          contract,
          state
        });
      }
      this[contract.namespace][name] = proxy;
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
    init({ proxies, config = {} }) {
      this._config = config;
      this.http = new http_default(this._config);
      for (const [name, proxy] of Object.entries(proxies)) {
        this._registerProxyAsProperty(name, proxy);
      }
    }
    view(url, shared_payload = {}) {
      return new view_default(this.http, url, shared_payload);
    }
  }
  var client_default = GlueClient;

  // client_js/src/proxies/queryset.js
  class GlueQuerySetProxy extends base_default {
    _items = [];
    _queryParams = {};
    _prevQueryParams = {};
    constructor({ http, name, contract, state, actions = null, namespace = "queryset" }) {
      super({ http, name, contract, state, actions, namespace });
    }
    *[Symbol.iterator]() {
      yield* this._items;
    }
    buildChildModelProxy(item) {
      const pkFieldName = this._contract.custom_data.pk_field_name || "id";
      const proxy = new model_default({
        http: this.http,
        name: this._name,
        contract: this._contract,
        state: {
          instance_pk: item[pkFieldName],
          instance_data: item,
          errors: {},
          files: {}
        },
        parentQuerySet: this
      });
      const querySetProxy = this;
      Object.keys(proxy._actions).forEach((actionName) => {
        ["before", "after", "error"].forEach((type) => {
          proxy.addListener(actionName, (event) => {
            querySetProxy.emitListeners(type, actionName, event);
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
        await this._processAction("GlueQuerySetProxy.query_with_params", this._queryParams);
        this._prevQueryParams = this._queryParams;
        this._loaded = true;
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
      return this.addQueryParam("slice", { stop: idx });
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
    _handleActionResponse(actionName, actionKwargs, response) {
      if (this._state?.list_data) {
        this._items = this._state.list_data.map((item) => this.buildChildModelProxy(item));
      }
    }
  }
  var queryset_default = GlueQuerySetProxy;

  // client_js/src/proxies/template.js
  class GlueTemplateProxy extends base_default {
    static name = "template";
    constructor({ http, proxyUniqueName, proxyDefinition, sharedPayload = {} }) {
      super({ http, proxyUniqueName, proxyDefinition });
      this._sharedPayload = sharedPayload;
    }
    async _renderHtml(payload = {}) {
      const mergedPayload = {
        ...this._sharedPayload,
        ...payload
      };
      const response = await this._processAction("render_html", mergedPayload);
      return response.html;
    }
    async renderInnerHtml(targetElement, payload = {}) {
      targetElement.innerHTML = await this._renderHtml(payload);
    }
    async _renderInsertAdjacentHtml(targetElement, position, payload = {}) {
      const html = await this._renderHtml(payload);
      targetElement.insertAdjacentHTML(position, html);
    }
    async renderInsertAdjacentHtmlBeforeEnd(targetElement, payload = {}) {
      await this._renderInsertAdjacentHtml(targetElement, "beforeend", payload);
    }
    async renderInsertAdjacentHtmlAfterEnd(targetElement, payload = {}) {
      await this._renderInsertAdjacentHtml(targetElement, "afterend", payload);
    }
    async renderInsertAdjacentHtmlBeforeBegin(targetElement, payload = {}) {
      await this._renderInsertAdjacentHtml(targetElement, "beforebegin", payload);
    }
    async renderInsertAdjacentHtmlAfterBegin(targetElement, payload = {}) {
      await this._renderInsertAdjacentHtml(targetElement, "afterbegin", payload);
    }
    async renderOuterHtml(targetElement, payload = {}) {
      targetElement.outerHTML = await this._renderHtml(payload);
    }
  }
  var template_default = GlueTemplateProxy;

  // client_js/src/utils.js
  function isObject(val) {
    return Object.prototype.toString.call(val) === "[object Object]";
  }

  // client_js/src/proxies/function.js
  class GlueFunctionProxy extends base_default {
    constructor({ http, name, contract, namespace = "function" }) {
      super({ http, name, contract, namespace });
      this._params = contract.params || [];
    }
    static create({ http, name, contract }) {
      const instance = new GlueFunctionProxy({
        http,
        name,
        contract
      });
      const fn = async function(kwargs = {}) {
        if (!isObject(kwargs)) {
          throw Error("Must pass glue function arguments as fields in an object.");
        }
        const payload = {};
        instance._params.forEach((param) => {
          if (param.name in kwargs) {
            payload[param.name] = kwargs[param.name];
          }
        });
        const response = await instance._processAction("execute", payload);
        return response.result;
      };
      fn._name = name;
      fn._contract = contract;
      fn._params = instance._params;
      fn.addListener = instance.addListener.bind(instance);
      fn.removeListener = instance.removeListener.bind(instance);
      fn.clearListeners = instance.clearListeners.bind(instance);
      return fn;
    }
  }
  var function_default = GlueFunctionProxy;

  // client_js/src/proxies/index.js
  var SUBJECT_TYPE_TO_PROXY_CLASS = {
    model: model_default,
    form: form_default,
    querySet: queryset_default,
    template: template_default,
    function: function_default
  };
  window.BaseGlueProxy = base_default;
  window.GlueModelProxy = model_default;
  window.GlueQuerySetProxy = queryset_default;
  window.GlueFormProxy = form_default;
  window.GlueTemplateProxy = template_default;
  window.GlueFunctionProxy = function_default;

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
