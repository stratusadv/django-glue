class FieldGlue {
    constructor({owner, name, stateKey, metadata = {}}) {
        this.name = name
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
        return this.owner._state?.[this.stateKey]?.value
    }

    set value(value) {
        if (!this.owner._state) {
            this.owner._state = {}
        }
        if (!this.owner._state[this.stateKey]) {
            this.owner._state[this.stateKey] = {}
        }
        this.owner._state[this.stateKey].value = value
    }

    get errors() {
        return this.owner._state?.[this.stateKey]?.errors || []
    }

    get hasErrors() {
        return Boolean(this.errors?.length)
    }

    get errorText() {
        return this.errors.join(', ')
    }

    updateMetadata(metadata = {}) {
        Object.assign(this, metadata)
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
