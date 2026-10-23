import type {GlueChoice} from "../../wire"
import type {GlueFieldOwner} from "./base"
import ChoiceFieldGlue from "./choice"

// A relation's owner serves its choices through a `foreign_key_choices`
// callable, materialized on the proxy when the server declares it.
interface GlueRelationFieldOwner extends GlueFieldOwner {
    foreign_key_choices?(kwargs: {field_name: string, search?: string}): Promise<{results?: GlueChoice[]} | null | undefined>
}

// The choices every field with the same cache key shares.
interface GlueChoicesCache {
    loaded: boolean
    promise: Promise<GlueChoice[]> | null
    choices: GlueChoice[]
    fields: Set<RelationFieldGlue>
}

class RelationFieldGlue extends ChoiceFieldGlue {
    // Static cache tracks loading state only, not data
    static loadingCache = new Map<string, GlueChoicesCache>()

    declare owner: GlueRelationFieldOwner
    declare _choices: GlueChoice[] | undefined
    declare _choicesOverridden: boolean | undefined
    declare _searchQuery: string | undefined
    declare _searchChoices: GlueChoice[] | null | undefined
    declare _searchPromise: Promise<GlueChoice[]> | null | undefined
    declare _searchGeneration: number | undefined
    declare _retainedSelectedChoice: GlueChoice | undefined

    get choices(): GlueChoice[] {
        if (this._searchQuery) {
            return this._searchChoices || []
        }
        if (this.choice_model_path && !this._choicesOverridden) {
            this.ensureChoices()
        }
        return this._choices || []
    }

    set choices(value: GlueChoice[]) {
        this._choices = value
    }

    // Explicitly assigns this field's choices and keeps them from being
    // clobbered by ensureChoices() -- the choices getter otherwise
    // self-heals from a shared, cache-key-scoped cache on every read
    // (including incidental reads from template re-renders), which
    // silently overwrites anything assigned outside that cache. Use this
    // when a caller (e.g. a glue-callable-backed dependent-choices reload)
    // is the authoritative source for this field's choices right now,
    // instead of the field's own default foreign_key_choices() lookup.
    // Independent of search -- see searchChoices()/clearSearch(), which
    // hold their own results and leave this override alone.
    overrideChoices(choices: GlueChoice[]): GlueChoice[] {
        this._choices = Array.isArray(choices) ? choices : []
        this._choicesOverridden = true
        return this._choices
    }

    // Reverts to the default cache-backed behavior -- the next read of
    // `choices` calls ensureChoices() again as normal.
    clearChoicesOverride(): void {
        this._choicesOverridden = false
    }

    get pk(): unknown {
        const value = this.value
        if (value && typeof value === 'object') {
            return (value as {value?: unknown}).value
        }
        return value
    }

    set pk(value: unknown) {
        this.value = value
    }

    get selectedChoice(): GlueChoice | undefined {
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

    get isSearchingChoices(): boolean {
        return Boolean(this._searchPromise)
    }

    ensureChoices(): Promise<GlueChoice[]> {
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
            field_name: this.choice_field || this.name,
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

    // Runs a server-side search over the fields declared by Glue.choices()
    // and takes over this field's choices via a dedicated _searchChoices
    // slot (read by the choices getter above whenever _searchQuery is set)
    // until clearSearch() runs. This is deliberately independent of
    // overrideChoices()/_choicesOverridden -- those track a caller-supplied
    // choice list (e.g. a dependent-choices reload) that has nothing to do
    // with search and must survive a search starting and ending around it.
    async searchChoices(query: string): Promise<GlueChoice[]> {
        if (!query) {
            return this.clearSearch()
        }

        this._rememberSelectedChoice()
        this._searchGeneration = (this._searchGeneration || 0) + 1
        const searchGeneration = this._searchGeneration
        this._searchQuery = query

        const searchPromise = this.owner.foreign_key_choices!({
            field_name: this.choice_field || this.name,
            search: query,
        }).then(result => {
            if (
                searchGeneration !== this._searchGeneration
                || query !== this._searchQuery
            ) {
                return this._searchChoices || []
            }
            const {results = []} = result || {}
            this._searchChoices = Array.isArray(results) ? results : []
            return this._searchChoices
        }).finally(() => {
            if (this._searchPromise === searchPromise) {
                this._searchPromise = null
            }
        })
        this._searchPromise = searchPromise

        return searchPromise
    }

    // Reverts to the default (override- or cache-backed) choices list, as
    // they stood before searchChoices() took over -- e.g. when the user
    // clears the search box or closes the dropdown. Only touches search
    // state; a choice list assigned via overrideChoices() is untouched and
    // reasserts itself once _searchQuery is cleared (see the choices
    // getter).
    clearSearch(): GlueChoice[] {
        this._rememberSelectedChoice()
        this._searchGeneration = (this._searchGeneration || 0) + 1
        this._searchQuery = ''
        this._searchPromise = null
        this._searchChoices = null
        return this.choices
    }

    _rememberSelectedChoice(): void {
        const selectedChoice = this.selectedChoice
        if (selectedChoice) {
            this._retainedSelectedChoice = selectedChoice
        }
    }

    _getChoicesCacheKey(): string {
        return this.choices_cache_key || [
            this.owner._record.policy.identity.model_class_path,
            this.owner._record.policy.identity.form_class_path,
            this.choice_model_path,
            this.name,
        ].filter(Boolean).join(':')
    }

    _getOrCreateCache(cacheKey: string): GlueChoicesCache {
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

    _mergeChoices(newChoices: GlueChoice[]): void {
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

export type {GlueRelationFieldOwner}
export default RelationFieldGlue
