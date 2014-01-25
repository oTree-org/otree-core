from ptree.db import models
import ptree.models

class LifeOrientationTest(ptree.models.AuxiliaryModel):


    LIKERT_CHOICES = ((0, '0 - Strongly disagree'),
                      (1, '1 - Disagree'),
                      (2, '2 - Neutral'),
                      (3, '3 - Agree'),
                      (4, '4 - Strongly agree'))

    q1 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="In uncertain times, I usually expect the best.")
    q2 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="It's easy for me to relax")
    q3 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="If something can go wrong for me, it will.")
    q4 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="I'm always optimistic about my future.")
    q5 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="I enjoy my friends a lot.")
    q6 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="It's important for me to keep busy.")
    q7 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="I hardly ever expect things to go my way.")
    q8 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="I don't get upset too easily.")
    q9 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="I rarely count on good things happening to me.")
    q10 = models.IntegerField(choices=LIKERT_CHOICES, null=True, verbose_name="Overall, I expect more good things to happen to me than bad.")

