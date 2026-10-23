import type GlueAddressRecord from "../../runtime/addressRecord"
import type {GlueFieldComputed, GlueFieldDescriptor} from "../../wire"

// What a field needs of the proxy that owns it.
interface GlueFieldOwner {
    _record: GlueAddressRecord
}

// A field's server metadata: its static descriptor merged with its computed
// output.
type GlueFieldMetadata = Partial<GlueFieldDescriptor & GlueFieldComputed>

interface GlueFieldOptions {
    owner: GlueFieldOwner
    name: string
    fieldPath?: string
    stateKey?: string
    metadata?: GlueFieldMetadata
}

// updateMetadata() copies the metadata onto the field, except the keys a
// field class defines itself.
interface FieldGlue extends Omit<GlueFieldMetadata, 'errors' | 'choices'> {}

class FieldGlue {
    name: string
    fieldPath: string
    stateKey: string
    declare owner: GlueFieldOwner
    declare _metadataKeys: string[] | undefined
    declare readonly __glue__isFieldProxy: true

    constructor({owner, name, fieldPath = name, stateKey, metadata = {}}: GlueFieldOptions) {
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

    get value(): unknown {
        return this.owner._record.getValue(this.stateKey)
    }

    set value(value: unknown) {
        this.owner._record.setValue(this.stateKey, value)
    }

    get errors(): string[] {
        return this.owner._record.getFieldComputed(this.fieldPath).errors || []
    }

    get hasErrors(): boolean {
        return Boolean(this.errors?.length)
    }

    get errorText(): string {
        return this.errors.join(', ')
    }

    // Server metadata lands as plain data properties and never writes through
    // or shadows a member the field class defines (errors, choices, value...):
    // those own client-side state that a refresh must not reset.
    updateMetadata(metadata: GlueFieldMetadata = {}): void {
        const members = this as unknown as Record<string, unknown>
        for (const key of this._metadataKeys || []) delete members[key]
        const prototype = Object.getPrototypeOf(this)
        const assignable = Object.fromEntries(
            Object.entries(metadata).filter(([key]) => !(key in prototype))
        )
        Object.assign(this, assignable)
        this._metadataKeys = Object.keys(assignable)
    }

    primitiveValue(hint = 'default'): unknown {
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

    [Symbol.toPrimitive](hint: string): unknown {
        return this.primitiveValue(hint)
    }

    toString(): string {
        return String(this.primitiveValue())
    }

    valueOf(): unknown {
        return this.primitiveValue()
    }

    toJSON(): unknown {
        return this.value
    }
}

export type {GlueFieldMetadata, GlueFieldOptions, GlueFieldOwner}
export default FieldGlue
