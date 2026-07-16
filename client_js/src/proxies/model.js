import FieldBackedGlueProxy from "./fieldBacked"

class GlueModelProxy extends FieldBackedGlueProxy {
    async save() {
        return await this._call('save')
    }

    async validate() {
        return await this._call('validate')
    }

    async delete() {
        const result = await this._call('delete')
        this.$collection?._removeRowProxy(this)
        return result
    }
}

export default GlueModelProxy
