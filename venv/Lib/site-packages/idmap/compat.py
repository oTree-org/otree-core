from django.db.models.query import QuerySet


try:
    # django 1.9+
    from django.db.models.query import ModelIterable, ValuesIterable, \
        ValuesListIterable, FlatValuesListIterable
    HAS_ITER_CLASSES = True

    class CompatIdMapQuerySet(QuerySet):

        def _idmap_clone(self):
            clone = super(CompatIdMapQuerySet, self)._clone()
            clone.__dict__.update({
                '_fields': None,
                '_iterable_class': ModelIterable
            })
            return clone

        def _idmap_get_instance(self, clone, *args, **kwargs):
            return super(
                CompatIdMapQuerySet,
                clone
            ).get(*args, **kwargs)

        def _idmap_get(self, instance):
            if self._iterable_class is ModelIterable:
                return instance
            elif self._iterable_class is ValuesListIterable:
                return [getattr(instance, f) for f in self._fields]
            elif self._iterable_class is FlatValuesListIterable:
                return getattr(instance, self._fields[0])
            elif self._iterable_class is ValuesIterable:
                return {f: getattr(instance, f) for f in self._fields}

except ImportError:
    # django 1.8
    from django.db.models.query import ValuesQuerySet, ValuesListQuerySet
    HAS_ITER_CLASSES = False

    class CompatIdMapQuerySet(QuerySet):

        def _idmap_clone(self):
            return super(CompatIdMapQuerySet, self)\
                ._clone(klass=QuerySet, _fields=None)

        def _idmap_get_instance(self, clone, *args, **kwargs):
            return clone.get(*args, **kwargs)

        def _idmap_get(self, instance):
            if isinstance(self, ValuesListQuerySet):
                values = [getattr(instance, f) for f in self._fields]
                if self.flat:
                    return values[0]
                else:
                    return values
            elif isinstance(self, ValuesQuerySet):
                return {f: getattr(instance, f) for f in self._fields}
            else:
                return instance
