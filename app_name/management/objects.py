from fractions import Fraction as F
from donation.models import Treatment, Experiment, Player

probabilities = [F(x,3) for x in range(4)]

def create_experiment_with_treatments():

    Experiment.objects.all().delete()
    Treatment.objects.all().delete()

    experiment = Experiment(randomization_mode = Experiment.SMOOTHING, description = 'Experiment with all treatments')
    experiment.save()

    for p in probabilities:
        for fallback in [True, False]:
            if p == 1 and fallback == True:
                # fallback is irrelevant for p == 1, so we don't need double data points
                pass
            else:
                t = Treatment(experiment = experiment,
                              base_pay = 100,
                              max_offer_amount = 100,
                              probability_of_honoring_split_numerator = p.numerator,
                              probability_of_honoring_split_denominator = p.denominator,
                              increment_amount = 1,
                              player_gets_all_money_if_no_honor_split = fallback)
                t.save()

def create_players(n):
    Player.objects.all().delete()

    experiment = Experiment.objects.all()[0]

    for i in range(n):
        player = Player(experiment = experiment)
        player.save()