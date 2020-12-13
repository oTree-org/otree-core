from contextlib import contextmanager
from collections import defaultdict

participants_by_code = {}
participants_by_id = {}
sessions_by_code = {}
sessions_by_id = {}
subsessions = defaultdict(dict)
groups = defaultdict(dict)
players_by_id = defaultdict(dict)
players_by_participant_round = defaultdict(dict)

SUPPORTED_CACHE_LOOKUP_FIELDS = dict(
    Session=set(['code']),
    Participant=set(['code']),
    Subsession=set(),
    Group=set(),
    Player=set(['round_number', 'participant']),
    # See below! we add more stuff
)

for aset in SUPPORTED_CACHE_LOOKUP_FIELDS.values():
    aset.add('id')
    aset.add('pk')


def flush():
    for cache in [
        participants_by_id,
        participants_by_code,
        sessions_by_id,
        sessions_by_code,
        subsessions,
        groups,
        players_by_id,
        players_by_participant_round,
    ]:
        cache.clear()


def get_instances():
    for cache in [
        participants_by_id,
        sessions_by_id,
    ]:
        for instance in cache.values():
            yield instance
    for cache in [
        subsessions,
        groups,
        players_by_id,
    ]:
        for app_cache in cache.values():
            for instance in app_cache.values():
                yield instance


def save():
    for inst in get_instances():
        # object may have gotten deleted after being added to cache
        if inst.id:
            inst.save()


is_active = False


def activate():
    flush()
    global is_active
    is_active = True


def deactivate():
    flush()
    global is_active
    is_active = False


@contextmanager
def use_cache():
    activate()
    try:
        yield
        save()
    finally:
        deactivate()


class ParticipantIDMapMixin:
    @classmethod
    def _get_cached_instance(cls, id=None, code=None):
        assert id or code
        if id is not None:
            return participants_by_id.get(id)
        return participants_by_code.get(code)

    @classmethod
    def cache_instance(cls, instance):
        participants_by_id[instance.id] = instance
        participants_by_code[instance.code] = instance

    @classmethod
    def flush_cached_instance(cls, instance):
        participants_by_id.pop(instance.id, None)
        participants_by_code.pop(instance.code, None)


class SessionIDMapMixin:
    @classmethod
    def _get_cached_instance(cls, id=None, code=None):
        assert id or code
        if id is not None:
            return sessions_by_id.get(id)
        return sessions_by_code.get(code)

    @classmethod
    def cache_instance(cls, instance):
        sessions_by_id[instance.id] = instance
        sessions_by_code[instance.code] = instance

    @classmethod
    def flush_cached_instance(cls, instance):
        sessions_by_id.pop(instance.id, None)
        sessions_by_code.pop(instance.code, None)


class SubsessionIDMapMixin:
    @classmethod
    def cache(cls) -> dict:
        return subsessions[cls._meta.app_label]

    @classmethod
    def _get_cached_instance(cls, id):
        return cls.cache().get(id)

    @classmethod
    def cache_instance(cls, instance):
        cls.cache()[instance.id] = instance

    @classmethod
    def flush_cached_instance(cls, instance):
        cls.cache().pop(instance.id, None)


class GroupIDMapMixin:
    @classmethod
    def cache(cls) -> dict:
        return groups[cls._meta.app_label]

    @classmethod
    def _get_cached_instance(cls, id):
        return cls.cache().get(id)

    @classmethod
    def cache_instance(cls, instance):
        cls.cache()[instance.id] = instance

    @classmethod
    def flush_cached_instance(cls, instance):
        cls.cache().pop(instance.id, None)


class PlayerIDMapMixin:
    @classmethod
    def cache(cls) -> dict:
        return players_by_id[cls._meta.app_label]

    @classmethod
    def round_cache(cls) -> dict:
        return players_by_participant_round[cls._meta.app_label]

    @classmethod
    def _get_cached_instance(cls, id=None, participant=None, round_number=None):
        assert id or (participant and round_number)
        if id is not None:
            return cls.cache().get(id)
        return cls.round_cache().get((participant.id, round_number))

    @classmethod
    def cache_instance(cls, instance):
        cls.cache()[instance.id] = instance
        cls.round_cache()[instance.participant_id, instance.round_number] = instance

    @classmethod
    def flush_cached_instance(cls, instance):
        cls.cache().pop(instance.id, None)
        cls.round_cache().pop((instance.participant_id, instance.round_number), None)
