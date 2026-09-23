class FieldGlue {
    constructor({owner, name, fieldPath = name, stateKey, metadata = {}}) {
        this.name = name
        this.fieldPath = fieldPath
        this.stateKey = stateKey || name

        Object.defineProperty(this, 'owner', {
            value: owner,
            enumerable: false,
            configurable: true,
        })
        
        this.updateMetadata(metadata)

        Object.defineProperty(this, '__glue__isFieldProxy', {
            value: true,
            enumerable: false,
            configurable: false,
        })
    }

    get value() {
        return this.owner._record.getValue(this.stateKey)
    }

    set value(value) {
        this.owner._record.setValue(this.stateKey, value)
    }

    get errors() {
        return this.owner._record.getFieldComputed(this.fieldPath).errors || []
    }

    get hasErrors() {
        return Boolean(this.errors?.length)
    }

    get errorText() {
        return this.errors.join(', ')
    }

    updateMetadata(metadata = {}) {
        for (const key of this._metadataKeys || []) delete this[key]
        const assignable = Object.fromEntries(
            Object.entries(metadata).filter(([key]) => key !== 'errors')
        )
        Object.assign(this, assignable)
        this._metadataKeys = Object.keys(assignable)
    }

    primitiveValue(hint = 'default') {
        const value = this.value
        if (value === null || value === undefined) {
            return ''
        }
        if (value instanceof Date) {
            return hint === 'number' ? value.valueOf() : value.toString()
        }
        if (typeof value === 'object') {
            return Array.isArray(value) ? value.join(',') : String(value)
        }
        return value
    }

    [Symbol.toPrimitive](hint) {
        return this.primitiveValue(hint)
    }

    toString() {
        return String(this.primitiveValue())
    }

    valueOf() {
        return this.primitiveValue()
    }

    toJSON() {
        return this.value
    }
}

export default FieldGlue
