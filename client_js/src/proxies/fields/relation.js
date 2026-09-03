import ChoiceFieldGlue from "./choice"

class RelationFieldGlue extends ChoiceFieldGlue {
    // Static cache tracks loading state only, not data
    static loadingCache = new Map()

    get choices() {
        if (this.choice_model_path && !this._choicesOverridden) {
            this.ensureChoices()
        }
        return this._choices || []
    }

    set choices(value) {
        this._choices = value
    }

    // Explicitly assigns this field's choices and keeps them from being
    // clobbered by ensureChoices() -- the choices getter otherwise
    // self-heals from a shared, cache-key-scoped cache on every read
    // (including incidental reads from template re-renders), which
    // silently overwrites anything assigned outside that cache. Use this
    // when a caller (e.g. a glue-callable-backed dependent-choices reload,
    // or an active search -- see searchChoices()) is the authoritative
    // source for this field's choices right now, instead of the field's
    // own default foreign_key_choices() lookup.
    overrideChoices(choices) {
        this._choices = Array.isArray(choices) ? choices : []
        this._choicesOverridden = true
        return this._choices
    }

    // Reverts to the default cache-backed behavior -- the next read of
    // `choices` calls ensureChoices() again as normal.
    clearChoicesOverride() {
        this._choicesOverridden = false
    }

    get pk() {
        const value = this.value
        if (value && typeof value === 'object') {
            return value.value
        }
        return value
    }

    set pk(value) {
        this.value = value
    }

    get selectedChoice() {
        const pk = this.pk
        if (pk == null) return undefined

        const loaded = (this.choices || []).find(choice => String(choice.value) === String(pk))
        if (loaded) return loaded

        if (
            this._retainedSelectedChoice
            && String(this._retainedSelectedChoice.value) === String(pk)
        ) {
            return this._retainedSelectedChoice
        }

        // selected_choice metadata seeds the current value of a searchable
        // relation before the user has issued a query.
        if (this.selected_choice && String(this.selected_choice.value) === String(pk)) {
            return this.selected_choice
        }

        return undefined
    }

    get isSearchingChoices() {
        return Boolean(this._searchPromise)
    }

    ensureChoices() {
        const cacheKey = this._getChoicesCacheKey()
        const cache = this._getOrCreateCache(cacheKey)
        cache.fields.add(this)

        if (this._choices !== cache.choices) {
            this.choices = cache.choices
        }

        if (cache.loaded) {
            return cache.promise || Promise.resolve(this._choices || [])
        }

        if (cache.promise) {
            return cache.promise
        }

        if (typeof this.owner.foreign_key_choices !== 'function') {
            return Promise.resolve(this._choices || [])
        }

        cache.promise = this.owner.foreign_key_choices({
            field_name: this.name,
        }).then(result => {
            const {results = []} = result || {}
            this._mergeChoices(results)
            cache.loaded = true
            return this._choices || []
        }).finally(() => {
            cache.promise = null
        })

        return cache.promise
    }

    // Runs a server-side search over the fields declared by
    // Glue.choices() and takes over this field's choices via
    // overrideChoices() until clearSearch() runs.
    async searchChoices(query) {
        if (!query) {
            return this.clearSearch()
        }

        this._rememberSelectedChoice()
        this._searchGeneration = (this._searchGeneration || 0) + 1
        const searchGeneration = this._searchGeneration
        this._searchActive = true
        this._searchQuery = query

        const searchPromise = this.owner.foreign_key_choices({
            field_name: this.name,
            search: query,
        }).then(result => {
            if (
                searchGeneration !== this._searchGeneration
                || !this._searchActive
                || query !== this._searchQuery
            ) {
                return this._choices || []
            }
            const {results = []} = result || {}
            return this.overrideChoices(results)
        }).finally(() => {
            if (this._searchPromise === searchPromise) {
                this._searchPromise = null
            }
        })
        this._searchPromise = searchPromise

        return searchPromise
    }

    // Reverts to the default (cache-backed) choices list, as they stood
    // before searchChoices() took over -- e.g. when the user clears the
    // search box or closes the dropdown.
    clearSearch() {
        this._rememberSelectedChoice()
        this._searchGeneration = (this._searchGeneration || 0) + 1
        this._searchActive = false
        this._searchQuery = ''
        this._searchPromise = null
        this.clearChoicesOverride()
        return this.choices
    }

    _rememberSelectedChoice() {
        const selectedChoice = this.selectedChoice
        if (selectedChoice) {
            this._retainedSelectedChoice = selectedChoice
        }
    }

    _getChoicesCacheKey() {
        return this.choices_cache_key || [
            this.owner._policy.identity.model_class_path,
            this.owner._policy.identity.form_class_path,
            this.choice_model_path,
            this.name,
        ].filter(Boolean).join(':')
    }

    _getOrCreateCache(cacheKey) {
        let cache = RelationFieldGlue.loadingCache.get(cacheKey)
        if (!cache) {
            cache = {
                loaded: false,
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
            const existing = merged.find(item => item.value === choice.value)
            if (existing) {
                Object.assign(existing, choice)
            } else {
                merged.push(choice)
            }
        })

        cache.choices = merged

        for (const field of cache.fields) {
            if (!field._choicesOverridden) {
                field.choices = cache.choices
            }
        }
    }
}

export default RelationFieldGlue
