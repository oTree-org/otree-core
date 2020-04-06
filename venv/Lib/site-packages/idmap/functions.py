from .signals import pre_flush, post_flush


def flush(db=None):
    from .models import IdMapModel
    pre_flush.send(IdMapModel, db=db)
    for model in IdMapModel.__subclasses__():
        model.flush_instance_cache(db=db, flush_sub=True)
    post_flush.send(IdMapModel, db=db)
