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
      this.csrfCookieName = config.csrfCookieName || "csrftoken";
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
  function shouldJsonSerializePostData(value) {
    if (typeof value !== "object" || value === null) {
      return false;
    }
    if (value instanceof FormData || value instanceof Blob || value instanceof URLSearchParams) {
      return false;
    }
    const tag = Object.prototype.toString.call(value);
    return tag === "[object Object]" || tag === "[object Array]";
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
      const headers = { ...requestOptions.headers || {} };
      const method = requestOptions.method || "GET";
      let contentType = requestOptions.contentType;
      let payload = requestOptions.payload ?? requestOptions.body;
      let csrfProtected = requestOptions.csrfProtected;
      if (method === "GET") {
        contentType = null;
        payload = null;
        csrfProtected = false;
      }
      if (contentType && contentType !== "multipart/form-data") {
        headers["Content-Type"] = contentType;
      }
      if (contentType === "application/json" && payload) {
        payload = shouldJsonSerializePostData(payload) ? JSON.stringify(payload) : payload;
      }
      if (csrfProtected !== false) {
        headers["X-CSRFToken"] = this.getCookie(this._config.csrfCookieName);
      }
      try {
        const response = await fetch(url, {
          method,
          body: payload,
          headers,
          signal: controller.signal
        });
        if (!response.ok) {
          throw await this._buildRequestError(response);
        }
        return {
          ok: response.ok,
          payload: await response.clone().text(),
          httpResponse: response,
          data: await response.json()
        };
      } finally {
        clearTimeout(timeoutId);
      }
    }
    async get(url, params, headers = {}) {
      return await this.sendRequest(url, {
        payload: params,
        headers
      });
    }
    async postJson(url, data, headers = {}, csrfProtected = true) {
      return await this.sendRequest(url, {
        payload: data,
        method: "POST",
        headers,
        contentType: "application/json",
        csrfProtected
      });
    }
    async postForm(url, data, headers = {}, csrfProtected = true) {
      return await this.sendRequest(url, {
        payload: data,
        method: "POST",
        contentType: "multipart/form-data",
        headers,
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
      return await this.postForm(`${this._config.attributeUrlPath}${name}/${attribute}/`, formData);
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
      const errorData = payload?.result?.error || payload?.error;
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
    constructor({
      http,
      policy,
      state = {},
      metadata = {},
      owner = null,
      client = null,
      loadingStrategy = "lazy"
    }) {
      this._http = http;
      this._policy = policy;
      this._name = policy?.name;
      this._state = state || {};
      this._metadata = metadata || {};
      this._client = client;
      this._listeners = { before: {}, after: {}, error: {} };
      this._onMessage = null;
      this._onError = null;
      this._loadingStrategy = loadingStrategy;
      this._loaded = loadingStrategy === "eager" || this._hasPopulatedState;
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
      const attributeMetadata = this._metadata?.attributes?.[attribute] || {};
      this._emit("before", attribute, { attributeRequest, object: this });
      try {
        const response = await this._http.sendAttributeRequest({
          name: this._name,
          policy: this._policy,
          state: this._stateForAttribute(attributeMetadata.loads_state),
          attribute,
          kwargs
        });
        this._applyResponse(response.data);
        const result = this._convertResultManifestsToProxies(response.data?.result);
        if (response.data) {
          response.data.result = result;
        }
        this._processMessages(response.data);
        this._emit("after", attribute, {
          attributeRequest,
          object: this,
          proxy: this,
          response: response.data
        });
        return result;
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
    _stateForAttribute(loadsState) {
      if (loadsState === false) {
        return null;
      }
      if (Array.isArray(loadsState)) {
        return Object.fromEntries(loadsState.filter((key) => Object.prototype.hasOwnProperty.call(this._state || {}, key)).map((key) => [key, this._state[key]]));
      }
      return this._state;
    }
    _applyResponse(data = {}) {
      const shouldRefreshGlueObjectAttributes = Boolean(data.policy || data.metadata);
      if (data.policy) {
        this._policy = data.policy;
      }
      if (data.metadata !== undefined) {
        this._metadata = data.metadata || {};
      }
      if (data.state !== undefined) {
        this._applyState(data.state || {});
        this._loaded = true;
      }
      if (data.loading_strategy !== undefined) {
        this._loadingStrategy = data.loading_strategy;
        this._loaded = data.loading_strategy === "eager" || this._hasPopulatedState;
      }
      if (shouldRefreshGlueObjectAttributes) {
        this._refreshGlueObjectAttributes();
      }
    }
    _invalidateGlueObjectCache() {
      Object.keys(this).forEach((key) => {
        if (key.startsWith("__glue_object__")) {
          delete this[key];
        }
      });
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
    get _hasPopulatedState() {
      return this._state && typeof this._state === "object" && Object.keys(this._state).length > 0;
    }
    _configureAttributeInitializers() {
      this._attributeBuilders = {
        composite: (owner, name, qualName, meta) => this._initializeCompositeAttribute(owner, name, qualName, meta),
        callable: (owner, name, qualName, meta) => this._initializeCallableAttribute(owner, name, qualName, meta),
        readonly: (owner, name, qualName, meta) => this._initializeReadOnlyAttribute(owner, name, qualName, meta),
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
    _initializeCompositeAttribute(owner, attributeName) {
      this._defineCompositeAttribute(owner, attributeName);
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
      const existingDescriptor = Object.getOwnPropertyDescriptor(owner, attributeName);
      if (existingDescriptor?.configurable) {
        delete owner[attributeName];
      } else if (existingDescriptor) {
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
      const nestedState = proxy._state?.[relativeName] || {};
      if (proxy[cacheKey]) {
        proxy[cacheKey]._applyResponse({
          policy: attributePolicy,
          state: nestedState,
          metadata: nestedMetadata
        });
      }
      Object.defineProperty(owner, attributeName, {
        get() {
          if (!proxy[cacheKey]) {
            const nestedProxy = new ProxyClass({
              http: proxy._http,
              policy: attributePolicy,
              state: nestedState,
              metadata: nestedMetadata,
              owner: proxy,
              client: proxy._client,
              loadingStrategy: proxy._loadingStrategy
            });
            proxy[cacheKey] = nestedProxy;
          }
          return proxy[cacheKey];
        },
        enumerable: true,
        configurable: true
      });
    }
    _initializeStateAttribute(owner, attributeName, attributeQualName, attributeMetadata) {
      Object.defineProperty(owner, attributeName, {
        get() {
          const root = this.__glue__root || this;
          return root._state?.[attributeQualName];
        },
        set(value) {
          const root = this.__glue__root || this;
          if (!root._state)
            root._state = {};
          root._state[attributeQualName] = value;
        },
        enumerable: true,
        configurable: true
      });
    }
    _initializeReadOnlyAttribute(owner, attributeName, attributeQualName) {
      Object.defineProperty(owner, attributeName, {
        get() {
          const root = this.__glue__root || this;
          return root._state?.[attributeQualName]?.value;
        },
        enumerable: true,
        configurable: true
      });
    }
    _resolveAttributeOwner(parts) {
      return parts.reduce((current, part) => {
        if (current[part] === undefined) {
          this._defineCompositeAttribute(current, part);
        }
        return current[part];
      }, this);
    }
    _defineCompositeAttribute(owner, attributeName) {
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
    _refreshGlueObjectAttributes() {
      (this._policy?.attributes || []).forEach((attribute) => {
        if (!attribute?.name || typeof attribute === "string") {
          return;
        }
        const parentPrefix = this._name ? `${this._name}.` : "";
        const relativeName = attribute.name.startsWith(parentPrefix) ? attribute.name.slice(parentPrefix.length) : attribute.name;
        const attributeMetadata = this._metadata?.attributes?.[relativeName] || {};
        this._initializeGlueObjectAttribute(attribute, attributeMetadata);
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
    _convertResultManifestsToProxies(result) {
      if (!this._client) {
        return result;
      }
      if (Array.isArray(result)) {
        return result.map((item) => this._convertResultManifestsToProxies(item));
      }
      if (!result || typeof result !== "object") {
        return result;
      }
      if (this._resultIsManifest(result)) {
        return this._client._createProxy(result);
      }
      Object.keys(result).forEach((key) => {
        result[key] = this._convertResultManifestsToProxies(result[key]);
      });
      return result;
    }
    _resultIsManifest(result) {
      return Boolean(result?.policy?.name && result?.policy?.namespace && result?.metadata !== undefined);
    }
  }
  var base_default = BaseGlueProxy;

  // client_js/src/proxies/collection.js
  class GlueCollectionProxy extends base_default {
    constructor(options) {
      super(options);
      if (!this._itemProxyCache) {
        this._itemProxyCache = new Map;
      }
    }
    get items() {
      return this._itemProxies();
    }
    get length() {
      return this.items.length;
    }
    at(index) {
      return this.items.at(index);
    }
    [Symbol.iterator]() {
      return this.items[Symbol.iterator]();
    }
    _itemProxies() {
      if (!this._itemProxyCache) {
        this._itemProxyCache = new Map;
      }
      const itemPolicies = (this._policy?.attributes || []).filter((attribute) => typeof attribute !== "string");
      const currentKeys = new Set(itemPolicies.map((policy, index) => policy.name || `${this._name}.${index}`));
      Array.from(this._itemProxyCache.keys()).forEach((key) => {
        if (!currentKeys.has(key)) {
          this._itemProxyCache.delete(key);
        }
      });
      return itemPolicies.map((policy, index) => this._buildItemProxy(policy, index));
    }
    _buildItemProxy(policy, index) {
      const metadata = this._metadata?.attributes?.[`items.${index}`]?.metadata || {};
      const state = this._state?.[`items.${index}`] || {};
      const ProxyClass = getProxyClass(policy.namespace) || base_default;
      const cacheKey = policy.name || `${this._name}.${index}`;
      const cachedItem = this._itemProxyCache.get(cacheKey);
      if (cachedItem) {
        if (cachedItem.policy !== policy || cachedItem.state !== state || cachedItem.metadata !== metadata) {
          cachedItem.proxy._applyResponse({ policy, state, metadata, loading_strategy: this._loadingStrategy });
          cachedItem.policy = policy;
          cachedItem.state = state;
          cachedItem.metadata = metadata;
        }
        return cachedItem.proxy;
      }
      const proxy = new ProxyClass({
        http: this._http,
        policy,
        state,
        metadata,
        owner: this,
        client: this._client,
        loadingStrategy: this._loadingStrategy
      });
      this._itemProxyCache.set(cacheKey, {
        proxy,
        policy,
        state,
        metadata
      });
      return proxy;
    }
  }
  var collection_default = GlueCollectionProxy;

  // client_js/src/proxies/fields/base.js
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
      this.owner._ensureLoaded?.();
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
  }
  var base_default2 = FieldGlue;

  // client_js/src/proxies/fields/choice.js
  class ChoiceFieldGlue extends base_default2 {
    get selectedChoice() {
      return (this.choices || []).find((choice) => String(choice.value) === String(this.value));
    }
  }
  var choice_default = ChoiceFieldGlue;

  // client_js/src/proxies/fields/manyChoice.js
  class ManyChoiceFieldGlue extends choice_default {
    get selectedValues() {
      return this.value || [];
    }
    get selectedChoices() {
      const selectedValues = new Set(this.selectedValues.map((value) => String(value)));
      return (this.choices || []).filter((choice) => selectedValues.has(String(choice.value)));
    }
    hasChoiceSelected(value) {
      return this.selectedValues.some((item) => String(item) === String(value));
    }
    addChoice(value) {
      if (this.hasChoiceSelected(value)) {
        return this;
      }
      this.value = [...this.selectedValues, value];
      return this;
    }
    removeChoice(value) {
      this.value = this.selectedValues.filter((item) => String(item) !== String(value));
      return this;
    }
    toggleChoice(value) {
      return this.hasChoiceSelected(value) ? this.removeChoice(value) : this.addChoice(value);
    }
  }
  var manyChoice_default = ManyChoiceFieldGlue;

  // client_js/src/proxies/fields/relation.js
  class RelationFieldGlue extends choice_default {
    static loadingCache = new Map;
    get choices() {
      if (this.choice_model_path) {
        this.ensureChoices([]);
      }
      return this._choices || [];
    }
    set choices(value) {
      this._choices = value;
    }
    get pk() {
      const value = this.value;
      if (value && typeof value === "object") {
        return value.value;
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
      return (this.choices || []).find((choice) => String(choice.value) === String(pk));
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
      const requiredFields = this._choiceObjectFields(choiceFields);
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
        choice_fields: missingFields.filter((f) => !["value", "label", "pk", "__str__"].includes(f))
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
    _choiceObjectFields(choiceFields = []) {
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
        const existing = merged.find((item) => item.value === choice.value);
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
    get selectedPks() {
      return (this.value || []).filter((value) => value != null);
    }
    get selectedChoices() {
      const selectedPks = new Set(this.selectedPks.map((value) => String(value)));
      return (this.choices || []).filter((choice) => selectedPks.has(String(choice.value)));
    }
    hasChoiceSelected(value) {
      return this.selectedPks.some((item) => String(item) === String(value));
    }
    addChoice(value) {
      if (this.hasChoiceSelected(value)) {
        return this;
      }
      this.value = [...this.value || [], value];
      return this;
    }
    removeChoice(value) {
      this.value = (this.value || []).filter((item) => String(item) !== String(value));
      return this;
    }
    toggleChoice(value) {
      return this.hasChoiceSelected(value) ? this.removeChoice(value) : this.addChoice(value);
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
    if (metadata.choice_model_path && ["ManyToManyField", "ModelMultipleChoiceField"].includes(metadata.type)) {
      return new manyRelation_default(options);
    }
    if (metadata.choice_model_path) {
      return new relation_default(options);
    }
    if (Array.isArray(metadata.choices)) {
      const stateValue = owner._state?.[stateKey]?.value;
      const multipleChoiceTypes = ["MultipleChoiceField", "TypedMultipleChoiceField"];
      const multipleChoiceWidgets = ["CheckboxSelectMultiple", "SelectMultiple"];
      if (Array.isArray(stateValue) || multipleChoiceTypes.includes(metadata.type) || multipleChoiceWidgets.includes(metadata.widget)) {
        return new manyChoice_default(options);
      }
      return new choice_default(options);
    }
    return new base_default2(options);
  }

  // client_js/src/proxies/fieldBacked.js
  class FieldBackedGlueProxy extends base_default {
    constructor(options) {
      super(options);
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
    _ensureLoaded() {
      if (!this._loaded && !this.loading) {
        this.loading = true;
        this._callAttribute("load_state").finally(() => {
          this.loading = false;
        });
      }
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
          this._ensureLoaded();
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

  // client_js/src/proxies/json.js
  class GlueJsonProxy extends base_default {
    constructor({ http, policy, state = {}, metadata = {}, owner = null }) {
      super({ http, policy, state, metadata, owner });
      this._value = policy?.identity?.value;
    }
    get value() {
      return this._value;
    }
    get length() {
      return this._value?.length;
    }
    at(index) {
      return this._value?.at?.(index);
    }
    [Symbol.iterator]() {
      return this._value?.[Symbol.iterator]?.() || [][Symbol.iterator]();
    }
  }
  var json_default = GlueJsonProxy;

  // client_js/src/proxies/model.js
  class GlueModelProxy extends fieldBacked_default {
    _configureAttributeInitializers() {
      super._configureAttributeInitializers();
      this._attributeBuilders.readonly = (owner, name, qualName) => {
        this._initializeReadOnlyAttribute(owner, name, qualName);
      };
    }
    _initializeReadOnlyAttribute(owner, attributeName, attributeQualName) {
      Object.defineProperty(owner, attributeName, {
        get() {
          const root = this.__glue__root || this;
          return root._state?.[attributeQualName]?.value;
        },
        enumerable: true,
        configurable: true
      });
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
      this.loading = false;
      if (this._canHydrateFromState()) {
        this._syncFromResult(this._state);
      }
    }
    get items() {
      return Array.from(this);
    }
    [Symbol.iterator]() {
      if (!this._loaded && !this.loading) {
        this.loading = true;
        this.all().then(() => {
          this._loaded = true;
        }).finally(() => {
          this.loading = false;
        });
      }
      return this._modelProxies.values();
    }
    async all() {
      if (this._loaded) {
        return this;
      }
      const result = await this.query_with_params(this._queryParams);
      this._syncFromResult(result);
      this._loaded = true;
      return this;
    }
    async get(pk) {
      const row = await this._callAttribute("get", { pk });
      const name = row._name || row.policy?.name || `${this._name}.${pk}`;
      const proxy = this._buildModelProxy(row, this._modelProxies.get(name));
      this._modelProxies.set(name, proxy);
      return proxy;
    }
    async new(initial = {}) {
      const newItem = await this._callAttribute("new", { initial });
      const proxy = this._buildModelProxy(newItem);
      return proxy;
    }
    _syncFromResult(result = {}) {
      const items = result.items || [];
      const oldProxies = this._modelProxies;
      this._modelProxies = new Map;
      items.forEach((row, index) => {
        const name = row._name || row.policy?.name || `${this._name}.${index}`;
        const proxy = this._buildModelProxy(row, oldProxies.get(name));
        this._modelProxies.set(name, proxy);
      });
    }
    _buildModelProxy(row, existingProxy = null) {
      if (row instanceof model_default) {
        row._loaded = true;
        return row;
      }
      const rowLoadingStrategy = row.loading_strategy || this._loadingStrategy;
      let proxy = existingProxy;
      if (proxy) {
        proxy._applyResponse({
          policy: row.policy,
          state: row.state,
          metadata: row.metadata || this._metadata,
          loading_strategy: rowLoadingStrategy
        });
      } else {
        proxy = new model_default({
          http: this._http,
          policy: row.policy,
          state: row.state,
          metadata: row.metadata || this._metadata,
          client: this._client,
          owner: this,
          loadingStrategy: rowLoadingStrategy
        });
      }
      proxy._loaded = true;
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
      return this._modelProxies.size;
    }
    _cloneWithQueryParams(params = {}) {
      return new this.constructor({
        http: this._http,
        policy: this._policy,
        state: {},
        metadata: this._metadata,
        client: this._client,
        owner: this._owner,
        queryParams: this._mergeQueryParams(params),
        loadingStrategy: "lazy"
      });
    }
    _canHydrateFromState() {
      return Boolean(this._loaded && Array.isArray(this._state?.items) && !this._hasQueryParams());
    }
    _hasQueryParams() {
      return Boolean(Object.keys(this._queryParams.filter || {}).length || Object.keys(this._queryParams.slice || {}).length || this._queryParams.order_by);
    }
    _mergeQueryParams(params = {}) {
      const mergedParams = {
        ...this._queryParams,
        ...params
      };
      const filter = {
        ...this._queryParams.filter || {},
        ...params.filter || {}
      };
      const slice = {
        ...this._queryParams.slice || {},
        ...params.slice || {}
      };
      if (Object.keys(filter).length) {
        mergedParams.filter = filter;
      } else {
        delete mergedParams.filter;
      }
      if (Object.keys(slice).length) {
        mergedParams.slice = slice;
      } else {
        delete mergedParams.slice;
      }
      return mergedParams;
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
    collection: collection_default,
    form: form_default,
    function: function_default,
    json: json_default,
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
      this._directNamespaces = new Set;
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
      const response = await this.http.sendRequest(url, requestOptions);
      return response.data;
    }
    view(url, sharedPayload = {}) {
      return new view_default(this.http, url, sharedPayload);
    }
    loadManifests(manifest_list = []) {
      (manifest_list || []).forEach((manifest) => {
        this._registerManifest(manifest);
      });
    }
    _createProxy({ policy, metadata = {}, state = {}, loading_strategy = "lazy" }) {
      const namespace = policy?.namespace || metadata?.namespace;
      const ProxyClass = NAMESPACE_TO_PROXY_CLASS2[namespace] || base_default;
      if (namespace === "function") {
        return ProxyClass.create({ http: this.http, policy, metadata });
      }
      return new ProxyClass({
        http: this.http,
        policy,
        state,
        metadata,
        client: this,
        loadingStrategy: loading_strategy
      });
    }
    _registerManifest({ policy, metadata = {}, state = {}, loading_strategy = "lazy" }) {
      const name = policy?.name;
      const namespace = policy?.namespace || metadata?.namespace;
      if (!name) {
        throw new GlueProxyError("Cannot register a Glue proxy without policy.name.");
      }
      if (!namespace) {
        throw new GlueProxyError(`No Glue proxy class registered for namespace "${namespace}".`);
      }
      const manifest = { policy, metadata, state, loading_strategy };
      if (name === namespace) {
        if (namespace in this && !this._directNamespaces.has(namespace)) {
          throw new GlueProxyError(`Cannot register direct Glue proxy "${namespace}" because that namespace is already registered.`);
        }
        this._directNamespaces.add(namespace);
        Object.defineProperty(this, namespace, {
          get: () => this._createProxy(manifest),
          configurable: true
        });
        return;
      }
      if (this._directNamespaces.has(namespace)) {
        throw new GlueProxyError(`Cannot register named Glue proxy "${namespace}.${name}" because that namespace is already registered directly.`);
      }
      if (!(namespace in this)) {
        this[namespace] = {};
      }
      Object.defineProperty(this[namespace], name, {
        get: () => this._createProxy(manifest),
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
