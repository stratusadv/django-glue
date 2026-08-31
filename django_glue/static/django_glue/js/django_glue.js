(() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  function __accessProp(key) {
    return this[key];
  }
  var __toCommonJS = (from) => {
    var entry = (__moduleCache ??= new WeakMap).get(from), desc;
    if (entry)
      return entry;
    entry = __defProp({}, "__esModule", { value: true });
    if (from && typeof from === "object" || typeof from === "function") {
      for (var key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(entry, key))
          __defProp(entry, key, {
            get: __accessProp.bind(from, key),
            enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable
          });
    }
    __moduleCache.set(from, entry);
    return entry;
  };
  var __moduleCache;
  var __returnValue = (v) => v;
  function __exportSetter(name, newValue) {
    this[name] = __returnValue.bind(null, newValue);
  }
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, {
        get: all[name],
        enumerable: true,
        configurable: true,
        set: __exportSetter.bind(all, name)
      });
  };

  // client_js/django_glue.js
  var exports_django_glue = {};
  __export(exports_django_glue, {
    GlueClient: () => client_default,
    parseJsonScriptById: () => parseJsonScriptById,
    resolveUrl: () => resolveUrl
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
  function resolveElement(target) {
    return typeof target === "string" ? document.querySelector(target) : target;
  }
  function htmlToFragment(html) {
    const template = document.createElement("template");
    template.innerHTML = html;
    return template.content;
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
    async sendAttributeRequest({ name, policyToken, state = null, attribute, kwargs = {} }) {
      const formData = new FormData;
      const { files, data } = this._extractFiles(serializeValue(state || {}));
      formData.append("policy_token", policyToken);
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
      const element = resolveElement(target);
      const html = await this.post(payload);
      element.replaceChildren(htmlToFragment(html));
      return html;
    }
    async renderOuterHtml(target, payload = {}) {
      const element = resolveElement(target);
      const html = await this.post(payload);
      element.replaceWith(htmlToFragment(html));
      return html;
    }
    async _renderInsertAdjacentHtml(target, position, payload = {}) {
      const element = resolveElement(target);
      const html = await this.post(payload);
      const fragment = htmlToFragment(html);
      if (position === "beforebegin") {
        element.before(fragment);
      } else if (position === "afterbegin") {
        element.prepend(fragment);
      } else if (position === "beforeend") {
        element.append(fragment);
      } else if (position === "afterend") {
        element.after(fragment);
      } else {
        throw new Error(`Invalid insert position: ${position}`);
      }
      return html;
    }
    async renderInsertAdjacentHtmlBeforeBegin(target, payload = {}) {
      return await this._renderInsertAdjacentHtml(target, "beforebegin", payload);
    }
    async renderInsertAdjacentHtmlAfterBegin(target, payload = {}) {
      return await this._renderInsertAdjacentHtml(target, "afterbegin", payload);
    }
    async renderInsertAdjacentHtmlBeforeEnd(target, payload = {}) {
      return await this._renderInsertAdjacentHtml(target, "beforeend", payload);
    }
    async renderInsertAdjacentHtmlAfterEnd(target, payload = {}) {
      return await this._renderInsertAdjacentHtml(target, "afterend", payload);
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

  // client_js/src/policy.js
  class GluePolicy {
    static fromSignedPolicyToken(token) {
      if (typeof token !== "string") {
        throw new TypeError("Glue policy token must be a string.");
      }
      const encodedPayload = token.split(":", 1)[0];
      if (!encodedPayload || encodedPayload.startsWith(".")) {
        throw new Error("Glue policy token must contain uncompressed Django signed JSON.");
      }
      const base64 = encodedPayload.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(encodedPayload.length / 4) * 4, "=");
      const binary = atob(base64);
      const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
      const payload = JSON.parse(new TextDecoder().decode(bytes));
      return this._fromDecodedPayload(payload, token);
    }
    static _fromDecodedPayload(payload, token = payload.token) {
      const attributes = (payload.attributes || []).map((attribute) => {
        if (typeof attribute !== "object" || attribute === null) {
          return attribute;
        }
        return this._fromDecodedPayload(attribute);
      });
      return new this({ ...payload, attributes, token });
    }
    constructor(data) {
      Object.assign(this, data);
    }
  }
  var policy_default = GluePolicy;

  // client_js/src/htmlResult.js
  class GlueHtmlResult {
    constructor(html) {
      this.html = html;
    }
    toString() {
      return this.html;
    }
    async renderInnerHtml(target) {
      resolveElement(target).replaceChildren(htmlToFragment(this.html));
      return this.html;
    }
    async renderOuterHtml(target) {
      resolveElement(target).replaceWith(htmlToFragment(this.html));
      return this.html;
    }
    async _renderInsertAdjacentHtml(target, position) {
      const element = resolveElement(target);
      const fragment = htmlToFragment(this.html);
      if (position === "beforebegin") {
        element.before(fragment);
      } else if (position === "afterbegin") {
        element.prepend(fragment);
      } else if (position === "beforeend") {
        element.append(fragment);
      } else if (position === "afterend") {
        element.after(fragment);
      } else {
        throw new Error(`Invalid insert position: ${position}`);
      }
      return this.html;
    }
    async renderInsertAdjacentHtmlBeforeBegin(target) {
      return await this._renderInsertAdjacentHtml(target, "beforebegin");
    }
    async renderInsertAdjacentHtmlAfterBegin(target) {
      return await this._renderInsertAdjacentHtml(target, "afterbegin");
    }
    async renderInsertAdjacentHtmlBeforeEnd(target) {
      return await this._renderInsertAdjacentHtml(target, "beforeend");
    }
    async renderInsertAdjacentHtmlAfterEnd(target) {
      return await this._renderInsertAdjacentHtml(target, "afterend");
    }
  }
  var htmlResult_default = GlueHtmlResult;

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
      if (!(policy instanceof policy_default)) {
        throw new TypeError("Glue proxies require a decoded GluePolicy instance.");
      }
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
          policyToken: this._policy.token,
          state: this._stateForAttribute(attributeMetadata.takes_client_state),
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
        }
        throw error;
      }
    }
    _stateForAttribute(takesClientState) {
      if (takesClientState === false) {
        return null;
      }
      if (Array.isArray(takesClientState)) {
        return Object.fromEntries(takesClientState.filter((key) => Object.prototype.hasOwnProperty.call(this._state || {}, key)).map((key) => [key, this._state[key]]));
      }
      return this._state;
    }
    _applyResponse(data = {}) {
      const shouldRefreshGlueObjectAttributes = Boolean(data.policy_token || data.metadata);
      if (data.policy_token) {
        this._policy = policy_default.fromSignedPolicyToken(data.policy_token);
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
      const nestedLoadingStrategy = typeof attributeMetadata.lazy === "boolean" ? attributeMetadata.lazy ? "lazy" : "eager" : proxy._loadingStrategy;
      if (proxy[cacheKey]) {
        proxy[cacheKey]._policy = attributePolicy;
        proxy[cacheKey]._applyResponse({
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
              loadingStrategy: nestedLoadingStrategy
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
        return this._client._createProxyFromManifest(result);
      }
      if (this._resultIsTemplateResponse(result)) {
        this._client.loadManifests(result.manifest_list);
        return new htmlResult_default(result.html);
      }
      Object.keys(result).forEach((key) => {
        result[key] = this._convertResultManifestsToProxies(result[key]);
      });
      return result;
    }
    _resultIsManifest(result) {
      return result?.is_glue_manifest === true;
    }
    _resultIsTemplateResponse(result) {
      return result?.is_glue_template_response === true;
    }
  }
  var base_default = BaseGlueProxy;

  // client_js/src/proxies/sequence.js
  class GlueSequenceProxy extends base_default {
    constructor(options) {
      super(options);
      this._itemProxies = new Map;
      this._syncItemsFromState();
    }
    get items() {
      return Array.from(this._itemProxies.values());
    }
    get length() {
      return this._itemProxies.size;
    }
    at(index) {
      return this.items.at(index);
    }
    [Symbol.iterator]() {
      return this._itemProxies.values();
    }
    _applyResponse(data = {}) {
      super._applyResponse(data);
      if (data.state !== undefined) {
        this._syncItemsFromState();
      }
    }
    _syncItemsFromState() {
      const manifests = this._state?.items || [];
      const oldProxies = this._itemProxies;
      const nextProxies = new Map;
      manifests.forEach((manifest, index) => {
        const policy = policy_default.fromSignedPolicyToken(manifest.policy_token);
        const key = policy.name || `${this._name}.${index}`;
        const existing = oldProxies.get(key);
        if (existing) {
          existing._policy = policy;
          existing._applyResponse({
            state: manifest.state,
            metadata: manifest.metadata,
            loading_strategy: manifest.loading_strategy
          });
          nextProxies.set(key, existing);
          return;
        }
        const ProxyClass = getProxyClass(policy.namespace) || base_default;
        nextProxies.set(key, new ProxyClass({
          http: this._http,
          policy,
          state: manifest.state,
          metadata: manifest.metadata,
          owner: this,
          client: this._client,
          loadingStrategy: manifest.loading_strategy || this._loadingStrategy
        }));
      });
      this._itemProxies = nextProxies;
    }
  }
  var sequence_default = GlueSequenceProxy;

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
      if (this.choice_model_path && !this._choicesOverridden) {
        this.ensureChoices([]);
      }
      return this._choices || [];
    }
    set choices(value) {
      this._choices = value;
    }
    overrideChoices(choices) {
      this._choices = Array.isArray(choices) ? choices : [];
      this._choicesOverridden = true;
      return this._choices;
    }
    clearChoicesOverride() {
      this._choicesOverridden = false;
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
    get hasMoreChoices() {
      if (this._searchActive) {
        return Boolean(this._searchHasNext);
      }
      return Boolean(this._getOrCreateCache(this._getChoicesCacheKey()).hasNext);
    }
    get isLoadingMoreChoices() {
      return Boolean(this._loadMorePromise);
    }
    get isSearchingChoices() {
      return Boolean(this._searchPromise);
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
        choice_fields: this._serverChoiceFields(missingFields),
        batch_size: this.choices_batch_size ?? null
      }).then((result) => {
        const { results = [], has_next: hasNext = false, seek_key: seekKey = null } = result || {};
        this._mergeChoices(results);
        cache.hasNext = hasNext;
        cache.seekKey = seekKey;
        requiredFields.forEach((f) => cache.loadedFields.add(f));
        return this._choices || [];
      }).finally(() => {
        cache.promise = null;
      });
      return cache.promise;
    }
    async loadMoreChoices(choiceFields = []) {
      if (this._loadMorePromise) {
        return this._loadMorePromise;
      }
      if (this._searchActive) {
        if (!this._searchHasNext) {
          return this._choices || [];
        }
        this._loadMorePromise = this.owner.foreign_key_choices({
          field_name: this.name,
          choice_fields: this._serverChoiceFields(this._choiceObjectFields(choiceFields)),
          search: this._searchQuery,
          search_field: this._searchField,
          seek_key: this._searchSeekKey,
          batch_size: this.choices_batch_size ?? null
        }).then((result) => {
          const { results = [], has_next: hasNext = false, seek_key: seekKey = null } = result || {};
          this._searchHasNext = hasNext;
          this._searchSeekKey = seekKey;
          return this.overrideChoices([...this._choices || [], ...results]);
        }).finally(() => {
          this._loadMorePromise = null;
        });
        return this._loadMorePromise;
      }
      const cacheKey = this._getChoicesCacheKey();
      const cache = this._getOrCreateCache(cacheKey);
      if (!cache.hasNext || cache.promise) {
        return this._choices || [];
      }
      this._loadMorePromise = cache.promise = this.owner.foreign_key_choices({
        field_name: this.name,
        choice_fields: this._serverChoiceFields([...cache.loadedFields]),
        seek_key: cache.seekKey,
        batch_size: this.choices_batch_size ?? null
      }).then((result) => {
        const { results = [], has_next: hasNext = false, seek_key: seekKey = null } = result || {};
        cache.hasNext = hasNext;
        cache.seekKey = seekKey;
        this._mergeChoices(results);
        return this._choices || [];
      }).finally(() => {
        cache.promise = null;
        this._loadMorePromise = null;
      });
      return this._loadMorePromise;
    }
    async searchChoices(query, searchField, choiceFields = []) {
      if (!query) {
        return this.clearSearch();
      }
      this._searchActive = true;
      this._searchQuery = query;
      this._searchField = searchField;
      this._searchSeekKey = null;
      this._searchPromise = this.owner.foreign_key_choices({
        field_name: this.name,
        choice_fields: this._serverChoiceFields(this._choiceObjectFields(choiceFields)),
        search: query,
        search_field: searchField,
        batch_size: this.choices_batch_size ?? null
      }).then((result) => {
        const { results = [], has_next: hasNext = false, seek_key: seekKey = null } = result || {};
        this._searchHasNext = hasNext;
        this._searchSeekKey = seekKey;
        return this.overrideChoices(results);
      }).finally(() => {
        this._searchPromise = null;
      });
      return this._searchPromise;
    }
    clearSearch() {
      this._searchActive = false;
      this._searchQuery = "";
      this._searchField = "";
      this._searchSeekKey = null;
      this._searchHasNext = false;
      this.clearChoicesOverride();
      return this.choices;
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
    _serverChoiceFields(fields = []) {
      return fields.filter((f) => !["value", "label", "pk", "__str__"].includes(f));
    }
    _getOrCreateCache(cacheKey) {
      let cache = RelationFieldGlue.loadingCache.get(cacheKey);
      if (!cache) {
        cache = {
          loadedFields: new Set,
          promise: null,
          choices: [],
          fields: new Set,
          hasNext: false,
          seekKey: null
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
      this._loadAttempted = false;
      this._loadError = null;
      this._loadPromise = null;
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
      if (this._loaded || this._loadAttempted) {
        return this._loadPromise;
      }
      this._loadAttempted = true;
      this.loading = true;
      this._loadPromise = this._callAttribute("load_state").catch((error) => {
        this._loadError = error;
      }).finally(() => {
        this.loading = false;
      });
      return this._loadPromise;
    }
    retryLoad() {
      this._loadAttempted = false;
      this._loadError = null;
      return this._ensureLoaded();
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

  // client_js/src/proxies/formset.js
  class GlueFormSetProxy extends base_default {
    constructor(options) {
      super(options);
      this._formProxyCache = new Map;
      this._formProxies = this._initialForms();
      this._nextKey = this._formProxies.size;
      this.nonFormErrors = [];
      this._hasPendingLocalEdit = false;
    }
    get forms() {
      return Array.from(this._formProxies.values());
    }
    get length() {
      return this._formProxies.size;
    }
    async append(initial = {}) {
      const key = String(this._nextKey++);
      const form = await this._callAttribute("append", { key, initial });
      this._formProxies = new Map(this._formProxies).set(key, form);
      this._hasPendingLocalEdit = true;
      return form;
    }
    pop(key) {
      const entry = Array.from(this._formProxies.entries()).find(([, form]) => form.$key === key);
      if (!entry)
        return;
      const [mapKey, removed] = entry;
      const nextEntries = Array.from(this._formProxies.entries()).filter(([existingKey]) => existingKey !== mapKey);
      this._formProxies = new Map(nextEntries);
      this._hasPendingLocalEdit = true;
      return removed;
    }
    async validate() {
      const result = await this._callAttribute("validate");
      this._formProxies = new Map((result?.form_list || []).map((form, index) => [String(index), form]));
      this._hasPendingLocalEdit = false;
      this.nonFormErrors = result?.non_form_errors || [];
      return result;
    }
    _stateForAttribute(takesClientState) {
      if (takesClientState === false) {
        return null;
      }
      return { form_list: this.forms.map((form) => form._state) };
    }
    _applyResponse(data = {}) {
      super._applyResponse(data);
      if (this._hasPendingLocalEdit || !(data.policy_token || data.metadata || data.state))
        return;
      this._formProxies = this._initialForms();
    }
    _initialForms() {
      if (!this._formProxyCache) {
        this._formProxyCache = new Map;
      }
      const formPolicies = (this._policy?.attributes || []).filter((attribute) => typeof attribute !== "string" && attribute.namespace === "form");
      const currentKeys = new Set(formPolicies.map((policy, index) => policy.name || `${this._name}.${index}`));
      Array.from(this._formProxyCache.keys()).forEach((key) => {
        if (!currentKeys.has(key)) {
          this._formProxyCache.delete(key);
        }
      });
      return new Map(formPolicies.map((policy, index) => [String(index), this._buildFormProxy(policy, index)]));
    }
    _buildFormProxy(policy, index) {
      const attributeKey = `form_list.${index}`;
      const metadata = this._metadata?.attributes?.[attributeKey]?.metadata || {};
      const state = this._state?.[attributeKey] || {};
      const ProxyClass = getProxyClass(policy.namespace) || base_default;
      const cacheKey = policy.name || `${this._name}.${index}`;
      const cachedForm = this._formProxyCache.get(cacheKey);
      if (cachedForm) {
        if (cachedForm.policy !== policy || cachedForm.state !== state || cachedForm.metadata !== metadata) {
          cachedForm.proxy._policy = policy;
          cachedForm.proxy._applyResponse({ state, metadata, loading_strategy: this._loadingStrategy });
          cachedForm.policy = policy;
          cachedForm.state = state;
          cachedForm.metadata = metadata;
        }
        return cachedForm.proxy;
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
      this._formProxyCache.set(cacheKey, {
        proxy,
        policy,
        state,
        metadata
      });
      return proxy;
    }
  }
  var formset_default = GlueFormSetProxy;

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
  var QUERY_CACHE_LIMIT = 64;

  class GlueQuerySetProxy extends base_default {
    constructor(options) {
      super(options);
      this._modelProxies = new Map;
      this._queryParams = options.queryParams || {};
      this._queryCache = options.queryCache || new Map([[JSON.stringify(this._queryParams), this]]);
      this._seekKey = null;
      this._hasNext = false;
      this._batchSize = null;
      this._total = null;
      this.loading = false;
      if (options.seed) {
        this._seedFrom(options.seed);
      }
      if (this._canHydrateFromState()) {
        this._syncFromResult(this._state);
      }
    }
    get items() {
      return Array.from(this);
    }
    get batchSize() {
      return this._batchSize;
    }
    get hasNext() {
      return this._hasNext;
    }
    get total() {
      return this._total;
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
    async all({ withTotal = false } = {}) {
      if (this._loaded) {
        return this;
      }
      const params = withTotal ? { ...this._queryParams, with_total: true } : this._queryParams;
      const result = await this.query_with_params(params);
      this._syncFromResult(result);
      this._loaded = true;
      return this;
    }
    async refresh() {
      for (const proxy of this._queryCache.values()) {
        proxy._loaded = false;
      }
      return this.all();
    }
    async loadMore() {
      if (this.loading) {
        return this;
      }
      if (!this._loaded) {
        return this.all();
      }
      if (!this.hasNext) {
        return this;
      }
      this.loading = true;
      try {
        const result = await this.query_with_params({ ...this._queryParams, seek_key: this._seekKey });
        this._syncFromResult(result, { append: true });
      } finally {
        this.loading = false;
      }
      return this;
    }
    async get(pk) {
      const row = await this._callAttribute("get", { pk });
      const policy = this._policyForRow(row);
      const name = row._name || policy.name || `${this._name}.${pk}`;
      const proxy = this._buildModelProxy(row, this._modelProxies.get(name), policy);
      this._modelProxies.set(name, proxy);
      return proxy;
    }
    async new(initial = {}) {
      const newItem = await this._callAttribute("new", { initial });
      const proxy = this._buildModelProxy(newItem);
      return proxy;
    }
    async count() {
      return this._callAttribute("count", { filter: this._queryParams.filter });
    }
    _applyResponse(data = {}) {
      super._applyResponse(data);
      if (data.state !== undefined && this._canHydrateFromState()) {
        this._syncFromResult(this._state);
      }
    }
    _seedFrom(source) {
      this._modelProxies = new Map(source._modelProxies);
      this._batchSize = source._batchSize;
    }
    _syncFromResult(result = {}, { append = false } = {}) {
      const items = result.items || [];
      const oldProxies = this._modelProxies;
      this._modelProxies = append ? new Map(oldProxies) : new Map;
      this._seekKey = result.seek_key ?? null;
      this._hasNext = result.has_next ?? false;
      this._batchSize = result.batch_size ?? null;
      if ("total" in result) {
        this._total = result.total;
      }
      items.forEach((row, index) => {
        const policy = this._policyForRow(row);
        const name = row._name || policy.name || `${this._name}.${index}`;
        const proxy = this._buildModelProxy(row, oldProxies.get(name), policy);
        this._modelProxies.set(name, proxy);
      });
    }
    _policyForRow(row) {
      if (row instanceof model_default) {
        return row._policy;
      }
      return policy_default.fromSignedPolicyToken(row.policy_token);
    }
    _buildModelProxy(row, existingProxy = null, policy = this._policyForRow(row)) {
      if (row instanceof model_default) {
        row._loaded = true;
        return row;
      }
      const rowLoadingStrategy = row.loading_strategy || this._loadingStrategy;
      let proxy = existingProxy;
      if (proxy) {
        proxy._applyResponse({
          policy_token: row.policy_token,
          state: row.state,
          metadata: row.metadata || this._metadata,
          loading_strategy: rowLoadingStrategy
        });
      } else {
        proxy = new model_default({
          http: this._http,
          policy,
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
      const queryParams = this._mergeQueryParams(params);
      const key = JSON.stringify(queryParams);
      if (!this._queryCache.has(key)) {
        this._queryCache.set(key, this._cloneWithQueryParams(queryParams));
        this._evictQueryCache();
      }
      return this._queryCache.get(key);
    }
    _evictQueryCache() {
      for (const key of this._queryCache.keys()) {
        if (this._queryCache.size <= QUERY_CACHE_LIMIT) {
          return;
        }
        if (key !== "{}" && this._queryCache.get(key) !== this) {
          this._queryCache.delete(key);
        }
      }
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
    _cloneWithQueryParams(queryParams = {}) {
      return new this.constructor({
        http: this._http,
        policy: this._policy,
        state: {},
        metadata: this._metadata,
        client: this._client,
        owner: this._owner,
        queryParams,
        queryCache: this._queryCache,
        seed: this,
        loadingStrategy: "lazy"
      });
    }
    _canHydrateFromState() {
      return Boolean(this._loaded && Array.isArray(this._state?.items) && !this._hasQueryParams());
    }
    _hasQueryParams() {
      return Object.keys(this._queryParams).length > 0;
    }
    _mergeQueryParams(params = {}) {
      const filter = {
        ...this._queryParams.filter || {},
        ...params.filter || {}
      };
      const orderBy = params.order_by ?? this._queryParams.order_by;
      const slice = {
        ...this._queryParams.slice || {},
        ...params.slice || {}
      };
      const mergedParams = {};
      if (Object.keys(filter).length) {
        mergedParams.filter = filter;
      }
      if (orderBy) {
        mergedParams.order_by = orderBy;
      }
      if (Object.keys(slice).length) {
        mergedParams.slice = slice;
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
    async _renderInsertAdjacentHtml(selector, position, payload = {}) {
      const element = typeof selector === "string" ? document.querySelector(selector) : selector;
      const html = await this.renderHtml(payload);
      element.insertAdjacentHTML(position, html);
      return html;
    }
    async renderInsertAdjacentHtmlBeforeBegin(selector, payload = {}) {
      return await this._renderInsertAdjacentHtml(selector, "beforebegin", payload);
    }
    async renderInsertAdjacentHtmlAfterBegin(selector, payload = {}) {
      return await this._renderInsertAdjacentHtml(selector, "afterbegin", payload);
    }
    async renderInsertAdjacentHtmlBeforeEnd(selector, payload = {}) {
      return await this._renderInsertAdjacentHtml(selector, "beforeend", payload);
    }
    async renderInsertAdjacentHtmlAfterEnd(selector, payload = {}) {
      return await this._renderInsertAdjacentHtml(selector, "afterend", payload);
    }
  }
  var template_default = GlueTemplateProxy;

  // client_js/src/proxies/index.js
  var NAMESPACE_TO_PROXY_CLASS2 = {
    sequence: sequence_default,
    form: form_default,
    formSet: formset_default,
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
    _createProxyFromManifest({ policy_token, metadata = {}, state = {}, loading_strategy = "lazy" }) {
      return this._createProxy({
        policy: policy_default.fromSignedPolicyToken(policy_token),
        metadata,
        state,
        loading_strategy
      });
    }
    _registerManifest({ policy_token, metadata = {}, state = {}, loading_strategy = "lazy" }) {
      const policy = policy_default.fromSignedPolicyToken(policy_token);
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
          enumerable: true,
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
        enumerable: true,
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
