// django_glue/client/src/constants.js
var baseUrlPath = "django_glue";
var actionUrl = `/${baseUrlPath}/`;

// django_glue/client/src/http-client.js
function getHttpCookie(name2) {
  if (document?.cookie !== "") {
    const cookies = document.cookie.split(";").map((cookie) => cookie.trim());
    for (const cookie of cookies) {
      if (cookie.substring(0, name2.length + 1) === name2 + "=") {
        return decodeURIComponent(cookie.substring(name2.length + 1));
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

// django_glue/client/src/config.js
var ModelGlue = class {
  constructor(uniqueName) {
    this.glue = glueServerData.session[uniqueName];
    this.loaded = false;
    this.loading = false;
    this.values = {};
    this.actionPayloads = {};
    Object.keys(glueServerData.context[uniqueName].actions).forEach((actionName) => {
      Object.defineProperty(this, actionName, {
        value: async function(payload = null) {
          const requestData = {
            unique_name: uniqueName,
            action: actionName,
            payload: actionName in this.actionPayloads ? this.actionPayloads[actionName] : null
          };
          const response = await sendActionRequest(requestData);
          if (response.ok) {
            return response.data;
          } else {
            console.error(`An error occurred when performing ${name} on target ${uniqueName}: ${response}`);
            return null;
          }
        }
      });
    });
    Object.keys(glueServerData.context[uniqueName].fields).forEach((fieldName) => {
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
          this.actionPayloads["save"] = this.values;
        }
      });
    });
  }
};

// django_glue/client/src/glue.js
var DjangoGlue = class {
  initialized = false;
  targetConstructors = {};
  async init() {
    this.registerTargetConstructor("Model", ModelGlue);
    this.initialized = true;
  }
  registerTargetConstructor(targetClassName, targetConstructor) {
    if (this.initialized) {
      throw Error("Custom target class handler registration is not allowed after initialization.");
    }
    this.targetConstructors[targetClassName] = targetConstructor;
  }
};
var Glue = new Proxy(new DjangoGlue(), {
  get(target, name2) {
    if (name2 in glueServerData.session) {
      const glue = glueServerData.session[name2];
      console.log(target.targetConstructors[glue.target_class]);
      return new target.targetConstructors[glue.target_class](glue.unique_name);
    } else {
      return Reflect.get(target, name2);
    }
  }
});
var glue_default = Glue;

// django_glue/client/src/index.js
var src_default = glue_default;

// django_glue/client/builds/module.js
var module_default = src_default;
export {
  src_default as Glue,
  module_default as default
};
