import { GlueFormProxy } from "./form";

export class GlueModelProxy extends GlueFormProxy {
    constructor({
        proxyUniqueName,
        contextData,
        actions=null,
        autoFetch=false,
        values=null
    }) {
        super({proxyUniqueName, contextData, actions, autoFetch});
        this._values = values
    }

    async delete() {
        return await this.processAction('delete', {id: this.values.id});
    }
}