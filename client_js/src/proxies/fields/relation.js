import ChoiceFieldGlue from "./choice"

class RelationFieldGlue extends ChoiceFieldGlue {
    static choicesCache = new Map()

    updateMetadata(metadata = {}) {
        super.updateMetadata(metadata)
        this._initializeChoices()
    }

    get pk() {
        const value = this.value
        if (value && typeof value === 'object') {
            return value.pk ?? value.id
        }
        return value
    }

    set pk(value) {
        this.value = value
    }

    get selectedChoice() {
        const pk = Number(this.pk)
        return (this.choices || []).find(choice => Number(choice.pk) === pk)
    }

    get selectedLabel() {
        return this.selectedChoice?.__str__ ?? ''
    }

    buildChoices(...choiceFields) {
        this.ensureChoices(choiceFields, this)
        return this.choices
    }

    ensureChoices(choiceFields = [], subscriber = this) {
        const cacheKey = this._getChoicesCacheKey()
        const cached = this._getOrCreateChoicesCache(cacheKey)
        cached.fields.add(subscriber)
        const requiredFields = this._normalizeChoiceFields(choiceFields)
        const missingFields = requiredFields.filter(choiceField => !cached.loadedFields.has(choiceField))

        if (missingFields.length === 0) {
            subscriber._applyCachedChoices(cached)
            return cached.promise || Promise.resolve(cached.data)
        }

        if (cached.promise) {
            subscriber.__glue__loadingChoices = true
            return cached.promise.then(() => this.ensureChoices(choiceFields, subscriber))
        }

        if (typeof this.owner.foreign_key_choices !== 'function') {
            return Promise.resolve(cached.data)
        }

        subscriber.__glue__loadingChoices = true
        missingFields.forEach(choiceField => cached.pendingFields.add(choiceField))

        cached.promise = this.owner.foreign_key_choices({
            field_name: this.name,
            choice_fields: missingFields.filter(choiceField => !['pk', '__str__'].includes(choiceField)),
        }).then(result => {
            const choices = Array.isArray(result) ? result : []
            this._cacheChoices(choices, missingFields)
            return cached.data
        }).finally(() => {
            missingFields.forEach(choiceField => cached.pendingFields.delete(choiceField))
            cached.promise = null
            subscriber.__glue__loadingChoices = false
        })

        return cached.promise
    }

    _initializeChoices() {
        const cacheKey = this._getChoicesCacheKey()
        const cached = RelationFieldGlue.choicesCache.get(cacheKey)
        const initialChoices = Array.isArray(this.__glue__choicesData)
            ? this.__glue__choicesData
            : Array.isArray(this.choices)
                ? this.choices
                : []

        this.__glue__choicesCacheKey = cacheKey
        this.__glue__choicesLoaded = Boolean(cached?.loadedFields?.has('__str__'))
        this.__glue__loadingChoices = Boolean(cached?.promise)
        this.__glue__choicesData = cached?.data || initialChoices
        this.choices = cached?.data || initialChoices
    }

    _getChoicesCacheKey() {
        return this.choices_cache_key
            || [
                this.owner.$policy?.identity?.model_class_path,
                this.owner.$policy?.identity?.form_class_path,
                this.choice_model_path,
                this.name,
            ].filter(Boolean).join(':')
            || `${this.type}:${this.name}`
    }

    _normalizeChoiceFields(choiceFields = []) {
        return ['pk', '__str__', ...choiceFields].filter((choiceField, index, fields) => {
            return choiceField && fields.indexOf(choiceField) === index
        })
    }

    _getOrCreateChoicesCache(cacheKey) {
        let cached = RelationFieldGlue.choicesCache.get(cacheKey)
        if (!cached) {
            cached = {
                data: this.__glue__choicesData || [],
                fields: new Set(),
                loadedFields: new Set(),
                pendingFields: new Set(),
                promise: null,
            }
            RelationFieldGlue.choicesCache.set(cacheKey, cached)
        }
        return cached
    }

    _applyCachedChoices(cached, {force = false} = {}) {
        const previousChoices = this.__glue__choicesData
        this.__glue__choicesLoaded = cached.loadedFields.has('__str__')
        this.__glue__loadingChoices = Boolean(cached.promise)
        if (force || previousChoices !== cached.data) {
            this.choices = cached.data
        } else {
            this.__glue__choicesData = cached.data
        }
    }

    _cacheChoices(choices, choiceFields = []) {
        const cached = this._getOrCreateChoicesCache(this._getChoicesCacheKey())
        const nextChoices = [...cached.data]
        choices.forEach(choice => this._mergeChoice(nextChoices, choice))
        cached.data = nextChoices
        this._normalizeChoiceFields(choiceFields).forEach(choiceField => cached.loadedFields.add(choiceField))
        cached.fields.forEach(field => {
            field._applyCachedChoices(cached, {force: true})
        })
    }

    _mergeChoice(choices, choice) {
        if (!choice || typeof choice !== 'object') {
            return
        }
        const existing = choices.find(item => item.pk === choice.pk)
        if (existing) {
            Object.assign(existing, choice)
        } else {
            choices.push(choice)
        }
    }
}

export default RelationFieldGlue
