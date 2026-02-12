(() => {
  // client_js/src/constants.js
  var baseUrlPath = "django_glue";
  var actionUrl = `/${baseUrlPath}/`;

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
    csrfProtected: true
  }) {
    const options = {
      method: requestOptions.method,
      headers: {
        "Content-Type": requestOptions.contentType
      }
    };
    if (options.method === "POST") {
      options.body = requestOptions.body;
    }
    if (requestOptions.csrfProtected) {
      options.headers["X-CSRFToken"] = getHttpCookie("csrftoken");
    }
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

  // client_js/src/adapters/base.js
  var BaseGlueAdapter = class {
    constructor(uniqueName) {
      this.uniqueName = uniqueName;
      this.contextData = glueServerData.context[uniqueName];
      this.sessionData = glueServerData.session[uniqueName];
      this.actions = {};
      Object.keys(this.contextData.actions).forEach((actionName) => {
        this.actions[actionName] = { payload: null, name: actionName };
        Object.defineProperty(this, actionName, {
          value: (payload) => this.actionFunctionTemplate(actionName, payload)
        });
      });
      this.postInit();
    }
    setActionPayload(actionName, payload) {
      this.actions[actionName].payload = payload;
    }
    getActionPayload(actionName) {
      return this.actions[actionName].payload;
    }
    async actionFunctionTemplate(actionName, payload = null) {
      const requestData = {
        unique_name: this.uniqueName,
        action: actionName,
        payload: this.getActionPayload(actionName)
      };
      const response = await sendActionRequest(requestData);
      if (response.ok) {
        return response.data;
      } else {
        console.error(`An error occurred when performing ${actionName} on target ${this.uniqueName}: ${response}`);
        return null;
      }
    }
    postInit() {
    }
  };

  // client_js/src/utils.js
  function getClassByName(name) {
    if (name.match(/^[a-zA-Z0-9_]+$/) && Object.values(adapterTypeConfig).includes(name)) {
      return eval?.(`"use strict";(${name})`);
    } else {
      throw new Error(`ALERT: DANGEROUS STRING PASSED INTO 'getClassByName': '${name}'`);
    }
  }

  // client_js/src/manager.js
  var GlueAdapterManager = class {
    #adapterTypeRegistry = {};
    #adapterInstances = {};
    addAdapter(typeName, typeClass) {
      if (!(typeClass.prototype instanceof BaseGlueAdapter)) {
        throw Error(`The class registered ('${typeClass}') for the adapter type '${typeName}' does not extend BaseGlueAdapter.`);
      }
      this.#adapterTypeRegistry[typeName] = typeClass;
    }
    #registerAdapterTypes() {
      this.#adapterTypeRegistry = {};
      Object.entries(adapterTypeConfig).forEach(([typeName, typeClass]) => {
        this.addAdapter(typeName, getClassByName(typeClass));
      });
    }
    #createAdapterInstance(adapterUniqueName, adapterType) {
      return new this.#adapterTypeRegistry[adapterType](adapterUniqueName);
    }
    #defineAdapterUniqueNameAsProperty(glueSessionData) {
      Object.defineProperty(this, glueSessionData.unique_name, {
        get: function() {
          if (!(glueSessionData.unique_name in this.#adapterInstances)) {
            this.#adapterInstances[glueSessionData.unique_name] = this.#createAdapterInstance(
              glueSessionData.unique_name,
              glueSessionData.target_class
            );
          }
          return this.#adapterInstances[glueSessionData.unique_name];
        }
      });
    }
    #loadSession() {
      for (const glueSessionData of Object.values(glueServerData.session)) {
        this.#defineAdapterUniqueNameAsProperty(glueSessionData);
      }
    }
    // TODO: pass data and type config from global scope as parameters to make this more
    // explicitly defined
    init() {
      this.#registerAdapterTypes();
      this.#loadSession();
    }
  };
  var manager_default = GlueAdapterManager;

  // client_js/src/adapters/model.js
  var ModelGlueAdapter = class extends BaseGlueAdapter {
    // TODO: Clean this up
    postInit() {
      Object.keys(this.contextData.fields).forEach((fieldName) => {
        Object.defineProperty(this, fieldName, {
          get: function() {
            if (!this.loaded) {
              if (!this.loading) {
                this.loading = true;
                this.get().then((data) => {
                  this.values = data;
                }).finally(() => {
                  this.loading = false;
                  this.loaded = true;
                });
              }
            }
            return this.values?.[fieldName];
          },
          set: function(value) {
            if (!this.values) {
              this.values = {};
            }
            this.values[fieldName] = value;
            this.setActionPayload("save", this.values);
          }
        });
      });
    }
  };

  // client_js/glue.js
  window.ModelGlueAdapter = ModelGlueAdapter;
  var Glue = new manager_default();
  window.Glue = Glue;
})();
