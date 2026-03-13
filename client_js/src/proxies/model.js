import { GlueFormProxy } from "./form";

let $keyCounter = 0;

export class GlueModelProxy extends GlueFormProxy {
    constructor({
        proxyUniqueName,
        contextData,
        actions=null,
        autoFetch=false,
        values=null,
        parentQuerySet=null
    }) {
        super({proxyUniqueName, contextData, actions, autoFetch});
        this.$values = values;
        this.$key = `glue_${++$keyCounter}`;
        this.$parent = parentQuerySet;
    }

    get $isNew() {
        return !this.$values?.id;
    }

    async $get(pk = null) {
        let data;
        if (this.$parent) {
            data = await this.$parent.$processAction('get', {id: pk})
        }
        else {
            data = await this.$processAction('get')
        }

        this.$updateValues(data)

        this.$loading = false;
        this.$loaded = true;
    }

    async $delete() {
        if (this.$isNew && this.$parent) {
            // Unsaved item - just remove from parent's $items
            this.$parent.$items = this.$parent.$items.filter(item => item.$key !== this.$key);
            return { success: true };
        }
        const result = await this.$processAction('delete', {id: this.$values.id});
        if (this.$parent) {
            await this.$parent.$refresh();
        }
        return result;
    }
}