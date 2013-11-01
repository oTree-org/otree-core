from django.db import models
import ptree.models

class NewGeneralSelfEfficacyScale(ptree.models.AuxiliaryModel):


    ANSWER_CHOICES = ((1, '1 - Not at all true'),
                      (2, '2 - Hardly true'),
                      (3, '3 - Moderately true'),
                      (4, '4 - Exactly true'))

    q1 = models.IntegerField(choices=ANSWER_CHOICES,
                             null=True,
                             verbose_name="In uncertain times, I usually expect the best.")
    q2 = models.IntegerField(choices=ANSWER_CHOICES,
                             null=True,
                             verbose_name="It's easy for me to relax")
    q3 = models.IntegerField(choices=ANSWER_CHOICES,
                             null=True,
                             verbose_name="If something can go wrong for me, it will.")
    q4 = models.IntegerField(choices=ANSWER_CHOICES,
                             null=True,
                             verbose_name="I'm always optimistic about my future.")
    q5 = models.IntegerField(choices=ANSWER_CHOICES,
                             null=True,
                             verbose_name="I enjoy my friends a lot.")
    q6 = models.IntegerField(choices=ANSWER_CHOICES,
                             null=True,
                             verbose_name="It's important for me to keep busy.")
    q7 = models.IntegerField(choices=ANSWER_CHOICES,
                             null=True,
                             verbose_name="I hardly ever expect things to go my way.")
    q8 = models.IntegerField(choices=ANSWER_CHOICES,
                             null=True,
                             verbose_name="I don't get upset too easily.")

