var formInputs = new Proxy(document.getElementById('form').elements, {
    set: function (obj, prop, value) {
        throw new TypeError(`To set the value of a field, you must use .value, for example, formInputs.${prop}.value = ...`);
    },
    get: function (target, prop, receiver) {
        var input = Reflect.get(...arguments);
        var proxyInput = new Proxy(input, {
            set: function (obj, prop2, value) {
                if (!(prop2 in obj) && NodeList.prototype.isPrototypeOf(obj)) {
                    throw Error(`formInputs.${prop} has no property '${prop2}'. (Note that it is a RadioNodeList, not a regular input.) `)
                }
                obj[prop2] = value;
            },
        });
        return proxyInput;
    },
});