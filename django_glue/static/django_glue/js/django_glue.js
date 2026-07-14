(() => {
  // client_js/src/proxies/base.js
  class BaseGlueProxy {
    _loaded = false;
    _loading = false;
    constructor({ http, name, policy, state = null, attributes = null, namespace = "base" }) {
      this.http = http;
      this._namespace = namespace;
      this._name = name;
      this._policy = policy;
      this._state = state;
      this._attributes = attributes ? attributes : policy.bound_attributes;
      this._defineAttributeProperties();
      this._listeners = {
        before: {},
        after: {},
        error: {}
      };
      this._onMessage = null;
    }
    onMessage(callback) {
      this._onMessage = callback;
      return this;
    }
    addListener(attributeName, callback, type = "after") {
      if (!this._listeners[type]) {
        throw new Error(`Invalid listener type: _${type}. Use 'before', 'after', or 'error'.`);
      }
      if (!this._listeners[type][attributeName]) {
        this._listeners[type][attributeName] = [];
      }
      this._listeners[type][attributeName].push(callback);
      return this;
    }
    removeListener(attributeName, callback, type = "after") {
      const listeners = this._listeners[type]?.[attributeName];
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
    async emitListeners(type, attributeName, event) {
      const listeners = this._listeners?.[type]?.[attributeName] || [];
      for (const callback of listeners) {
        await callback(event);
      }
    }
    async _processAttributeEvent(attributeName, eventKwargs = null) {
      const shortName = attributeName.split(".").pop();
      const event = {
        attribute: attributeName,
        proxy: this,
        eventKwargs
      };
      await this.emitListeners("before", shortName, event);
      this._loading = true;
      try {
        const response = await this.http.sendAttributeEventRequest({
          name: this._name,
          attribute: attributeName,
          eventKwargs,
          policy: this._policy,
          state: this._state
        });
        const responseData = response.data;
        this._handleEventResponse(attributeName, eventKwargs, responseData);
        await this._handleMessages(responseData, attributeName, eventKwargs);
        const data = responseData.result ?? {};
        event.result = data;
        await this.emitListeners("after", shortName, event);
        return data;
      } catch (err) {
        event.error = err;
        await this._handleExpiry(err, attributeName, eventKwargs);
        await this.emitListeners("error", shortName, event);
        await this._handleError(err, attributeName, eventKwargs);
        throw err;
      } finally {
        this._loading = false;
      }
    }
    async _handleError(error, attributeName, eventKwargs) {
      const handler = globalThis.Glue?._onError;
      if (!handler) {
        return;
      }
      await handler({
        error,
        proxy: this,
        attribute: attributeName,
        eventKwargs
      });
    }
    async _handleExpiry(error, attributeName, eventKwargs) {
      if (!this._isExpiryError(error)) {
        return;
      }
      const handler = globalThis.Glue?._onExpiry || this._defaultExpiryHandler;
      await handler({
        error,
        proxy: this,
        attribute: attributeName,
        eventKwargs
      });
    }
    _isExpiryError(error) {
      return error?.code === "proxy_policy_expired";
    }
    _defaultExpiryHandler() {
      globalThis.alert?.("Your session has expired. Please refresh the page.");
    }
    async _handleMessages(response, attributeName, eventKwargs) {
      const messages = response?.messages || [];
      if (!Array.isArray(messages) || messages.length === 0) {
        return;
      }
      const handler = this._onMessage || globalThis.Glue?._onMessage;
      if (!handler) {
        return;
      }
      await handler({
        messages,
        response,
        proxy: this,
        attribute: attributeName,
        eventKwargs
      });
    }
    _handleEventResponse(attributeName, eventKwargs, response) {
      if (response.policy) {
        this._policy = response.policy;
      }
      if (this._state) {
        if (this._state.instance_data && response.state.instance_data) {
          for (const key of Object.keys(this._state.instance_data)) {
            if (!(key in response.state.instance_data)) {
              delete this._state.instance_data[key];
            }
          }
          for (const [key, value] of Object.entries(response.state.instance_data)) {
            this._state.instance_data[key] = value;
          }
          for (const [key, value] of Object.entries(response.state)) {
            if (key !== "instance_data") {
              this._state[key] = value;
            }
          }
        } else {
          Object.assign(this._state, response.state);
        }
      } else {
        this._state = response.state;
      }
    }
    _defineAttributeProperties() {
      Object.entries(this._attributes).forEach(([attributePath, attribute]) => {
        const proxy = this;
        let target = proxy;
        const attributePartsParts = attributePath.split(".");
        for (let i = 1;i < attributePartsParts.length; i++) {
          const attributePart = attributePartsParts[i];
          if (i === attributePartsParts.length - 1) {
            target[attributePart] = async function(eventKwargs = null) {
              return await this._processAttributeEvent(attributePath, eventKwargs);
            };
          } else {
            target[attributePart] = target;
            target = target[attributePart];
          }
        }
      });
    }
  }
  var base_default = BaseGlueProxy;

  // client_js/src/proxies/form.js
  class GlueFormProxy extends base_default {
    static choicesCache = new Map;
    constructor({ http, name, policy, state, attributes = null, namespace = "form" }) {
      super({ http, name, policy, state, attributes, namespace });
      this._pkFieldName = policy.subject_details?.pk_field_name || "id";
      this._defineFields();
      this._refreshFieldErrorAttributes();
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
      const cacheKey = this._getChoicesCacheKey(fieldName, field);
      const cached = GlueFormProxy.choicesCache.get(cacheKey);
      field.__glue__choicesCacheKey = cacheKey;
      field.__glue__choicesLoaded = Boolean(cached?.loadedFields?.has("__str__"));
      field.__glue__loadingChoices = Boolean(cached?.promise && cached?.pendingFields?.has("__str__"));
      field.__glue__choicesData = cached?.data || [];
      const proxy = this;
      Object.defineProperty(field, "choices", {
        get: function() {
          proxy._ensureFieldChoices(fieldName, this);
          const cached2 = GlueFormProxy.choicesCache.get(this.__glue__choicesCacheKey);
          return cached2?.data || this.__glue__choicesData;
        },
        enumerable: true,
        configurable: true
      });
      field.buildChoices = function(...choiceFields) {
        return proxy._buildFieldChoices(fieldName, this, choiceFields);
      };
      return field;
    }
    _getChoicesCacheKey(fieldName, field) {
      const subject = this._policy.subject_details || {};
      return field.choices_cache_key || [
        subject.model_class_path,
        subject.form_class_path,
        field.choice_model_path,
        fieldName
      ].filter(Boolean).join(":") || `${field.type}:${fieldName}`;
    }
    _ensureFieldChoices(fieldName, field, choiceFields = []) {
      const cacheKey = this._getChoicesCacheKey(fieldName, field);
      const cached = this._getOrCreateChoicesCache(cacheKey, field);
      const requiredFields = this._normalizeChoiceFields(choiceFields);
      const missingFields = requiredFields.filter((choiceField) => !cached.loadedFields.has(choiceField));
      if (missingFields.length === 0) {
        this._applyCachedChoicesToField(field, cached);
        return cached.promise || Promise.resolve(cached.data);
      }
      if (cached.promise) {
        field.__glue__loadingChoices = true;
        if (missingFields.every((choiceField) => cached.pendingFields.has(choiceField))) {
          return cached.promise;
        }
        return cached.promise.then(() => this._ensureFieldChoices(fieldName, field, choiceFields));
      }
      field.__glue__loadingChoices = true;
      missingFields.forEach((choiceField) => cached.pendingFields.add(choiceField));
      const promise = this.foreign_key_choices({
        field_name: fieldName,
        choice_fields: missingFields.filter((choiceField) => !["pk", "__str__"].includes(choiceField))
      }).then((result) => {
        const choices = Array.isArray(result) ? result : [];
        this._cacheFieldChoices(fieldName, choices, missingFields);
        return cached.data;
      }).finally(() => {
        missingFields.forEach((choiceField) => cached.pendingFields.delete(choiceField));
        cached.promise = null;
        field.__glue__loadingChoices = false;
      });
      cached.promise = promise;
      return promise;
    }
    _buildFieldChoices(fieldName, field, choiceFields = []) {
      this._ensureFieldChoices(fieldName, field, choiceFields);
      const cacheKey = this._getChoicesCacheKey(fieldName, field);
      return GlueFormProxy.choicesCache.get(cacheKey)?.data || [];
    }
    _normalizeChoiceFields(choiceFields = []) {
      return ["pk", "__str__", ...choiceFields].filter((choiceField, index, fields) => {
        return choiceField && fields.indexOf(choiceField) === index;
      });
    }
    _getOrCreateChoicesCache(cacheKey, field) {
      let cached = GlueFormProxy.choicesCache.get(cacheKey);
      if (!cached) {
        cached = {
          data: field.__glue__choicesData || [],
          loadedFields: new Set,
          pendingFields: new Set,
          promise: null
        };
        GlueFormProxy.choicesCache.set(cacheKey, cached);
      }
      return cached;
    }
    _applyCachedChoicesToField(field, cached) {
      field.__glue__choicesLoaded = cached.loadedFields.has("__str__");
      field.__glue__loadingChoices = Boolean(cached.promise);
      field.__glue__choicesData = cached.data;
    }
    _cacheFieldChoices(fieldName, choices, choiceFields = []) {
      const field = this._fields[fieldName];
      if (!field)
        return;
      const cacheKey = this._getChoicesCacheKey(fieldName, field);
      const cached = this._getOrCreateChoicesCache(cacheKey, field);
      if (Array.isArray(choices)) {
        choices.forEach((choice) => this._mergeChoice(cached.data, choice));
      }
      this._normalizeChoiceFields(choiceFields).forEach((choiceField) => cached.loadedFields.add(choiceField));
      this._applyCachedChoicesToField(field, cached);
    }
    _mergeChoice(choices, choice) {
      if (!choice || typeof choice !== "object")
        return;
      const existing = choices.find((item) => item.pk === choice.pk);
      if (existing) {
        Object.assign(existing, choice);
      } else {
        choices.push(choice);
      }
    }
    async _loadFieldChoices(fieldName, field) {
      if (field.__glue__choicesLoaded || field.__glue__loadingChoices) {
        return;
      }
      await this._ensureFieldChoices(fieldName, field);
    }
    _setFieldChoices(fieldName, choices, choiceFields = []) {
      const field = this._fields[fieldName];
      if (!field)
        return;
      this._cacheFieldChoices(fieldName, choices, choiceFields);
    }
    get pk() {
      let pk = this._policy.subject_details.target_pk;
      if (!pk) {
        pk = this._state.instance_data?.[this._pkFieldName];
      }
      return pk;
    }
    _defineFieldNameProperty(fieldName, field) {
      field = { ...field || {} };
      if (field.type === "ModelMultipleChoiceField") {
        if (!this._state.instance_data) {
          this._state.instance_data = {};
        }
        if (this._state.instance_data[fieldName] === undefined || this._state.instance_data[fieldName] === null) {
          this._state.instance_data[fieldName] = [];
        }
      }
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
          return this._state.instance_data[fieldName];
        },
        set: function(value) {
          if (!this._state.instance_data) {
            this._state.instance_data = {};
          }
          this._state.instance_data[fieldName] = value;
        }
      });
      if (!field.hasOwnProperty("value")) {
        Object.defineProperty(field, "value", {
          get: function() {
            return this._state.instance_data[fieldName];
          }.bind(this),
          set: function(val) {
            if (!this._state.instance_data)
              this._state.instance_data = {};
            this._state.instance_data[fieldName] = val;
          }.bind(this)
        });
      }
      if (!field.hasOwnProperty("errors")) {
        Object.defineProperty(field, "errors", {
          get: function() {
            return this._state.errors?.[fieldName];
          }.bind(this),
          enumerable: true,
          configurable: true
        });
      }
      field.hasErrors = false;
      field.errorText = "";
      this._fields[fieldName] = field;
      this._fields[fieldName]["name"] = fieldName;
    }
    _defineFields() {
      this._fields = {};
      this._fields[this.pkFieldName] = this.pk;
      Object.keys(this._fields).forEach((k) => delete this._fields[k]);
      Object.entries(this._policy.subject_details.included_fields).forEach(([fieldName, field]) => {
        if (!this.hasOwnProperty(fieldName)) {
          this._defineFieldNameProperty(fieldName, field);
        }
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
    _refreshFieldErrorAttributes() {
      Object.keys(this._fields).forEach((fieldName) => {
        const field = this._fields[fieldName];
        field.hasErrors = this._state?.errors?.[fieldName]?.length > 0;
        field.errorText = this._state?.errors?.[fieldName]?.join(", ");
      });
    }
    hasErrors(fieldName) {
      if (fieldName) {
        return Boolean(this._state?.errors?.[fieldName] && this._state.errors[fieldName].length > 0);
      }
      return Object.keys(this._state?.errors || {}).length > 0;
    }
    _handleEventResponse(attributeName, eventKwargs, response) {
      super._handleEventResponse(attributeName, eventKwargs, response);
      if (attributeName.endsWith("foreign_key_choices") && eventKwargs?.field_name) {
        const fieldName = eventKwargs.field_name;
        this._setFieldChoices(fieldName, response.result, eventKwargs.choice_fields || []);
      }
      this._refreshFieldErrorAttributes();
      if (!this.hasErrors()) {
        this.loadInstanceData();
      }
    }
  }
  var form_default = GlueFormProxy;

  // client_js/src/proxies/model.js
  var _keyCounter = 0;

  class GlueModelProxy extends form_default {
    constructor({
      http,
      name,
      policy,
      state,
      attributes = null,
      autoFetch = false,
      parentQuerySet = null,
      namespace = "model"
    }) {
      super({ http, name, policy, state, attributes, autoFetch, namespace });
      if (this._state.instance_data) {
        this._defineExtraFields();
        this.loadInstanceData();
      }
      this.$key = `django-glue-${++_keyCounter}`;
      this._parent = parentQuerySet;
      this._pkFieldName = policy.subject_details?.pk_field_name || "id";
    }
    get pk() {
      let pk = this._policy.subject_details.target_pk;
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
      return !this.pk;
    }
    _handleEventResponse(attributeName, eventKwargs, response) {
      super._handleEventResponse(attributeName, eventKwargs, response);
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

  // client_js/src/proxies/queryset.js
  class GlueQuerySetProxy extends base_default {
    _items = [];
    _queryParams = {};
    _prevQueryParams = {};
    constructor({ http, name, policy, state, attributes = null, namespace = "querySet" }) {
      super({ http, name, policy, state, attributes, namespace });
    }
    *[Symbol.iterator]() {
      yield* this._items;
    }
    buildChildModelProxy(item) {
      const pkFieldName = this._policy.subject_details.pk_field_name || "id";
      if (!item.__policy__) {
        throw new Error(`Child proxy item missing __policy__ for pk ${item[pkFieldName]}`);
      }
      const childName = item.__policy__.name || `${this._name}__${item[pkFieldName]}`;
      const querySetProxy = this;
      const proxy = new model_default({
        http: this.http,
        name: childName,
        policy: item.__policy__,
        state: {
          namespace: "model",
          instance_data: item,
          errors: {}
        }
      });
      proxy.addListener("delete", async (event) => {
        await this.emitListeners("after", "delete", event);
        await this.refresh();
      }, "after");
      proxy.addListener("delete", async (event) => {
        await this.emitListeners("error", "delete", event);
      }, "error");
      proxy.addListener("save", async (event) => {
        await this.emitListeners("after", "save", event);
        if (!event.proxy.hasErrors()) {
          await this.refresh();
        }
      }, "after");
      proxy.addListener("save", async (event) => {
        await this.emitListeners("error", "save", event);
      }, "error");
      globalThis.Glue["model"][proxy._name] = proxy;
      return proxy;
    }
    async queryWithParams(queryParams = null) {
      if (queryParams) {
        this._queryParams = queryParams;
      }
      if (!this._loaded || !this._isEqual(this._prevQueryParams, this._queryParams)) {
        await this._processAttributeEvent("GlueQuerySetProxy.query_with_params", this._queryParams);
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
      const defaults = await this._processAttributeEvent("GlueQuerySetProxy.new");
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
    _handleEventResponse(attributeName, eventKwargs, response) {
      super._handleEventResponse(attributeName, eventKwargs, response);
      if (this._state?.list_data) {
        this._items = this._state.list_data.map((item) => this.buildChildModelProxy(item));
      }
    }
  }
  var queryset_default = GlueQuerySetProxy;

  // client_js/src/proxies/template.js
  class GlueTemplateProxy extends base_default {
    static name = "template";
    constructor({ http, name, policy, state = null, sharedPayload = {} }) {
      super({ http, name, policy, state });
      this._sharedPayload = sharedPayload;
    }
    async _renderHtml(payload = {}) {
      const mergedPayload = {
        ...this._sharedPayload,
        ...payload
      };
      const response = await this.render_html(mergedPayload);
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
    constructor({ http, name, policy, namespace = "function" }) {
      super({ http, name, policy, namespace });
      this._params = policy.subject_details.params || [];
    }
    static create({ http, name, policy }) {
      const instance = new GlueFunctionProxy({
        http,
        name,
        policy
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
        const response = await instance.execute(payload);
        return response.result;
      };
      fn._name = name;
      fn._policy = policy;
      fn._params = instance._params;
      fn.addListener = instance.addListener.bind(instance);
      fn.removeListener = instance.removeListener.bind(instance);
      fn.clearListeners = instance.clearListeners.bind(instance);
      fn.onMessage = instance.onMessage.bind(instance);
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

  // client_js/src/errors.js
  class GlueHttpError extends Error {
    constructor({ message, status = null, code = null, payload = null, responseBody = "" }) {
      super(`An error occurred when sending a glue http request: ${message}`);
      this.name = "GlueHttpError";
      this.status = status;
      this.code = code;
      this.payload = payload;
      this.details = payload?.details || {};
      this.responseBody = responseBody;
      this.isGlueError = Boolean(code);
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
          throw await this._buildRequestError(response);
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
    async _buildRequestError(response) {
      const body = await response.text();
      let payload = null;
      try {
        payload = JSON.parse(body);
      } catch (_) {}
      const errorData = payload?.error;
      const message = errorData?.message || body;
      return new GlueHttpError({
        message,
        status: response.status,
        code: errorData?.code,
        payload: errorData || null,
        responseBody: body
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
    async sendAttributeEventRequest({ name, attribute, eventKwargs = null, policy, state = null }) {
      const url = `${this._config.attributeEventUrlPath}${name}/${attribute}/`;
      const formData = new FormData;
      formData.append("policy", JSON.stringify(policy));
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
      if (eventKwargs) {
        formData.append("event_kwargs", JSON.stringify(eventKwargs));
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
      window.Glue.init({
        proxies: viewResponse.data.proxies,
        config: this.http._config
      });
      return viewResponse.data.html;
    }
    _htmlToFragment(html) {
      const template = document.createElement("template");
      template.innerHTML = html;
      return template.content;
    }
    async renderInnerHtml(target_element, payload = {}) {
      const html = await this._fetchView(payload);
      target_element.replaceChildren(this._htmlToFragment(html));
    }
    async _renderInsertAdjacentHtml(target_element, position, payload = {}) {
      const html = await this._fetchView(payload);
      const fragment = this._htmlToFragment(html);
      if (position === "beforeend") {
        target_element.append(fragment);
      } else if (position === "afterbegin") {
        target_element.prepend(fragment);
      } else if (position === "beforebegin") {
        target_element.before(fragment);
      } else if (position === "afterend") {
        target_element.after(fragment);
      } else {
        throw new Error(`Invalid insert position: ${position}`);
      }
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
      const html = await this._fetchView(payload);
      target_element.replaceWith(this._htmlToFragment(html));
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
    _onMessage = null;
    _onExpiry = null;
    _onError = this._defaultErrorHandler;
    onMessage(callback) {
      this._onMessage = callback;
      return this;
    }
    onExpiry(callback) {
      this._onExpiry = callback;
      return this;
    }
    onError(callback) {
      this._onError = callback;
      return this;
    }
    _defaultErrorHandler({ error, proxy, attribute }) {
      console.error("[Django Glue] Bound attribute event failed", {
        error,
        proxy,
        attribute
      });
    }
    _registerProxyAsProperty(name, { policy, state }) {
      let proxyClass = SUBJECT_TYPE_TO_PROXY_CLASS[policy.subject_details.namespace];
      let proxy;
      if (policy.subject_details.namespace === "function") {
        proxy = proxyClass.create({
          http: this.http,
          name,
          policy
        });
      } else {
        proxy = new proxyClass({
          http: this.http,
          name,
          policy,
          state
        });
      }
      this[policy.subject_details.namespace][name] = proxy;
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

  // client_js/src/config.js
  class GlueConfig {
    constructor({
      requestTimeoutSeconds = 30,
      attributeEventUrlPath,
      glueViewUrlPath
    }) {
      this.requestTimeoutSeconds = requestTimeoutSeconds;
      this.attributeEventUrlPath = attributeEventUrlPath;
      this.glueViewUrlPath = glueViewUrlPath;
    }
  }
  var config_default = GlueConfig;

  // client_js/django_glue.js
  var Glue = new client_default;
  window.Glue = Glue;
  window.GlueConfig = config_default;
  window.GlueHttp = http_default;
  window.GlueHttpError = GlueHttpError;
})();
