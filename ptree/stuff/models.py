from django.db import models

class StubModel(models.Model):
    """To be used as the model for an empty form, so that form_class can be omitted."""
    stub_field = models.BooleanField(default=True)
