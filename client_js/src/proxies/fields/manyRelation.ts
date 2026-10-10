import type {GlueChoice} from "../../wire"
import RelationFieldGlue from "./relation"

class ManyRelationFieldGlue extends RelationFieldGlue {
    declare _retainedSelectedChoices: GlueChoice[] | undefined

    get selectedPks(): unknown[] {
        return ((this.value || []) as unknown[]).filter(value => value != null)
    }

    get selectedChoices(): GlueChoice[] {
        const selectedPks = new Set(this.selectedPks.map(value => String(value)))
        if (selectedPks.size === 0) return []

        // Later entries win in a Map, so order these least- to most-authoritative:
        // the server's initial seed is the fallback, a retained choice covers a
        // selection whose search has since been cleared, and the current results
        // are the freshest source for anything still on screen. Mirrors the
        // single-value `selectedChoice` getter in RelationFieldGlue.
        const candidates = [
            ...(this.selected_choices || []),
            ...(this._retainedSelectedChoices || []),
            ...(this.choices || []),
        ]
        const choicesByValue = new Map(
            candidates.map((choice): [string, GlueChoice] => [String(choice.value), choice])
        )
        return this.selectedPks
            .map(value => choicesByValue.get(String(value)))
            .filter(Boolean) as GlueChoice[]
    }

    _rememberSelectedChoice(): void {
        const retainedByValue = new Map(
            (this._retainedSelectedChoices || []).map((choice): [string, GlueChoice] => [String(choice.value), choice])
        )
        for (const choice of this.selectedChoices) {
            retainedByValue.set(String(choice.value), choice)
        }
        this._retainedSelectedChoices = Array.from(retainedByValue.values())
    }

    hasChoiceSelected(value: unknown): boolean {
        return this.selectedPks.some(item => String(item) === String(value))
    }

    addChoice(value: unknown): this {
        if (this.hasChoiceSelected(value)) {
            return this
        }
        this.value = [...((this.value || []) as unknown[]), value]
        return this
    }

    removeChoice(value: unknown): this {
        this.value = ((this.value || []) as unknown[]).filter(item => String(item) !== String(value))
        return this
    }

    toggleChoice(value: unknown): this {
        return this.hasChoiceSelected(value) ? this.removeChoice(value) : this.addChoice(value)
    }
}

export default ManyRelationFieldGlue
