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
    resolveUrl: () => resolveUrl,
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
  function serializeValue(value) {
    if (value === null || value === undefined) {
      return value;
    }
    if (typeof value === "function") {
      return;
    }
    if (value instanceof Date) {
      return value.toISOString();
    }
    if (Array.isArray(value)) {
      return value.map((item) => serializeValue(item));
    }
    if (isPlainObject(value)) {
      return Object.fromEntries(Object.entries(value).filter(([key, item]) => typeof item !== "function" && !key.startsWith("_")).map(([key, item]) => [key, serializeValue(item)]));
    }
    return value;
  }
  function parseJsonScriptById(scriptId) {
    return JSON.parse(document.getElementById(scriptId).textContent);
  }
  function resolveUrl(urlPathTemplate, kwargs = {}) {
    let url = urlPathTemplate;
    for (const [key, value] of Object.entries(kwargs)) {
      url = url.replace(`\${${key}}`, value);
    }
    return url;
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
      const isFileValue = (value) => value instanceof File || value instanceof Blob || value instanceof FileList;
      const extractFromValue = (value, key) => {
        if (isFileValue(value)) {
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
        if (value && typeof value === "object" && isFileValue(value.value)) {
          files[key] = value.value;
          return;
        }
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

  // client_js/src/proxies/registry.js
  var NAMESPACE_TO_PROXY_CLASS = {};
  function registerProxyClass(namespace, proxyClass) {
    NAMESPACE_TO_PROXY_CLASS[namespace] = proxyClass;
  }
  function getProxyClass(namespace) {
    return NAMESPACE_TO_PROXY_CLASS[namespace];
  }

  // client_js/src/proxies/base.js
  function isPlainObject2(value) {
    if (value === null || typeof value !== "object") {
      return false;
    }
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  }

  class BaseGlueProxy {
    constructor({ http, policy, state = {}, metadata = {}, owner = null }) {
      this._http = http;
      this._policy = policy;
      this._name = policy?.name;
      this._state = state || {};
      this._metadata = metadata || {};
      this._listeners = { before: {}, after: {}, error: {} };
      this._onMessage = null;
      this._onError = null;
      Object.defineProperty(this, "_owner", {
        value: owner,
        writable: true,
        enumerable: false,
        configurable: true
      });
      this._initializeAttributes();
    }
    get $owner() {
      return this._owner;
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
    removeListener(attribute, callback, when = "after") {
      const listeners = this._listeners[when]?.[attribute];
      if (!listeners) {
        return this;
      }
      this._listeners[when][attribute] = listeners.filter((listener) => listener !== callback);
      return this;
    }
    async _callAttribute(attribute, kwargs = {}) {
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
        if (errorHandler) {
          errorHandler({ error, attribute, attributeRequest, proxy: this });
        } else {
          throw error;
        }
      }
    }
    _applyResponse(data = {}) {
      if (data.policy) {
        this._policy = data.policy;
      }
      if (data.metadata !== undefined) {
        this._metadata = data.metadata || {};
      }
      if (data.state !== undefined) {
        this._applyState(data.state || {});
      }
    }
    _applyState(state) {
      const nextState = state || {};
      if (!this._state || typeof this._state !== "object") {
        this._state = nextState;
        return;
      }
      this._mergeState(this._state, nextState);
    }
    _mergeState(target, source) {
      Object.keys(target).forEach((key) => {
        if (!(key in source)) {
          delete target[key];
        }
      });
      Object.keys(source).forEach((key) => {
        const sourceValue = source[key];
        if (isPlainObject2(sourceValue)) {
          if (!isPlainObject2(target[key])) {
            target[key] = {};
          }
          this._mergeState(target[key], sourceValue);
        } else {
          target[key] = sourceValue;
        }
      });
    }
    _configureAttributeInitializers() {
      this._attributeBuilders = {
        container: (owner, name, qualName, meta) => this._initializeContainerAttribute(owner, name, qualName, meta),
        callable: (owner, name, qualName, meta) => this._initializeCallableAttribute(owner, name, qualName, meta),
        state: (owner, name, qualName, meta) => this._initializeStateAttribute(owner, name, qualName, meta)
      };
    }
    _initializeAttributes() {
      this._configureAttributeInitializers();
      (this._policy?.attributes || []).forEach((attribute) => {
        if (typeof attribute === "string") {
          const attributeMetadata = this._metadata?.attributes?.[attribute];
          if (attributeMetadata) {
            this._initializeAttribute(attribute, attributeMetadata);
          }
        } else if (attribute?.name) {
          const parentPrefix = this._name ? `${this._name}.` : "";
          const relativeName = attribute.name.startsWith(parentPrefix) ? attribute.name.slice(parentPrefix.length) : attribute.name;
          const attributeMetadata = this._metadata?.attributes?.[relativeName] || {};
          this._initializeGlueObjectAttribute(attribute, attributeMetadata);
        }
      });
      this._initializeGlueObjectAliases();
    }
    _initializeGlueObjectAliases() {
      const metadataAttrs = this._metadata?.attributes || {};
      for (const [attrKey, attrMeta] of Object.entries(metadataAttrs)) {
        if (attrMeta.namespace !== "glue")
          continue;
        const targetName = attrMeta.name;
        if (!targetName || targetName === attrKey)
          continue;
        const parts = attrKey.split(".");
        const aliasName = parts.pop();
        const owner = this._resolveAttributeOwner(parts);
        if (owner[aliasName] !== undefined)
          continue;
        const targetParts = targetName.split(".");
        const targetAttrName = targetParts.pop();
        const targetOwner = this._resolveAttributeOwner(targetParts);
        Object.defineProperty(owner, aliasName, {
          get() {
            return targetOwner[targetAttrName];
          },
          enumerable: true,
          configurable: true
        });
      }
    }
    _initializeAttribute(attributeQualName, attributeMetadata) {
      const parts = attributeQualName.split(".");
      const attributeName = parts.pop();
      const owner = this._resolveAttributeOwner(parts);
      if (owner[attributeName] !== undefined) {
        return;
      }
      const initializeAttribute = this._attributeBuilders[attributeMetadata.namespace];
      if (initializeAttribute) {
        initializeAttribute(owner, attributeName, attributeQualName, attributeMetadata);
      }
    }
    _initializeContainerAttribute(owner, attributeName) {
      this._defineContainerAttribute(owner, attributeName);
    }
    _initializeCallableAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
      Object.defineProperty(owner, attributeName, {
        value: async function(kwargs = {}) {
          const root = owner.__glue__root || this;
          return await root._callAttribute(attributeQualName, kwargs);
        },
        enumerable: false,
        configurable: true
      });
    }
    _initializeGlueObjectAttribute(attributePolicy, attributeMetadata) {
      const attributeQualName = attributePolicy.name;
      const parentPrefix = this._name ? `${this._name}.` : "";
      const relativeName = attributeQualName.startsWith(parentPrefix) ? attributeQualName.slice(parentPrefix.length) : attributeQualName;
      const parts = relativeName.split(".");
      const attributeName = parts.pop();
      const owner = this._resolveAttributeOwner(parts);
      if (owner[attributeName] !== undefined) {
        return;
      }
      const nestedMetadata = attributeMetadata.metadata || {};
      const nestedNamespace = attributeMetadata.glue_namespace || attributePolicy.namespace;
      const ProxyClass = getProxyClass(nestedNamespace);
      if (!ProxyClass) {
        return;
      }
      const proxy = this;
      const cacheKey = `__glue_object__${attributePolicy.name}`;
      Object.defineProperty(owner, attributeName, {
        get() {
          if (!proxy[cacheKey]) {
            const nestedState = proxy._state?.[relativeName] || {};
            const nestedProxy = new ProxyClass({
              http: proxy._http,
              policy: attributePolicy,
              state: nestedState,
              metadata: nestedMetadata,
              owner: proxy
            });
            if (Object.keys(nestedState).length > 0) {
              nestedProxy._loaded = true;
            }
            proxy[cacheKey] = nestedProxy;
          }
          return proxy[cacheKey];
        },
        enumerable: true,
        configurable: true
      });
    }
    _initializeStateAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
      const proxy = this;
      Object.defineProperty(owner, attributeName, {
        get() {
          return proxy._state?.[attributeQualName];
        },
        set(value) {
          if (!proxy._state)
            proxy._state = {};
          proxy._state[attributeQualName] = value;
        },
        enumerable: true,
        configurable: true
      });
    }
    _resolveAttributeOwner(parts) {
      return parts.reduce((current, part) => {
        if (current[part] === undefined) {
          this._defineContainerAttribute(current, part);
        }
        return current[part];
      }, this);
    }
    _defineContainerAttribute(owner, attributeName) {
      const cacheKey = Symbol(`__glue__${attributeName}`);
      Object.defineProperty(owner, attributeName, {
        get: function() {
          if (!Object.prototype.hasOwnProperty.call(this, cacheKey)) {
            Object.defineProperty(this, cacheKey, {
              value: {},
              enumerable: false,
              configurable: true
            });
          }
          Object.defineProperty(this[cacheKey], "__glue__root", {
            value: this.__glue__root || this,
            enumerable: false,
            configurable: true
          });
          return this[cacheKey];
        },
        enumerable: false,
        configurable: true
      });
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
  function isInternalProperty(prop) {
    return typeof prop === "string" && prop.startsWith("__glue__");
  }

  class FieldGlue {
    constructor({ owner, name, stateKey, metadata = {} }) {
      this.name = name;
      this.stateKey = stateKey || name;
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
      return this.owner._state?.[this.stateKey]?.value;
    }
    set value(value) {
      if (!this.owner._state) {
        this.owner._state = {};
      }
      if (!this.owner._state[this.stateKey]) {
        this.owner._state[this.stateKey] = {};
      }
      this.owner._state[this.stateKey].value = value;
    }
    get errors() {
      return this.owner._state?.[this.stateKey]?.errors || [];
    }
    get hasErrors() {
      return Boolean(this.errors?.length);
    }
    get errorText() {
      return this.errors.join(", ");
    }
    updateMetadata(metadata = {}) {
      Object.assign(this, metadata);
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
          target._handlePropertyAccess?.(prop, receiver);
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
          if (prop in target || isInternalProperty(prop)) {
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
      return (this.choices || []).find(([value]) => String(value) === String(this.value));
    }
    get selectedLabel() {
      return this.selectedChoice?.[1] ?? "";
    }
  }
  var choice_default = ChoiceFieldGlue;

  // client_js/src/proxies/fields/relation.js
  class RelationFieldGlue extends choice_default {
    static loadingCache = new Map;
    get choices() {
      return this._choices || [];
    }
    set choices(value) {
      this._choices = value;
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
      const pk = this.pk;
      if (pk == null)
        return;
      return (this.choices || []).find((choice) => Number(choice.pk) === Number(pk));
    }
    get selectedLabel() {
      return this.selectedChoice?.__str__ ?? "";
    }
    _handlePropertyAccess(prop, receiver) {
      if (prop === "choices" && this.choice_model_path) {
        receiver.ensureChoices([]);
      }
    }
    buildChoices(...choiceFields) {
      this.ensureChoices(choiceFields);
      return this.choices;
    }
    ensureChoices(choiceFields = []) {
      const cacheKey = this._getChoicesCacheKey();
      const cache = this._getOrCreateCache(cacheKey);
      cache.fields.add(this);
      if (this._choices !== cache.choices) {
        this.choices = cache.choices;
      }
      const requiredFields = this._normalizeChoiceFields(choiceFields);
      const missingFields = requiredFields.filter((f) => !cache.loadedFields.has(f));
      if (missingFields.length === 0) {
        return cache.promise || Promise.resolve(this._choices || []);
      }
      if (cache.promise) {
        return cache.promise.then(() => this.ensureChoices(choiceFields));
      }
      if (typeof this.owner.foreign_key_choices !== "function") {
        return Promise.resolve(this._choices || []);
      }
      cache.promise = this.owner.foreign_key_choices({
        field_name: this.name,
        choice_fields: missingFields.filter((f) => !["pk", "__str__"].includes(f))
      }).then((result) => {
        const newChoices = Array.isArray(result) ? result : [];
        this._mergeChoices(newChoices);
        requiredFields.forEach((f) => cache.loadedFields.add(f));
        return this._choices || [];
      }).finally(() => {
        cache.promise = null;
      });
      return cache.promise;
    }
    _getChoicesCacheKey() {
      return this.choices_cache_key || [
        this.owner._policy.identity.model_class_path,
        this.owner._policy.identity.form_class_path,
        this.choice_model_path,
        this.name
      ].filter(Boolean).join(":");
    }
    _normalizeChoiceFields(choiceFields = []) {
      return [...new Set(["pk", "__str__", ...choiceFields.filter(Boolean)])];
    }
    _getOrCreateCache(cacheKey) {
      let cache = RelationFieldGlue.loadingCache.get(cacheKey);
      if (!cache) {
        cache = {
          loadedFields: new Set,
          promise: null,
          choices: [],
          fields: new Set
        };
        RelationFieldGlue.loadingCache.set(cacheKey, cache);
      }
      return cache;
    }
    _mergeChoices(newChoices) {
      const cache = this._getOrCreateCache(this._getChoicesCacheKey());
      const current = cache.choices;
      const merged = [...current];
      newChoices.forEach((choice) => {
        if (!choice || typeof choice !== "object")
          return;
        const existing = merged.find((item) => item.pk === choice.pk);
        if (existing) {
          Object.assign(existing, choice);
        } else {
          merged.push(choice);
        }
      });
      cache.choices = merged;
      for (const field of cache.fields) {
        field.choices = cache.choices;
      }
    }
  }
  var relation_default = RelationFieldGlue;

  // client_js/src/proxies/fields/manyRelation.js
  class ManyRelationFieldGlue extends relation_default {
    _extractPk(choiceOrPk) {
      if (choiceOrPk == null)
        return null;
      const pk = choiceOrPk?.pk ?? choiceOrPk?.id ?? choiceOrPk;
      return pk == null ? null : Number(pk);
    }
    get selectedPks() {
      return (this.value || []).map((choice) => this._extractPk(choice)).filter((pk) => pk != null);
    }
    get selectedChoices() {
      const selectedPks = new Set(this.selectedPks);
      return (this.choices || []).filter((choice) => selectedPks.has(Number(choice.pk)));
    }
    has(choiceOrPk) {
      const pk = this._extractPk(choiceOrPk);
      if (pk == null)
        return false;
      const selectedPks = new Set(this.selectedPks);
      return selectedPks.has(pk);
    }
    add(choiceOrPk) {
      if (this.has(choiceOrPk)) {
        return this;
      }
      this.value = [...this.value || [], choiceOrPk];
      return this;
    }
    remove(choiceOrPk) {
      const pk = this._extractPk(choiceOrPk);
      if (pk == null)
        return this;
      this.value = (this.value || []).filter((choice) => this._extractPk(choice) !== pk);
      return this;
    }
    toggle(choiceOrPk) {
      return this.has(choiceOrPk) ? this.remove(choiceOrPk) : this.add(choiceOrPk);
    }
  }
  var manyRelation_default = ManyRelationFieldGlue;

  // client_js/src/proxies/fields/index.js
  function createFieldGlue({ owner, name, stateKey, metadata = {}, existingField = null }) {
    if (existingField?.__glue__isFieldProxy) {
      existingField.updateMetadata(metadata);
      existingField.name = name;
      existingField.stateKey = stateKey;
      return existingField;
    }
    const options = { owner, name, stateKey, metadata };
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
      this._loaded = false;
      this.loading = false;
    }
    get $fields() {
      return this._fields;
    }
    get $pk() {
      const pkField = this._policy?.identity?.pk_field_name || "id";
      return this._policy?.identity?.target_pk ?? this._state?.[pkField]?.value;
    }
    get $key() {
      return this.$pk ?? this._name;
    }
    hasErrors(fieldName = null) {
      if (fieldName) {
        return Boolean(this._state?.[fieldName]?.errors?.length);
      }
      return Object.values(this._state || {}).some((fieldState) => fieldState?.errors?.length > 0);
    }
    _configureAttributeInitializers() {
      super._configureAttributeInitializers();
      this._fields = {};
      this._attributeBuilders.field = (owner, name, qualName, meta) => this._initializeFieldAttribute(owner, name, qualName, meta);
      this._attributeBuilders.related_field = (owner, name, qualName, meta) => this._initializeRelatedFieldAttribute(owner, name, qualName, meta);
    }
    _initializeFieldAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
      this._fields[attributeName] = createFieldGlue({
        owner: this,
        name: attributeName,
        stateKey: attributeQualName,
        metadata: attributeMetadata,
        existingField: this._fields[attributeName]
      });
      Object.defineProperty(this, attributeName, {
        get() {
          if (!this._loaded && !this.loading) {
            this.loading = true;
            this._callAttribute("load").then(() => {
              this._loaded = true;
              this.loading = false;
            });
          }
          return this._state?.[attributeQualName]?.value;
        },
        set(value) {
          this._fields[attributeName].value = value?.__glue__isFieldProxy ? value.value : value;
        },
        enumerable: true,
        configurable: true
      });
    }
    _initializeRelatedFieldAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
      const proxy = this;
      const cacheKey = `__glue_object__${this._name}.${attributeQualName}`;
      if (!(attributeName in this)) {
        Object.defineProperty(this, attributeName, {
          get() {
            return proxy[cacheKey] || null;
          },
          enumerable: true,
          configurable: true
        });
      }
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
      const result = await this._callAttribute("execute", this._filterKwargs(kwargs));
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
    _configureAttributeInitializers() {
      super._configureAttributeInitializers();
      this._attributeBuilders.readable = (owner, name, qualName) => {
        this._initializeReadableAttribute(owner, name, qualName);
      };
    }
    _initializeReadableAttribute(owner, attributeName, attributeQualName) {
      const proxy = this;
      Object.defineProperty(owner, attributeName, {
        get() {
          return proxy._state?.[attributeQualName]?.value;
        },
        enumerable: true,
        configurable: true
      });
    }
    async delete() {
      const result = await this._callAttribute("delete");
      this.$collection?._removeModelProxy(this);
      return result;
    }
    async load() {
      const result = await this._callAttribute("load");
      this.$collection?._updateModelProxy(this);
      return result;
    }
  }
  var model_default = GlueModelProxy;

  // client_js/src/proxies/queryset.js
  class GlueQuerySetProxy extends base_default {
    constructor(options) {
      super(options);
      this._modelProxies = new Map;
      this._queryParams = options.queryParams || {};
      this._queryCache = {};
      this._loaded = false;
      this.loading = false;
    }
    get items() {
      return Array.from(this);
    }
    [Symbol.iterator]() {
      if (!this._loaded && !this.loading) {
        this.loading = true;
        this.all().then(() => {
          this._loaded = true;
          this.loading = false;
        });
      }
      return this._modelProxies.values();
    }
    async all() {
      const result = await this.query_with_params(this._queryParams);
      this._syncFromResult(result);
      this._loaded = true;
      return this;
    }
    async get(pk) {
      const row = await this._callAttribute("get", { pk });
      const name = row.policy?.name || `${this._name}.${pk}`;
      const proxy = this._buildModelProxy(row, this._modelProxies.get(name));
      this._modelProxies.set(name, proxy);
      return proxy;
    }
    async new(initial = {}) {
      const newItem = await this._callAttribute("new", { initial });
      const name = newItem.policy?.name;
      const proxy = this._buildModelProxy(newItem);
      return proxy;
    }
    _syncFromResult(result = {}) {
      const items = result.items || [];
      const oldProxies = this._modelProxies;
      this._modelProxies = new Map;
      items.forEach((row, index) => {
        const name = row.policy?.name || `${this._name}.${index}`;
        const proxy = this._buildModelProxy(row, oldProxies.get(name));
        this._modelProxies.set(name, proxy);
      });
    }
    _buildModelProxy(row, existingProxy = null) {
      let proxy = existingProxy;
      if (proxy) {
        proxy._applyResponse({
          policy: row.policy,
          state: row.state,
          metadata: row.metadata || this._metadata
        });
      } else {
        proxy = new model_default({
          http: this._http,
          policy: row.policy,
          state: row.state,
          metadata: row.metadata || this._metadata
        });
      }
      proxy._loaded = true;
      proxy.$collection = this;
      return proxy;
    }
    query(params = {}) {
      const key = JSON.stringify(params);
      if (!this._queryCache[key]) {
        this._queryCache[key] = this._cloneWithQueryParams(params);
      }
      return this._queryCache[key];
    }
    filter(filter = {}) {
      return this.query({ filter });
    }
    orderBy(orderBy) {
      return this.query({ order_by: orderBy });
    }
    slice(start, stop) {
      return this.query({ slice: { start, stop } });
    }
    get count() {
      this._modelProxies.size;
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
    _removeModelProxy(proxy) {
      this._modelProxies.delete(proxy._name);
    }
    _updateModelProxy(proxy) {
      this._modelProxies.set(proxy._name, proxy);
    }
  }
  var queryset_default = GlueQuerySetProxy;

  // client_js/src/proxies/template.js
  class GlueTemplateProxy extends base_default {
    async renderHtml(payload = {}) {
      const result = await this._callAttribute("render_html", payload);
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
  var NAMESPACE_TO_PROXY_CLASS2 = {
    form: form_default,
    function: function_default,
    model: model_default,
    querySet: queryset_default,
    template: template_default
  };
  Object.entries(NAMESPACE_TO_PROXY_CLASS2).forEach(([namespace, proxyClass]) => {
    registerProxyClass(namespace, proxyClass);
  });

  // client_js/src/client.js
  class GlueClient {
    constructor(context) {
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
    _registerManifestAsProxy({ policy, metadata = {} }) {
      const name = policy?.name;
      const namespace = policy?.namespace || metadata?.namespace;
      const ProxyClass = NAMESPACE_TO_PROXY_CLASS2[namespace];
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
        get: () => namespace === "function" ? ProxyClass.create({ http: this.http, policy, metadata }) : new ProxyClass({ http: this.http, policy, metadata }),
        configurable: true
      });
    }
  }
  var client_default = GlueClient;

  // client_js/django_glue.js
  globalThis.GlueClient = client_default;
  globalThis.parseJsonScriptById = parseJsonScriptById;
  globalThis.resolveUrl = resolveUrl;
})();
