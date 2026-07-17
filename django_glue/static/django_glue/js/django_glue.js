(() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __moduleCache = /* @__PURE__ */ new WeakMap;
  var __toCommonJS = (from) => {
    var entry = __moduleCache.get(from), desc;
    if (entry)
      return entry;
    entry = __defProp({}, "__esModule", { value: true });
    if (from && typeof from === "object" || typeof from === "function")
      __getOwnPropNames(from).map((key) => !__hasOwnProp.call(entry, key) && __defProp(entry, key, {
        get: () => from[key],
        enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
      }));
    __moduleCache.set(from, entry);
    return entry;
  };
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, {
        get: all[name],
        enumerable: true,
        configurable: true,
        set: (newValue) => all[name] = () => newValue
      });
  };

  // client_js/django_glue.js
  var exports_django_glue = {};
  __export(exports_django_glue, {
    parseJsonScriptById: () => parseJsonScriptById,
    GlueClient: () => client_default
  });

  // client_js/src/config.js
  class GlueConfig {
    constructor(config = {}) {
      const urls = config.urls || {};
      this.attributeUrlPath = urls.callable_attribute || "/__dg__/callable_attribute/";
      this.glueViewUrlPath = urls.glue_view || "/__dg__/glue_view/";
      this.requestTimeoutSeconds = config.requestTimeoutSeconds || 30;
    }
  }
  var config_default = GlueConfig;

  // client_js/src/errors.js
  class GlueHttpError extends Error {
    constructor({ message, status, code = null, payload = null, responseBody = null }) {
      super(message);
      this.name = "GlueHttpError";
      this.status = status;
      this.code = code;
      this.payload = payload;
      this.responseBody = responseBody;
    }
  }

  class GlueProxyError extends Error {
    constructor(message) {
      super(message);
      this.name = "GlueProxyError";
    }
  }

  // client_js/src/utils.js
  function isPlainObject(value) {
    return Object.prototype.toString.call(value) === "[object Object]";
  }
  function cloneValue(value) {
    if (value === null || value === undefined) {
      return value;
    }
    if (value instanceof Date) {
      return new Date(value);
    }
    if (Array.isArray(value)) {
      return value.map((item) => cloneValue(item));
    }
    if (isPlainObject(value)) {
      return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, cloneValue(item)]));
    }
    return value;
  }
  function parseFieldValue(field, value) {
    if (value === null || value === undefined || value === "" || value instanceof Date) {
      return value;
    }
    const type = field?.type;
    if (type === "DateField") {
      return new Date(`${value}T00:00:00`);
    }
    if (["DateTimeField", "SplitDateTimeField"].includes(type)) {
      return new Date(value);
    }
    return value;
  }
  function serializeValue(value) {
    if (value instanceof Date) {
      return value.toISOString();
    }
    if (Array.isArray(value)) {
      return value.map((item) => serializeValue(item));
    }
    if (isPlainObject(value)) {
      return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, serializeValue(item)]));
    }
    return value;
  }
  function parseJsonScriptById(scriptId) {
    return JSON.parse(document.getElementById(scriptId).textContent);
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
          if (cookie.substring(0, name.length + 1) === `${name}=`) {
            return decodeURIComponent(cookie.substring(name.length + 1));
          }
        }
      }
      return null;
    }
    async sendRequest(url, requestOptions = {}) {
      const timeoutSeconds = requestOptions.timeoutSeconds ?? this._config.requestTimeoutSeconds;
      const controller = new AbortController;
      const timeoutId = setTimeout(() => controller.abort(), timeoutSeconds * 1000);
      const headers = {};
      if (requestOptions.contentType && requestOptions.contentType !== "multipart/form-data") {
        headers["Content-Type"] = requestOptions.contentType;
      }
      if (requestOptions.csrfProtected !== false) {
        headers["X-CSRFToken"] = this.getCookie("csrftoken");
      }
      try {
        const response = await fetch(url, {
          method: requestOptions.method || "GET",
          body: requestOptions.body,
          headers,
          signal: controller.signal
        });
        if (!response.ok) {
          throw await this._buildRequestError(response);
        }
        return {
          ok: response.ok,
          body: await response.clone().text(),
          httpResponse: response,
          data: await response.json()
        };
      } finally {
        clearTimeout(timeoutId);
      }
    }
    async sendFormPostRequest(url, data, csrfProtected = true) {
      return await this.sendRequest(url, {
        body: data,
        method: "POST",
        contentType: "multipart/form-data",
        csrfProtected
      });
    }
    async sendAttributeRequest({ name, policy, state = null, attribute, kwargs = {} }) {
      const formData = new FormData;
      const { files, data } = this._extractFiles(serializeValue(state || {}));
      formData.append("policy", JSON.stringify(policy));
      formData.append("state", JSON.stringify(data));
      formData.append("attribute", attribute);
      formData.append("kwargs", JSON.stringify(kwargs));
      Object.entries(files).forEach(([key, value]) => {
        if (value instanceof FileList) {
          Array.from(value).forEach((file) => formData.append(key, file));
        } else if (Array.isArray(value)) {
          value.forEach((file) => formData.append(key, file));
        } else {
          formData.append(key, value);
        }
      });
      return await this.sendFormPostRequest(`${this._config.attributeUrlPath}${name}/${attribute}/`, formData);
    }
    _extractFiles(obj) {
      const files = {};
      const data = {};
      const extractFromValue = (value, key) => {
        if (value instanceof File || value instanceof Blob || value instanceof FileList) {
          files[key] = value;
          return;
        }
        if (Array.isArray(value)) {
          const hasFiles = value.some((item) => item instanceof File || item instanceof Blob);
          if (!hasFiles) {
            return value;
          }
          files[key] = value.filter((item) => item instanceof File || item instanceof Blob);
          const nonFiles = value.filter((item) => !(item instanceof File || item instanceof Blob));
          return nonFiles.length > 0 ? nonFiles : undefined;
        }
        if (value && typeof value === "object") {
          const nested = this._extractFiles(value);
          Object.entries(nested.files).forEach(([nestedKey, fileValue]) => {
            files[`${key}.${nestedKey}`] = fileValue;
          });
          return Object.keys(nested.data).length > 0 ? nested.data : undefined;
        }
        return value;
      };
      Object.entries(obj || {}).forEach(([key, value]) => {
        const extracted = extractFromValue(value, key);
        if (extracted !== undefined) {
          data[key] = extracted;
        }
      });
      return { files, data };
    }
    async _buildRequestError(response) {
      const body = await response.text();
      let payload = null;
      try {
        payload = JSON.parse(body);
      } catch (_) {}
      const errorData = payload?.error;
      return new GlueHttpError({
        message: errorData?.message || body,
        status: response.status,
        code: errorData?.code,
        payload: errorData || null,
        responseBody: body
      });
    }
  }
  var http_default = GlueHttp;

  // client_js/src/view.js
  class GlueView {
    constructor(http, url, sharedPayload = {}) {
      this.http = http;
      this.url = new URL(url, window.location.origin).pathname;
      this.sharedPayload = sharedPayload;
    }
    async get(payload = {}) {
      return await this._fetchView(payload, "GET");
    }
    async post(payload = {}) {
      return await this._fetchView(payload, "POST");
    }
    async renderInnerHtml(target, payload = {}) {
      const element = this._resolveElement(target);
      const html = await this.post(payload);
      element.replaceChildren(this._htmlToFragment(html));
      return html;
    }
    async renderOuterHtml(target, payload = {}) {
      const element = this._resolveElement(target);
      const html = await this.post(payload);
      element.replaceWith(this._htmlToFragment(html));
      return html;
    }
    async _fetchView(payload = {}, method = "POST") {
      const response = await this.http.sendRequest(this.http._config.glueViewUrlPath, {
        method: "POST",
        contentType: "application/json",
        csrfProtected: true,
        body: JSON.stringify({
          url_path: this.url,
          method,
          view_payload: {
            ...this.sharedPayload,
            ...payload
          }
        })
      });
      globalThis.Glue.loadManifests(response.data?.manifest_list || []);
      return response.data?.html || "";
    }
    _resolveElement(target) {
      return typeof target === "string" ? document.querySelector(target) : target;
    }
    _htmlToFragment(html) {
      const template = document.createElement("template");
      template.innerHTML = html;
      return template.content;
    }
  }
  var view_default = GlueView;

  // client_js/src/proxies/base.js
  class BaseGlueProxy {
    constructor({ http, policy, state = {}, metadata = {} }) {
      this._http = http;
      this._policy = cloneValue(policy);
      this._name = this._policy?.name;
      this._state = cloneValue(state || {});
      this._metadata = cloneValue(metadata || {});
      this._listeners = { before: {}, after: {}, error: {} };
      this._onMessage = null;
      this._onError = null;
      this._defineCallableAttributes();
    }
    get $policy() {
      return this._policy;
    }
    get $state() {
      return this._state;
    }
    get $metadata() {
      return this._metadata;
    }
    get $name() {
      return this._name;
    }
    addListener(attribute, callback, when = "after") {
      if (!this._listeners[when]) {
        this._listeners[when] = {};
      }
      if (!this._listeners[when][attribute]) {
        this._listeners[when][attribute] = [];
      }
      this._listeners[when][attribute].push(callback);
      return this;
    }
    async _call(attribute, kwargs = {}) {
      const attributeRequest = { attribute, kwargs };
      this._emit("before", attribute, { attributeRequest, object: this });
      try {
        const response = await this._http.sendAttributeRequest({
          name: this._name,
          policy: this._policy,
          state: this._state,
          attribute,
          kwargs
        });
        this._applyResponse(response.data);
        this._processMessages(response.data);
        this._emit("after", attribute, {
          attributeRequest,
          object: this,
          proxy: this,
          response: response.data
        });
        return response.data?.result;
      } catch (error) {
        this._emit("error", attribute, { attributeRequest, object: this, proxy: this, error });
        const errorHandler = this._onError || window.Glue?._onError;
        errorHandler?.({ error, attribute, attributeRequest, proxy: this });
        throw error;
      }
    }
    _applyResponse(data = {}) {
      if (data.policy) {
        this._policy = cloneValue(data.policy);
      }
      if (data.metadata !== undefined) {
        this._metadata = cloneValue(data.metadata || {});
      }
      if (data.policy || data.metadata !== undefined) {
        this._defineCallableAttributes();
      }
      if (data.state !== undefined) {
        this._applyState(data.state || {});
      }
    }
    _applyState(state) {
      const nextState = this._parseState(cloneValue(state || {}));
      if (!this._state || typeof this._state !== "object") {
        this._state = nextState;
        return;
      }
      if (this._state.instance_data && nextState.instance_data) {
        Object.keys(this._state.instance_data).forEach((key) => {
          if (!(key in nextState.instance_data)) {
            delete this._state.instance_data[key];
          }
        });
        Object.entries(nextState.instance_data).forEach(([key, value]) => {
          this._state.instance_data[key] = value;
        });
        delete nextState.instance_data;
      }
      Object.keys(this._state).forEach((key) => {
        if (!(key in nextState) && key !== "instance_data") {
          delete this._state[key];
        }
      });
      Object.assign(this._state, nextState);
    }
    _parseState(state) {
      return state;
    }
    _defineCallableAttributes() {
      Object.entries(this._metadata?.attributes || {}).forEach(([attributeName, spec]) => {
        if (spec?.namespace !== "callable") {
          return;
        }
        this._defineCallableAttribute(attributeName);
      });
    }
    _defineCallableAttribute(attributeName) {
      const parts = attributeName.split(".");
      const methodName = parts.pop();
      const owner = this._callableAttributeOwner(parts);
      if (owner[methodName] !== undefined) {
        return;
      }
      Object.defineProperty(owner, methodName, {
        value: async function(kwargs = {}) {
          const root = this.__glue__owner || this;
          return await root._call(attributeName, kwargs);
        },
        enumerable: false,
        configurable: true
      });
    }
    _callableAttributeOwner(parts) {
      return parts.reduce((current, part) => {
        const cacheKey = `__glue__${part}`;
        if (current[part] === undefined) {
          Object.defineProperty(current, part, {
            get: function() {
              if (!Object.prototype.hasOwnProperty.call(this, cacheKey)) {
                Object.defineProperty(this, cacheKey, {
                  value: {},
                  enumerable: false,
                  configurable: true
                });
              }
              Object.defineProperty(this[cacheKey], "__glue__owner", {
                value: this,
                enumerable: false,
                configurable: true
              });
              return this[cacheKey];
            },
            enumerable: false,
            configurable: true
          });
        }
        return current[part];
      }, this);
    }
    onMessage(callback) {
      this._onMessage = callback;
      return this;
    }
    onError(callback) {
      this._onError = callback;
      return this;
    }
    _processMessages(data = {}) {
      if (!data.messages?.length || typeof window === "undefined") {
        return;
      }
      const handler = this._onMessage || window.Glue?._onMessage;
      handler?.({ messages: data.messages, proxy: this });
    }
    _emit(when, attribute, payload) {
      const listeners = [
        ...this._listeners[when]?.[attribute] || [],
        ...this._listeners[when]?.["*"] || []
      ];
      listeners.forEach((listener) => listener(payload));
    }
  }
  var base_default = BaseGlueProxy;

  // client_js/src/proxies/fields/base.js
  function isFieldMetadataProperty(prop) {
    return prop === "choices" || prop === "buildChoices" || prop === "selectedChoice" || prop === "selectedChoices" || prop === "selectedPks" || prop === "selectedLabel" || prop === "pk" || typeof prop === "string" && prop.startsWith("__glue__");
  }

  class FieldGlue {
    constructor({ owner, name, metadata = {} }) {
      this.name = name;
      Object.defineProperty(this, "owner", {
        value: owner,
        enumerable: false,
        configurable: true
      });
      this.updateMetadata(metadata);
      Object.defineProperty(this, "__glue__isFieldProxy", {
        value: true,
        enumerable: false,
        configurable: false
      });
    }
    get value() {
      return this.owner._getFieldValue(this.name);
    }
    set value(value) {
      this.owner._setFieldValue(this.name, value);
    }
    get errors() {
      return this.owner._getFieldErrors()[this.name];
    }
    get hasErrors() {
      return Boolean(this.errors?.length);
    }
    updateMetadata(metadata = {}) {
      Object.entries(metadata).forEach(([key, value]) => {
        if (["value", "errors", "hasErrors"].includes(key)) {
          return;
        }
        this[key] = value;
      });
      this.name = this.name || metadata.name;
    }
    primitiveValue(hint = "default") {
      const value = this.value;
      if (value === null || value === undefined) {
        return "";
      }
      if (value instanceof Date) {
        return hint === "number" ? value.valueOf() : value.toString();
      }
      if (typeof value === "object") {
        return Array.isArray(value) ? value.join(",") : String(value);
      }
      return value;
    }
    [Symbol.toPrimitive](hint) {
      return this.primitiveValue(hint);
    }
    toString() {
      return String(this.primitiveValue());
    }
    valueOf() {
      return this.primitiveValue();
    }
    toJSON() {
      return this.value;
    }
    asProxy() {
      const field = this;
      return new Proxy(this, {
        get(target, prop, receiver) {
          if (prop === Symbol.iterator) {
            return target.value?.[Symbol.iterator]?.bind(target.value);
          }
          if (prop === "then") {
            return;
          }
          if (prop === "choices" && target.choice_model_path && !target.__glue__choicesLoaded && !target.__glue__loadingChoices) {
            target.ensureChoices([], receiver);
          }
          if (prop in target) {
            return Reflect.get(target, prop, receiver);
          }
          const value = target.value;
          const member = value?.[prop];
          return typeof member === "function" ? member.bind(value) : member;
        },
        set(target, prop, value, receiver) {
          if (prop === "value") {
            target.value = value;
            return true;
          }
          if (prop in target || isFieldMetadataProperty(prop)) {
            return Reflect.set(target, prop, value, receiver);
          }
          const current = target.value;
          if (current && typeof current === "object") {
            current[prop] = value;
            return true;
          }
          return Reflect.set(target, prop, value, receiver);
        },
        has(target, prop) {
          return prop in target || prop in Object(field.value ?? {});
        }
      });
    }
  }
  var base_default2 = FieldGlue;

  // client_js/src/proxies/fields/choice.js
  class ChoiceFieldGlue extends base_default2 {
    get selectedChoice() {
      return (this.choices || []).find(([value]) => value === this.value);
    }
    get selectedLabel() {
      return this.selectedChoice?.[1] ?? "";
    }
  }
  var choice_default = ChoiceFieldGlue;

  // client_js/src/proxies/fields/relation.js
  class RelationFieldGlue extends choice_default {
    static choicesCache = new Map;
    updateMetadata(metadata = {}) {
      super.updateMetadata(metadata);
      this._initializeChoices();
    }
    get pk() {
      const value = this.value;
      if (value && typeof value === "object") {
        return value.pk ?? value.id;
      }
      return value;
    }
    set pk(value) {
      this.value = value;
    }
    get selectedChoice() {
      const pk = Number(this.pk);
      return (this.choices || []).find((choice) => Number(choice.pk) === pk);
    }
    get selectedLabel() {
      return this.selectedChoice?.__str__ ?? "";
    }
    buildChoices(...choiceFields) {
      this.ensureChoices(choiceFields, this);
      return this.choices;
    }
    ensureChoices(choiceFields = [], subscriber = this) {
      const cacheKey = this._getChoicesCacheKey();
      const cached = this._getOrCreateChoicesCache(cacheKey);
      cached.fields.add(subscriber);
      const requiredFields = this._normalizeChoiceFields(choiceFields);
      const missingFields = requiredFields.filter((choiceField) => !cached.loadedFields.has(choiceField));
      if (missingFields.length === 0) {
        subscriber._applyCachedChoices(cached);
        return cached.promise || Promise.resolve(cached.data);
      }
      if (cached.promise) {
        subscriber.__glue__loadingChoices = true;
        return cached.promise.then(() => this.ensureChoices(choiceFields, subscriber));
      }
      if (typeof this.owner.foreign_key_choices !== "function") {
        return Promise.resolve(cached.data);
      }
      subscriber.__glue__loadingChoices = true;
      missingFields.forEach((choiceField) => cached.pendingFields.add(choiceField));
      cached.promise = this.owner.foreign_key_choices({
        field_name: this.name,
        choice_fields: missingFields.filter((choiceField) => !["pk", "__str__"].includes(choiceField))
      }).then((result) => {
        const choices = Array.isArray(result) ? result : [];
        this._cacheChoices(choices, missingFields);
        return cached.data;
      }).finally(() => {
        missingFields.forEach((choiceField) => cached.pendingFields.delete(choiceField));
        cached.promise = null;
        subscriber.__glue__loadingChoices = false;
      });
      return cached.promise;
    }
    _initializeChoices() {
      const cacheKey = this._getChoicesCacheKey();
      const cached = RelationFieldGlue.choicesCache.get(cacheKey);
      const initialChoices = Array.isArray(this.__glue__choicesData) ? this.__glue__choicesData : Array.isArray(this.choices) ? this.choices : [];
      this.__glue__choicesCacheKey = cacheKey;
      this.__glue__choicesLoaded = Boolean(cached?.loadedFields?.has("__str__"));
      this.__glue__loadingChoices = Boolean(cached?.promise);
      this.__glue__choicesData = cached?.data || initialChoices;
      this.choices = cached?.data || initialChoices;
    }
    _getChoicesCacheKey() {
      return this.choices_cache_key || [
        this.owner.$policy?.identity?.model_class_path,
        this.owner.$policy?.identity?.form_class_path,
        this.choice_model_path,
        this.name
      ].filter(Boolean).join(":") || `${this.type}:${this.name}`;
    }
    _normalizeChoiceFields(choiceFields = []) {
      return ["pk", "__str__", ...choiceFields].filter((choiceField, index, fields) => {
        return choiceField && fields.indexOf(choiceField) === index;
      });
    }
    _getOrCreateChoicesCache(cacheKey) {
      let cached = RelationFieldGlue.choicesCache.get(cacheKey);
      if (!cached) {
        cached = {
          data: this.__glue__choicesData || [],
          fields: new Set,
          loadedFields: new Set,
          pendingFields: new Set,
          promise: null
        };
        RelationFieldGlue.choicesCache.set(cacheKey, cached);
      }
      return cached;
    }
    _applyCachedChoices(cached, { force = false } = {}) {
      const previousChoices = this.__glue__choicesData;
      this.__glue__choicesLoaded = cached.loadedFields.has("__str__");
      this.__glue__loadingChoices = Boolean(cached.promise);
      if (force || previousChoices !== cached.data) {
        this.choices = cached.data;
      } else {
        this.__glue__choicesData = cached.data;
      }
    }
    _cacheChoices(choices, choiceFields = []) {
      const cached = this._getOrCreateChoicesCache(this._getChoicesCacheKey());
      const nextChoices = [...cached.data];
      choices.forEach((choice) => this._mergeChoice(nextChoices, choice));
      cached.data = nextChoices;
      this._normalizeChoiceFields(choiceFields).forEach((choiceField) => cached.loadedFields.add(choiceField));
      cached.fields.forEach((field) => {
        field._applyCachedChoices(cached, { force: true });
      });
    }
    _mergeChoice(choices, choice) {
      if (!choice || typeof choice !== "object") {
        return;
      }
      const existing = choices.find((item) => item.pk === choice.pk);
      if (existing) {
        Object.assign(existing, choice);
      } else {
        choices.push(choice);
      }
    }
  }
  var relation_default = RelationFieldGlue;

  // client_js/src/proxies/fields/manyRelation.js
  class ManyRelationFieldGlue extends relation_default {
    get selectedPks() {
      return (this.value || []).map((choice) => Number(choice?.pk ?? choice?.id ?? choice));
    }
    get selectedChoices() {
      const selectedPks = new Set(this.selectedPks);
      return (this.choices || []).filter((choice) => selectedPks.has(Number(choice.pk)));
    }
    has(choiceOrPk) {
      const pk = Number(choiceOrPk?.pk ?? choiceOrPk?.id ?? choiceOrPk);
      return this.selectedPks.includes(pk);
    }
    add(choiceOrPk) {
      if (this.has(choiceOrPk)) {
        return this.value || [];
      }
      this.value = [...this.value || [], choiceOrPk];
      return this.value;
    }
    remove(choiceOrPk) {
      const pk = Number(choiceOrPk?.pk ?? choiceOrPk?.id ?? choiceOrPk);
      this.value = (this.value || []).filter((choice) => Number(choice?.pk ?? choice?.id ?? choice) !== pk);
      return this.value;
    }
    toggle(choiceOrPk) {
      return this.has(choiceOrPk) ? this.remove(choiceOrPk) : this.add(choiceOrPk);
    }
  }
  var manyRelation_default = ManyRelationFieldGlue;

  // client_js/src/proxies/fields/index.js
  function createFieldGlue({ owner, name, metadata = {}, existingField = null }) {
    if (existingField?.__glue__isFieldProxy) {
      existingField.updateMetadata(metadata);
      existingField.name = name;
      return existingField;
    }
    const options = { owner, name, metadata };
    if (metadata.choice_model_path && metadata.type === "ManyToManyField") {
      return new manyRelation_default(options).asProxy();
    }
    if (metadata.choice_model_path) {
      return new relation_default(options).asProxy();
    }
    if (Array.isArray(metadata.choices)) {
      return new choice_default(options).asProxy();
    }
    return new base_default2(options).asProxy();
  }

  // client_js/src/proxies/fieldBacked.js
  class FieldBackedGlueProxy extends base_default {
    constructor(options) {
      super(options);
      this.loading = false;
      this._state === {} && this._initializeState();
      this._initializeFields();
    }
    get $fields() {
      return this._fields;
    }
    get $pk() {
      const pkField = this._policy?.identity?.pk_field_name || "id";
      return this._policy?.identity?.target_pk ?? this._state?.instance_data?.[pkField];
    }
    get $key() {
      return this.$pk ?? this.$name;
    }
    hasErrors(fieldName = null) {
      if (fieldName) {
        return Boolean(this._state?.errors?.[fieldName]?.length);
      }
      return Object.keys(this._state?.errors || {}).length > 0;
    }
    _ensureFieldState() {
      if (!this._state) {
        this._state = {};
      }
      if (!this._state.instance_data) {
        this._state.instance_data = {};
      }
      if (!this._state.errors) {
        this._state.errors = {};
      }
    }
    _getFieldValue(fieldName) {
      if (Object.keys(this._state.instance_data).length == 0 && !this.loading) {
        this.loading = true;
        this._call("load").then(() => {
          console.log(fieldName, "lodaded");
          this.loading = false;
        });
      }
      return this._state.instance_data?.[fieldName];
    }
    _setFieldValue(fieldName, value) {
      if (!this._state.instance_data) {
        this._state.instance_data = {};
      }
      this._state.instance_data[fieldName] = value;
    }
    _getFieldErrors() {
      return this._state?.errors || {};
    }
    _defineFields() {
      const nextFields = this._fields || {};
      Object.keys(nextFields).forEach((fieldName) => {
        if (!this._metadata?.fields?.[fieldName]) {
          delete nextFields[fieldName];
        }
      });
      Object.entries(this._metadata?.fields || {}).forEach(([fieldName, field]) => {
        nextFields[fieldName] = createFieldGlue({
          owner: this,
          name: fieldName,
          metadata: field,
          existingField: nextFields[fieldName]
        });
        if (this[fieldName] === undefined) {
          this._defineFieldProperty(fieldName);
        }
      });
      this._fields = nextFields;
      Object.values(this._fields).forEach((field) => {
        if (!field?.choice_model_path && !Array.isArray(field?.choices)) {
          field.choices = [];
        }
      });
    }
    _defineFieldProperty(fieldName) {
      Object.defineProperty(this, fieldName, {
        get: function() {
          this._fields[fieldName];
        },
        set: function(value) {
          this._fields[fieldName].value = value?.__glue__isFieldProxy ? value.value : value;
        },
        enumerable: true,
        configurable: true
      });
    }
    _parseFieldValues() {
      Object.keys(this._fields || {}).forEach((fieldName) => {
        this._fields[fieldName].value = parseFieldValue(this._fields[fieldName], this._getFieldValue(fieldName));
      });
    }
    _applyResponse(data = {}) {
      super._applyResponse.bind(this).call(data);
      this._ensureFieldState();
      this._defineFields();
      this._parseFieldValues();
    }
    _initializeState() {
      if (this._state === {}) {
        this._state.instance_data;
      }
    }
    _initializeFields() {
      Object.entries(this._metadata.fields).forEach(([fieldName, fieldDefinition]) => {
        this._state.instance_data;
      });
      console.log(this._metadata);
    }
  }
  var fieldBacked_default = FieldBackedGlueProxy;

  // client_js/src/proxies/form.js
  class GlueFormProxy extends fieldBacked_default {
  }
  var form_default = GlueFormProxy;

  // client_js/src/proxies/function.js
  class GlueFunctionProxy extends base_default {
    static create(options) {
      const object = new GlueFunctionProxy(options);
      const callable = async (kwargs = {}) => await object.execute(kwargs);
      return new Proxy(callable, {
        get(target, prop) {
          if (prop in object) {
            const value = object[prop];
            return typeof value === "function" ? value.bind(object) : value;
          }
          return target[prop];
        },
        set(target, prop, value) {
          object[prop] = value;
          return true;
        }
      });
    }
    async execute(kwargs = {}) {
      const result = await this._call("execute", this._filterKwargs(kwargs));
      return result?.result ?? result;
    }
    _filterKwargs(kwargs) {
      const params = this._normalizeParams(this._metadata?.params || this._policy?.identity?.params || []);
      if (!params.length) {
        return kwargs;
      }
      return Object.fromEntries(Object.entries(kwargs).filter(([key]) => params.includes(key)));
    }
    _normalizeParams(params) {
      return params.map((param) => typeof param === "string" ? param : param.name).filter(Boolean);
    }
  }
  var function_default = GlueFunctionProxy;

  // client_js/src/proxies/model.js
  class GlueModelProxy extends fieldBacked_default {
    async delete() {
      const result = await this._call("delete");
      this.$collection?._removeRowProxy(this);
      return result;
    }
  }
  var model_default = GlueModelProxy;

  // client_js/src/proxies/queryset.js
  class GlueQuerySetProxy extends base_default {
    constructor(options) {
      super(options);
      this._rowProxies = new Map;
      this._queryParams = options.queryParams || {};
      this._items = [];
      this._queryResults = {};
      this._resultCache = [];
      this._queryLoadingKeys = new Set;
      this._queryLoadedKeys = new Set;
      this._syncItems();
      this._setQueryResult(this._queryKey({}), this._items);
    }
    get _itemPayloads() {
      return this._state?.items || [];
    }
    get items() {
      return this._items;
    }
    get rows() {
      return this.items;
    }
    [Symbol.iterator]() {
      return this.items[Symbol.iterator]();
    }
    queryWithParams(params = {}) {
      const key = this._queryKey(params);
      if (this._queryResults[key]) {
        this._resultCache = this._queryResults[key];
        return this._resultCache;
      }
      this._queryResults[key] = this._resultCache;
      this._ensureQueryResult(params, key);
      return this._resultCache;
    }
    query_with_params(params = {}) {
      return this.queryWithParams(params);
    }
    async fetchWithParams(params = {}) {
      const attribute = "query_with_params";
      const attributeRequest = { attribute, kwargs: params };
      this._emit("before", attribute, { attributeRequest, object: this });
      try {
        const response = await this._http.sendAttributeRequest({
          name: this._name,
          policy: this._policy,
          state: this._state,
          attribute,
          kwargs: params
        });
        const items = this._itemsFromResponse(response.data);
        this._processMessages(response.data);
        this._emit("after", attribute, {
          attributeRequest,
          object: this,
          proxy: this,
          response: response.data
        });
        return items;
      } catch (error) {
        this._emit("error", attribute, { attributeRequest, object: this, proxy: this, error });
        throw error;
      }
    }
    async all() {
      return await this.fetchWithParams(this._queryParams);
    }
    filter(filter = {}) {
      return this._cloneWithQueryParams({ filter });
    }
    orderBy(orderBy) {
      return this._cloneWithQueryParams({ order_by: orderBy });
    }
    slice(start, stop) {
      return this._cloneWithQueryParams({ slice: { start, stop } });
    }
    async new() {
      return await this._call("new");
    }
    _applyResponse(data = {}) {
      super._applyResponse(data);
      this._syncItems();
    }
    _syncItems() {
      const items = this._itemPayloads.map((row, index) => this._buildRowObject(row, index));
      this._items = items;
      this._setQueryResult(this._queryKey({}), items);
    }
    _ensureQueryResult(params = {}, key = this._queryKey(params)) {
      if (this._queryLoadingKeys.has(key) || this._queryLoadedKeys.has(key)) {
        return;
      }
      this._queryLoadingKeys.add(key);
      this.fetchWithParams(params).then((items) => {
        this._setQueryResult(key, items);
        this._queryLoadedKeys.add(key);
      }).finally(() => {
        this._queryLoadingKeys.delete(key);
      });
    }
    _setQueryResult(key, items) {
      this._queryResults[key] = items;
      this._resultCache = items;
    }
    _cloneWithQueryParams(params = {}) {
      return new this.constructor({
        http: this._http,
        policy: this._policy,
        state: this._state,
        metadata: this._metadata,
        queryParams: this._mergeQueryParams(params)
      });
    }
    _mergeQueryParams(params = {}) {
      return {
        ...this._queryParams,
        ...params,
        filter: {
          ...this._queryParams.filter || {},
          ...params.filter || {}
        },
        slice: {
          ...this._queryParams.slice || {},
          ...params.slice || {}
        }
      };
    }
    _queryKey(params = {}) {
      return JSON.stringify(params || {});
    }
    _itemsFromResponse(data = {}) {
      const itemPayloads = data.result?.items || data.state?.items || [];
      return itemPayloads.map((row, index) => this._buildRowObject(row, index));
    }
    _buildRowObject(row, index) {
      if (row?.policy) {
        return this._getOrCreateRowProxy(row, index);
      }
      return {
        $key: row?.id ?? row?.pk ?? index,
        ...row
      };
    }
    _getOrCreateRowProxy(row, index) {
      const name = row.policy.name || `${this._name}.${index}`;
      let proxy = this._rowProxies.get(name);
      if (!proxy) {
        proxy = new model_default({
          http: this._http,
          policy: row.policy,
          state: row.state,
          metadata: row.metadata || this._metadata
        });
        proxy.$collection = this;
        this._rowProxies.set(name, proxy);
        return proxy;
      }
      proxy._applyResponse({
        policy: row.policy,
        state: row.state,
        metadata: row.metadata || this._metadata
      });
      proxy.$collection = this;
      return proxy;
    }
    _removeRowProxy(proxy) {
      const rowIndex = this._itemPayloads.findIndex((row) => {
        return row?.policy?.name === proxy.$name || row?.policy?.identity?.target_pk === proxy.$pk || row?.id === proxy.$pk || row?.pk === proxy.$pk;
      });
      if (rowIndex >= 0) {
        this._itemPayloads.splice(rowIndex, 1);
        this._items.splice(rowIndex, 1);
      }
      this._rowProxies.delete(proxy.$name);
    }
  }
  var queryset_default = GlueQuerySetProxy;

  // client_js/src/proxies/template.js
  class GlueTemplateProxy extends base_default {
    async renderHtml(payload = {}) {
      const result = await this._call("render_html", payload);
      return result?.html ?? result;
    }
    async renderInnerHtml(selector, payload = {}) {
      const element = typeof selector === "string" ? document.querySelector(selector) : selector;
      const html = await this.renderHtml(payload);
      element.innerHTML = html;
      return html;
    }
    async renderOuterHtml(selector, payload = {}) {
      const element = typeof selector === "string" ? document.querySelector(selector) : selector;
      const html = await this.renderHtml(payload);
      element.outerHTML = html;
      return html;
    }
  }
  var template_default = GlueTemplateProxy;

  // client_js/src/proxies/index.js
  var NAMESPACE_TO_PROXY_CLASS = {
    form: form_default,
    function: function_default,
    model: model_default,
    querySet: queryset_default,
    template: template_default
  };

  // client_js/src/client.js
  class GlueClient {
    constructor(context) {
      this.proxies = {};
      this._onMessage = null;
      this._onError = null;
      this._config = new config_default({
        ...context.config || {},
        urls: context.urls || {}
      });
      this.http = new http_default(this._config);
      this.loadManifests(context.manifest_list);
    }
    onMessage(callback) {
      this._onMessage = callback;
      return this;
    }
    onError(callback) {
      this._onError = callback;
      return this;
    }
    proxy(name) {
      return this.proxies[name];
    }
    async fetch(url, requestOptions = {}) {
      return await this.http.sendRequest(url, requestOptions);
    }
    view(url, sharedPayload = {}) {
      return new view_default(this.http, url, sharedPayload);
    }
    loadManifests(manifest_list = []) {
      (manifest_list || []).forEach((glueManifest) => {
        this._registerManifestAsProxy(glueManifest);
      });
    }
    _registerManifestAsProxy({ policy, state = {}, metadata = {} }) {
      const name = policy?.name;
      const namespace = policy?.namespace || metadata?.namespace;
      const ProxyClass = NAMESPACE_TO_PROXY_CLASS[namespace];
      if (!name) {
        throw new GlueProxyError("Cannot register a Glue proxy without policy.name.");
      }
      if (!ProxyClass) {
        throw new GlueProxyError(`No Glue proxy class registered for namespace "${namespace}".`);
      }
      if (!(namespace in this)) {
        this[namespace] = {};
      }
      Object.defineProperty(this[namespace], name, {
        get: () => namespace === "function" ? ProxyClass.create({ http: this.http, policy, state, metadata }) : new ProxyClass({ http: this.http, policy, state, metadata })
      });
    }
  }
  var client_default = GlueClient;

  // client_js/django_glue.js
  globalThis.GlueClient = client_default;
  globalThis.parseJsonScriptById = parseJsonScriptById;
})();
