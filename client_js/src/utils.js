// TODO: pass type config as parameter
export function getClassByName(name){
    if (name.match(/^[a-zA-Z0-9_]+$/) && Object.values(adapterTypeConfig).includes(name)) {
      // proceed only if the name is a single word string and is in adapterTypeConfig
        return eval?.(`"use strict";(${name})`)
    } else {
      // arbitrary code is detected
      throw new Error(`ALERT: DANGEROUS STRING PASSED INTO 'getClassByName': '${name}'`);
    }
}