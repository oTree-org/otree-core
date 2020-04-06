from django.utils import six

from .compat import CompatIdMapQuerySet


class IdMapQuerySet(CompatIdMapQuerySet):

    def get(self, *args, **kwargs):
        instance = None
        pk_attr = self.model._meta.pk.attname
        db = self._db or self.db

        pk_interceptions = (
            'pk',
            'pk__exact',
            pk_attr,
            '%s__exact' % pk_attr
        )

        # This is an exact lookup for the pk only -> kwargs.values()[0]
        # is the pk
        try:
            if len(args) == 1:
                q = args[0]
                if q.connector == 'AND' and not q.negated and \
                len(q.children) == 1:
                    c = q.children[0]
                    if c[0] in pk_interceptions:
                        args = []
                        for k in pk_interceptions:
                            kwargs.pop(k, None)
                        kwargs[pk_attr] = c[1]
        except (AttributeError, IndexError):
            pass

        if len(kwargs) == 1 and next(six.iterkeys(kwargs)) in pk_interceptions:
            instance = self.model.get_cached_instance(
                next(six.itervalues(kwargs)), db)

        where_children = self.query.where.children

        if len(where_children) == 1:
            where_child = where_children[0]
            col = where_child.lhs.target.column
            lookup_type = where_child.lookup_name
            param = where_child.rhs

            if col in ('pk', pk_attr) and lookup_type == 'exact':
                instance = self.model.get_cached_instance(param, db)

        # The cache missed or was not applicable, hit the database!
        if instance is None:

            clone = self._idmap_clone()

            clone.query.clear_select_fields()
            clone.query.default_cols = True

            instance = self._idmap_get_instance(clone, *args, **kwargs)

            # gets the pk of the retrieved object, and if it exists in the
            # cache, returns the cached instance
            # This enables object retrieved from 2 different ways (e.g directly
            # and through a relation) to share the same instance in memory.
            cached_instance = self.model.get_cached_instance(instance.pk, db)
            if cached_instance is not None:
                instance = cached_instance

        return self._idmap_get(instance)
