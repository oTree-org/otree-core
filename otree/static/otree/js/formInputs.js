var formInputs = new Proxy(document.getElementById('form').elements, {
  set: function (obj, prop, value) {
    throw new TypeError(`To set the value of a field, you must use .value, for example, formInputs.${prop}.value = ...`);
  }
});