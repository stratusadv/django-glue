import RelationFieldGlue from "./relation"

class ManyRelationFieldGlue extends RelationFieldGlue {
    get selectedPks() {
        return (this.value || []).map(choice => Number(choice?.pk ?? choice?.id ?? choice))
    }

    get selectedChoices() {
        const selectedPks = new Set(this.selectedPks)
        return (this.choices || []).filter(choice => selectedPks.has(Number(choice.pk)))
    }

    has(choiceOrPk) {
        const pk = Number(choiceOrPk?.pk ?? choiceOrPk?.id ?? choiceOrPk)
        return this.selectedPks.includes(pk)
    }

    add(choiceOrPk) {
        if (this.has(choiceOrPk)) {
            return this.value || []
        }
        this.value = [...(this.value || []), choiceOrPk]
        return this.value
    }

    remove(choiceOrPk) {
        const pk = Number(choiceOrPk?.pk ?? choiceOrPk?.id ?? choiceOrPk)
        this.value = (this.value || []).filter(choice => Number(choice?.pk ?? choice?.id ?? choice) !== pk)
        return this.value
    }

    toggle(choiceOrPk) {
        return this.has(choiceOrPk) ? this.remove(choiceOrPk) : this.add(choiceOrPk)
    }
}

export default ManyRelationFieldGlue
