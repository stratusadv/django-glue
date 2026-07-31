import ChoiceFieldGlue from "./choice"

class RelationFieldGlue extends ChoiceFieldGlue {
    // Static cache tracks loading state only, not data
    static loadingCache = new Map()

    get choices() {
        if (this.choice_model_path) {
            this.ensureChoices([])
        }
        return this._choices || []
    }

    set choices(value) {
        this._choices = value
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
        const pk = this.pk
        if (pk == null) return undefined
        return (this._choices || []).find(choice => Number(choice.pk) === Number(pk))
    }

    get selectedLabel() {
        return this.selectedChoice?.__str__ ?? ''
    }

    buildChoices(...choiceFields) {
        this.ensureChoices(choiceFields)
        return this.choices
    }

    ensureChoices(choiceFields = []) {
        const cacheKey = this._getChoicesCacheKey()
        const cache = this._getOrCreateCache(cacheKey)
        cache.fields.add(this)

        if (this._choices !== cache.choices) {
            this.choices = cache.choices
        }

        const requiredFields = this._normalizeChoiceFields(choiceFields)
        const missingFields = requiredFields.filter(f => !cache.loadedFields.has(f))

        if (missingFields.length === 0) {
            return cache.promise || Promise.resolve(this._choices || [])
        }

        if (cache.promise) {
            return cache.promise.then(() => this.ensureChoices(choiceFields))
        }

        if (typeof this.owner.foreign_key_choices !== 'function') {
            return Promise.resolve(this._choices || [])
        }

        cache.promise = this.owner.foreign_key_choices({
            field_name: this.name,
            choice_fields: missingFields.filter(f => !['pk', '__str__'].includes(f)),
        }).then(result => {
            const newChoices = Array.isArray(result) ? result : []
            this._mergeChoices(newChoices)
            requiredFields.forEach(f => cache.loadedFields.add(f))
            return this._choices || []
        }).finally(() => {
            cache.promise = null
        })

        return cache.promise
    }

    _getChoicesCacheKey() {
        return this.choices_cache_key || [
            this.owner._policy.identity.model_class_path,
            this.owner._policy.identity.form_class_path,
            this.choice_model_path,
            this.name,
        ].filter(Boolean).join(':')
    }

    _normalizeChoiceFields(choiceFields = []) {
        return [...new Set(['pk', '__str__', ...choiceFields.filter(Boolean)])]
    }

    _getOrCreateCache(cacheKey) {
        let cache = RelationFieldGlue.loadingCache.get(cacheKey)
        if (!cache) {
            cache = {
                loadedFields: new Set(),
                promise: null,
                choices: [],
                fields: new Set(),
            }
            RelationFieldGlue.loadingCache.set(cacheKey, cache)
        }
        return cache
    }

    _mergeChoices(newChoices) {
        const cache = this._getOrCreateCache(this._getChoicesCacheKey())
        const current = cache.choices
        const merged = [...current]

        newChoices.forEach(choice => {
            if (!choice || typeof choice !== 'object') return
            const existing = merged.find(item => item.pk === choice.pk)
            if (existing) {
                Object.assign(existing, choice)
            } else {
                merged.push(choice)
            }
        })

        cache.choices = merged

        for (const field of cache.fields) {
            field.choices = cache.choices
        }
    }
}

export default RelationFieldGlue
