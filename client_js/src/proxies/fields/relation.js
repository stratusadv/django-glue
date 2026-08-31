import ChoiceFieldGlue from "./choice"

class RelationFieldGlue extends ChoiceFieldGlue {
    // Static cache tracks loading state only, not data
    static loadingCache = new Map()

    get choices() {
        if (this.choice_model_path && !this._choicesOverridden) {
            this.ensureChoices([])
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
        return (this.choices || []).find(choice => String(choice.value) === String(pk))
    }

    // True once the field's registered batch_size (choices_batch_size
    // metadata, see FormFieldAttribute.add_choice_metadata) caused the last
    // fetch to stop short of the full related queryset -- whether that
    // fetch came from the default cache-backed load or an active search.
    get hasMoreChoices() {
        if (this._searchActive) {
            return Boolean(this._searchHasNext)
        }
        return Boolean(this._getOrCreateCache(this._getChoicesCacheKey()).hasNext)
    }

    get isLoadingMoreChoices() {
        return Boolean(this._loadMorePromise)
    }

    get isSearchingChoices() {
        return Boolean(this._searchPromise)
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

        const requiredFields = this._choiceObjectFields(choiceFields)
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
            choice_fields: this._serverChoiceFields(missingFields),
            batch_size: this.choices_batch_size ?? null,
        }).then(result => {
            const {results = [], has_next: hasNext = false, seek_key: seekKey = null} = result || {}
            this._mergeChoices(results)
            cache.hasNext = hasNext
            cache.seekKey = seekKey
            requiredFields.forEach(f => cache.loadedFields.add(f))
            return this._choices || []
        }).finally(() => {
            cache.promise = null
        })

        return cache.promise
    }

    // Fetches the next batch after whatever was loaded last -- continuing
    // the active search if one is in progress, otherwise extending the
    // shared default-choices cache. A field with no choices_batch_size
    // metadata never has more to load (hasMoreChoices is always false), so
    // this is a no-op for every field that hasn't opted into batching.
    async loadMoreChoices(choiceFields = []) {
        if (this._loadMorePromise) {
            return this._loadMorePromise
        }

        if (this._searchActive) {
            if (!this._searchHasNext) {
                return this._choices || []
            }

            this._loadMorePromise = this.owner.foreign_key_choices({
                field_name: this.name,
                choice_fields: this._serverChoiceFields(this._choiceObjectFields(choiceFields)),
                search: this._searchQuery,
                search_field: this._searchField,
                seek_key: this._searchSeekKey,
                batch_size: this.choices_batch_size ?? null,
            }).then(result => {
                const {results = [], has_next: hasNext = false, seek_key: seekKey = null} = result || {}
                this._searchHasNext = hasNext
                this._searchSeekKey = seekKey
                return this.overrideChoices([...(this._choices || []), ...results])
            }).finally(() => {
                this._loadMorePromise = null
            })

            return this._loadMorePromise
        }

        const cacheKey = this._getChoicesCacheKey()
        const cache = this._getOrCreateCache(cacheKey)
        if (!cache.hasNext || cache.promise) {
            return this._choices || []
        }

        this._loadMorePromise = cache.promise = this.owner.foreign_key_choices({
            field_name: this.name,
            choice_fields: this._serverChoiceFields([...cache.loadedFields]),
            seek_key: cache.seekKey,
            batch_size: this.choices_batch_size ?? null,
        }).then(result => {
            const {results = [], has_next: hasNext = false, seek_key: seekKey = null} = result || {}
            cache.hasNext = hasNext
            cache.seekKey = seekKey
            this._mergeChoices(results)
            return this._choices || []
        }).finally(() => {
            cache.promise = null
            this._loadMorePromise = null
        })

        return this._loadMorePromise
    }

    // Runs a server-side search (icontains on searchField, see the
    // scroll_queryset_filter_field convention in scroll.html for the same
    // pattern applied to Glue.queryset() scroll lists) and takes over this
    // field's choices via overrideChoices() until clearSearch() runs. Only
    // meaningful for a field that opted into batching -- searchField must
    // be passed explicitly by the widget, since there's no generic way to
    // filter on a model's __str__ at the database layer.
    async searchChoices(query, searchField, choiceFields = []) {
        if (!query) {
            return this.clearSearch()
        }

        this._searchActive = true
        this._searchQuery = query
        this._searchField = searchField
        this._searchSeekKey = null

        this._searchPromise = this.owner.foreign_key_choices({
            field_name: this.name,
            choice_fields: this._serverChoiceFields(this._choiceObjectFields(choiceFields)),
            search: query,
            search_field: searchField,
            batch_size: this.choices_batch_size ?? null,
        }).then(result => {
            const {results = [], has_next: hasNext = false, seek_key: seekKey = null} = result || {}
            this._searchHasNext = hasNext
            this._searchSeekKey = seekKey
            return this.overrideChoices(results)
        }).finally(() => {
            this._searchPromise = null
        })

        return this._searchPromise
    }

    // Reverts to the default (cache-backed) choices list, as they stood
    // before searchChoices() took over -- e.g. when the user clears the
    // search box or closes the dropdown.
    clearSearch() {
        this._searchActive = false
        this._searchQuery = ''
        this._searchField = ''
        this._searchSeekKey = null
        this._searchHasNext = false
        this.clearChoicesOverride()
        return this.choices
    }

    _getChoicesCacheKey() {
        return this.choices_cache_key || [
            this.owner._policy.identity.model_class_path,
            this.owner._policy.identity.form_class_path,
            this.choice_model_path,
            this.name,
        ].filter(Boolean).join(':')
    }

    _choiceObjectFields(choiceFields = []) {
        return [...new Set(['pk', '__str__', ...choiceFields.filter(Boolean)])]
    }

    _serverChoiceFields(fields = []) {
        return fields.filter(f => !['value', 'label', 'pk', '__str__'].includes(f))
    }

    _getOrCreateCache(cacheKey) {
        let cache = RelationFieldGlue.loadingCache.get(cacheKey)
        if (!cache) {
            cache = {
                loadedFields: new Set(),
                promise: null,
                choices: [],
                fields: new Set(),
                hasNext: false,
                seekKey: null,
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
            field.choices = cache.choices
        }
    }
}

export default RelationFieldGlue
