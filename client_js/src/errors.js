class GlueHttpError extends Error {
    constructor({message, status = null, code = null, payload = null, responseBody = ''}) {
        super(`An error occurred when sending a glue http request: ${message}`);
        this.name = 'GlueHttpError';
        this.status = status;
        this.code = code;
        this.payload = payload;
        this.details = payload?.details || {};
        this.responseBody = responseBody;
        this.isGlueError = Boolean(code);
    }
}

export {GlueHttpError};
