import FieldBackedGlueProxy from "./fieldBacked"

class GlueModelProxy extends FieldBackedGlueProxy {
    async delete() {
        const result = await this._callAttribute('delete')
        this.$collection?._removeRowProxy(this)
        return result
    }
}

export default GlueModelProxy
