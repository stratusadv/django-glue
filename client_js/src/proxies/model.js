import FieldBackedGlueProxy from "./fieldBacked"

class GlueModelProxy extends FieldBackedGlueProxy {
    _configureAttributeInitializers() {
        super._configureAttributeInitializers()
        this._attributeBuilders.readable = (owner, name, qualName) => {
            this._initializeReadableAttribute(owner, name, qualName)
        }
    }

    _initializeReadableAttribute(owner, attributeName, attributeQualName) {
        const proxy = this
        Object.defineProperty(owner, attributeName, {
            get() {
                return proxy._state?.[attributeQualName]?.value
            },
            enumerable: true,
            configurable: true,
        })
    }

    async delete() {
        const result = await this._callAttribute('delete')
        this.$collection?._removeModelProxy(this)
        return result
    }
}

export default GlueModelProxy
