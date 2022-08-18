var _FORM_INPUTS_NAME = 'forminputs';

window[_FORM_INPUTS_NAME] = (function () {
    function _innerGet(target, prop, receiver) {
        // https://stackoverflow.com/questions/27983023/
        // it works but i don't get why it makes a difference for getting input.value
        if (prop in target) {
            let ret = target[prop];
            if (typeof ret === 'function') {
                // DOM methods sometimes aren't instances of Function, so we can't directly use func.bind()
                ret = Function.prototype.bind.call(ret, target);
            }
            return ret;
        }
    }

    return new Proxy(document.getElementById('form').elements, {
        set: function (obj, prop, value) {
            throw new TypeError(`To set the value of a field, you must use .value, for example, formInputs.${prop}.value = ...`);
        },
        get: function (target, prop, receiver) {
            var input = Reflect.get(...arguments);
            if (input == null) {
                throw `Field "${prop}" does not exist.`
            }
            var proxyInput = new Proxy(input, {
                set: function (obj, prop2, value) {
                    if (!(prop2 in obj) && NodeList.prototype.isPrototypeOf(obj)) {
                        throw Error(`${_FORM_INPUTS_NAME}.${prop} has no property '${prop2}'. (Note that it is a RadioNodeList, not a regular input.) `)
                    }
                    obj[prop2] = value;
                },
                get: _innerGet
            });
            return proxyInput;
        },
    });
})();
