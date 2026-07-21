import RelationFieldGlue from "./relation"

class ManyRelationFieldGlue extends RelationFieldGlue {
    _extractPk(choiceOrPk) {
        if (choiceOrPk == null) return null
        const pk = choiceOrPk?.pk ?? choiceOrPk?.id ?? choiceOrPk
        return pk == null ? null : Number(pk)
    }

    get selectedPks() {
        return (this.value || [])
            .map(choice => this._extractPk(choice))
            .filter(pk => pk != null)
    }

    get selectedChoices() {
        const selectedPks = new Set(this.selectedPks)
        return (this.choices || []).filter(choice => selectedPks.has(Number(choice.pk)))
    }

    has(choiceOrPk) {
        const pk = this._extractPk(choiceOrPk)
        if (pk == null) return false
        const selectedPks = new Set(this.selectedPks)
        return selectedPks.has(pk)
    }

    add(choiceOrPk) {
        if (this.has(choiceOrPk)) {
            return this
        }
        this.value = [...(this.value || []), choiceOrPk]
        return this
    }

    remove(choiceOrPk) {
        const pk = this._extractPk(choiceOrPk)
        if (pk == null) return this
        this.value = (this.value || []).filter(choice => this._extractPk(choice) !== pk)
        return this
    }

    toggle(choiceOrPk) {
        return this.has(choiceOrPk) ? this.remove(choiceOrPk) : this.add(choiceOrPk)
    }
}

export default ManyRelationFieldGlue
