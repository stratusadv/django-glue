import {sendActionRequest} from "./http-client";
import {ModelGlue} from "./config";

class DjangoGlue {
    initialized = false
    targetConstructors = {}

    async init() {
        this.registerTargetConstructor('Model', ModelGlue)
        this.initialized = true
    }

    registerTargetConstructor(targetClassName, targetConstructor) {
        if (this.initialized) {
            throw Error('Custom target class handler registration is not allowed after initialization.')
        }

        this.targetConstructors[targetClassName] = targetConstructor
    }
}

const Glue = new Proxy(new DjangoGlue(), {
    get(target, name) {
        if (name in glueServerData.session) {
            const glue = glueServerData.session[name]
            console.log(target.targetConstructors[glue.target_class])
            return new target.targetConstructors[glue.target_class](glue.unique_name)
        }
        else {
            return Reflect.get(target, name)
        }
    }
})

export default Glue