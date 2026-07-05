(() => {
  // client_js/src/proxies/base.js
  class BaseGlueProxy {
    static name = "baseGlueProxy";
    constructor({ http, proxyUniqueName, proxyDefinition, actions = null }) {
      this.http = http;
      this._uniqueName = proxyUniqueName;
      this._proxyDefinition = proxyDefinition;
      this._actions = actions ? actions : proxyDefinition.actions;
      this._defineCustomActions();
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
    async _processAction(actionName, actionKwargs = null, proxyState = null) {
      const event = {
        action: actionName,
        proxy: this,
        actionKwargs
      };
      await this.emitListeners("before", actionName, event);
      try {
        const response = await this.http.sendActionRequest({
          uniqueName: this._uniqueName,
          action: actionName,
          actionKwargs,
          proxyDefinition: this._proxyDefinition,
          proxyState
        });
        const responseData = response.data;
        if (responseData.proxy_state) {
          this._handleResponseProxyState(responseData.proxy_state);
        }
        const data = responseData.data !== undefined ? responseData.data : responseData;
        event.result = data;
        await this.emitListeners("after", actionName, event);
        return data;
      } catch (err) {
        event.error = err;
        await this.emitListeners("error", actionName, event);
        throw err;
      }
    }
    _handleResponseProxyState(proxyState) {}
    async _defaultProcessAction(actionName, actionKwargs = null) {
      return await this._processAction(actionName, actionKwargs);
    }
    _defineCustomActions() {
      Object.keys(this._actions).forEach((actionName) => {
        if (!(actionName in this)) {
          this[actionName] = async (actionKwargs = null) => {
            return await this._defaultProcessAction(actionName, actionKwargs);
          };
        }
      });
    }
  }
  var base_default = BaseGlueProxy;

  // client_js/src/proxies/form.js
  class GlueFormProxy extends base_default {
    static name = "form";
    constructor({ http, proxyUniqueName, proxyDefinition, actions = null }) {
      super({ http, proxyUniqueName, proxyDefinition, actions });
      this._values = { ...this._proxyDefinition.initial || {} };
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
          fieldData.__glue__choicesLoaded = true;
          return data;
        }).finally(() => {
          fieldData.__glue__loadingChoices = false;
        });
        return fieldData.__glue__choicesPromise;
      }.bind(this);
      fieldData.choices = async function() {
        if (!fieldData.__glue__choicesLoaded) {
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
      Object.entries(this._proxyDefinition.fields).forEach(([fieldName, fieldData]) => {
        this._defineFieldNameProperty(fieldName);
        fieldData = { ...fieldData };
        if (["ModelChoiceField", "ModelMultipleChoiceField"].includes(fieldData.type)) {
          fieldData = this._defineModelChoiceField(fieldName, fieldData);
        }
        this._fields[fieldName] = fieldData;
        this._fields[fieldName]["name"] = fieldName;
        if (!fieldData.hasOwnProperty("value")) {
          Object.defineProperty(fieldData, "value", {
            get: function() {
              return this._values?.[fieldName];
            }.bind(this),
            set: function(val) {
              if (!this._values)
                this._values = {};
              this._values[fieldName] = val;
            }.bind(this)
          });
        }
        if (!fieldData.hasOwnProperty("errors")) {
          Object.defineProperty(fieldData, "errors", {
            get: function() {
              return this._errors?.[fieldName];
            }.bind(this)
          });
        }
        Object.keys(this._fields[fieldName]).forEach((attributeName) => {
          this._updateErrorAttributesForField(fieldName);
        });
      });
    }
    async _processAction(actionName, actionKwargs = null, proxyState = null) {
      const formProxyState = {
        ...proxyState || {},
        form_values: this._values || {}
      };
      return await base_default.prototype._processAction.call(this, actionName, actionKwargs, formProxyState);
    }
    _handleResponseProxyState(proxyState) {
      if (proxyState.errors) {
        this._updateErrors(proxyState.errors);
      }
      if (proxyState.form_values) {
        this._values = { ...this._values, ...proxyState.form_values };
      }
    }
    async get() {
      const data = await super._processAction("get");
      this._values = data;
      this._loading = false;
      this._loaded = true;
      return data;
    }
    _updateErrorAttributesForField(fieldName) {
      this._fields[fieldName][`has_errors`] = this._errors[fieldName]?.length > 0;
      this._fields[fieldName][`error_text`] = this._errors[fieldName]?.join(", ");
    }
    _updateErrors(errors) {
      this._errors = errors || {};
      Object.keys(this._fields).forEach((fieldName) => {
        this._updateErrorAttributesForField(fieldName);
      });
    }
    async validate() {
      const result = await this._processAction("validate");
      this._updateErrors(result.errors);
      return result;
    }
    async save() {
      const result = await this._processAction("save");
      this._updateErrors(result.errors);
      if (result.success) {
        this._clearErrors();
        this.get();
      }
      return result;
    }
    async process(actionKwargs = null) {
      const result = await this._processAction("process", actionKwargs);
      this._updateErrors(this._errors);
      return result;
    }
    hasErrors(fieldName) {
      if (fieldName) {
        return Boolean(this._errors[fieldName] && this._errors[fieldName].length > 0);
      }
      return Object.keys(this._errors).length > 0;
    }
    _clearErrors() {
      this._errors = {};
    }
  }
  var form_default = GlueFormProxy;

  // client_js/src/proxies/model.js
  var _keyCounter = 0;

  class GlueModelProxy extends form_default {
    static name = "model";
    constructor({
      http,
      proxyUniqueName,
      proxyDefinition,
      actions = null,
      autoFetch = false,
      values = null,
      parentQuerySet = null
    }) {
      super({ http, proxyUniqueName, proxyDefinition, actions, autoFetch });
      this._values = values;
      if (values) {
        this._defineExtraFields();
      }
      this.$key = `django-glue-${++_keyCounter}`;
      this._parent = parentQuerySet;
      this._pkFieldName = proxyDefinition.pk_field_name || "id";
    }
    get _pk() {
      return this._values?.[this._pkFieldName];
    }
    _defineExtraFields() {
      Object.keys(this._values).forEach((fieldName) => {
        if (!(fieldName in this)) {
          this._defineFieldNameProperty(fieldName);
        }
      });
    }
    get _isNew() {
      return !this._pk;
    }
    async get() {
      const data = await this._processAction("get");
      this._values = data;
      this._loading = false;
      this._loaded = true;
    }
    async _processAction(actionName, actionKwargs = null, proxyState = null) {
      const modelProxyState = {
        ...proxyState || {},
        instance_pk: this._pk,
        form_values: this._values || {}
      };
      if (this._parent) {
        return await this._parent._processAction(actionName, actionKwargs, modelProxyState);
      } else {
        return await form_default.prototype._processAction.call(this, actionName, actionKwargs, modelProxyState);
      }
    }
    async delete() {
      if (this._isNew && this._parent) {
        await this._parent.refresh();
        return { success: true };
      }
      const result = await this._processAction("delete");
      if (this._parent) {
        await this._parent.refresh();
      }
      return result;
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
    async sendActionRequest({ uniqueName, action, actionKwargs = null, proxyDefinition, proxyState = null }) {
      const url = `${this._config.actionUrlPath}${uniqueName}/${action}/`;
      const formData = new FormData;
      formData.append("proxy_definition", JSON.stringify(proxyDefinition));
      if (proxyState) {
        const { files, data } = this._extractFiles(proxyState);
        formData.append("proxy_state", JSON.stringify(data));
        Object.entries(files).forEach(([key, value]) => {
          if (value instanceof FileList) {
            Array.from(value).forEach((file) => formData.append(key, file));
          } else if (Array.isArray(value)) {
            value.forEach((file) => formData.append(key, file));
          } else {
            formData.append(key, value);
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
    static proxyDefinitions = {};
    static proxyClassesForSubjectTypes = {};
    static proxyRegistry = {};
    model = {};
    querySet = {};
    form = {};
    template = {};
    function = {};
    _keepLiveIntervalHandle = null;
    _defineProxyUniqueNameAsPropertyFromDefinition(proxyUniqueName, proxyDefinition) {
      const { subject_type: subjectType } = proxyDefinition;
      let proxyClass = SUBJECT_TYPE_TO_PROXY_CLASS[subjectType];
      if (!(proxyClass.name in this)) {
        this[proxyClass.name] = {};
      }
      let proxy;
      if (subjectType === "Function") {
        proxy = proxyClass.create({
          http: this.http,
          proxyUniqueName,
          proxyDefinition
        });
      } else {
        proxy = new proxyClass({
          http: this.http,
          proxyUniqueName,
          proxyDefinition
        });
      }
      this[proxyClass.name][proxyUniqueName] = proxy;
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
          ...this.form,
          ...this.template,
          ...this.function
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
      proxyDefinitions,
      config = {}
    }) {
      this._config = config;
      this.http = new http_default(this._config);
      this.initializeProxies(proxyRegistryFromSession, proxyDefinitions);
    }
    initializeProxies(proxyRegistryFromSession, proxyDefinitions) {
      for (const [proxyUniqueName, proxyDefinition] of Object.entries(proxyDefinitions)) {
        this._defineProxyUniqueNameAsPropertyFromDefinition(proxyUniqueName, proxyDefinition);
      }
      Object.assign(GlueClient.proxyRegistry, proxyRegistryFromSession);
      Object.assign(GlueClient.proxyDefinitions, proxyDefinitions);
      this._initializeKeepLivePulse();
    }
    view(url, shared_payload = {}) {
      return new view_default(this.http, url, shared_payload);
    }
  }
  var client_default = GlueClient;

  // client_js/src/proxies/queryset.js
  class GlueQuerySetProxy extends base_default {
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
      const proxy = new model_default({
        http: this.http,
        proxyUniqueName: this._uniqueName,
        proxyDefinition: client_default.proxyDefinitions[this._uniqueName],
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
    async save(data) {
      const result = await this._processAction("save", data);
      await this.refresh();
      return result;
    }
    async delete(params) {
      const result = await this._processAction("delete", params);
      await this.refresh();
      return result;
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
    static name = "function";
    constructor({ http, proxyUniqueName, proxyDefinition }) {
      super({ http, proxyUniqueName, proxyDefinition });
      this._params = proxyDefinition.params || [];
    }
    static create({ http, proxyUniqueName, proxyDefinition }) {
      const instance = new GlueFunctionProxy({
        http,
        proxyUniqueName,
        proxyDefinition
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
      fn._uniqueName = proxyUniqueName;
      fn._proxyDefinition = proxyDefinition;
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
    Model: model_default,
    ModelForm: form_default,
    QuerySet: queryset_default,
    BaseForm: form_default,
    Template: template_default,
    Function: function_default
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
