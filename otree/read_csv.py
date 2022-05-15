from otree.database import st, CurrencyType, Currency


def read_csv_bool(val):
    if val == '':
        return None
    return val in ['TRUE', '1', 'True', 'true', 1]


def read_csv_int(val):
    if val == '':
        return None
    return int(val)


def read_csv_float(val):
    if val == '':
        return None
    return float(val)


def read_csv_currency(val):
    if val == '':
        return None
    return Currency(val)


def read_csv_str(val):
    # should '' be interpreted as empty string or None?
    # i think empty string is better.
    # (1) the principle that you should not have 2 values for None,
    # (2) because this avoids null reference errors. you can use all string operations on an empty string.
    # it's true that oTree models use None as the default value for a StringField,
    # but that seems a bit different to me.
    return str(val)


def map_types(d, mapping: dict):
    ret = {}
    for k, v in d.items():
        type_conversion_function = mapping[k]
        try:
            ret[k] = type_conversion_function(v)
        except Exception:
            msg = f"CSV file contains an incompatible value in column '{k}': {repr(v)}"
            raise Exception(msg) from None
    return ret


class MissingFieldError(Exception):
    pass


def read_csv(path: str, type_model):
    import csv

    CONVERSION_FUNCTIONS = {
        st.Boolean: read_csv_bool,
        CurrencyType: read_csv_currency,
        st.Float: read_csv_float,
        st.Integer: read_csv_int,
        st.String: read_csv_str,
        st.Text: read_csv_str,
    }

    # even if it's not going into an ExtraModel, you can still make a model just for the purpose of CSV loading.
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        mapping = {}
        for fieldname in reader.fieldnames:
            try:
                _coltype = type(type_model.__table__.columns[fieldname].type)
            except KeyError as exc:
                # it's good to be strict and require all columns. This will prevent issues like
                # typos and users simply not understanding how the feature works.
                model_name = type_model.__name__
                msg = f"CSV file contains column '{exc.args[0]}', which is not found in model {model_name}."
                raise MissingFieldError(msg) from None
            mapping[fieldname] = CONVERSION_FUNCTIONS[_coltype]

        return [map_types(row, mapping) for row in reader]
