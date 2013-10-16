__doc__ = """Code for processing Mechanical Turk payments. This needs to be called from the Python prompt; there is no web interface for it."""

from boto.mturk.connection import MTurkConnection
from boto.mturk.price import Price

config = boto.config
config.add_section('boto')
config.set('boto','https_validate_certificates', 'False')
config.add_section('aws info')
config.set('aws info','aws_validate_certs','False')

def cents_to_dollars(num_cents):
    return round(num_cents/100.0,2)

def bonus_amount(redemption_code):
    """We need to know what game type it is so that we can look up the right game"""
    try:
        Profile.objects.get(redemption_code = redemption_code).participant_bonus()
    except Exception, e:
        print 'The following error occurred for HIT with redemption code', redemption_code, ':'
        print [e]
        return 0

pa

def pay_bonuses(experiment):


# FIXME: isn't this a batch_id, not a hit_id?
def pay_hit_bonuses(hit_id):
    """Finds all the assignments for the given HIT and pays the workers accordingly."""
    conn = MTurkConnection(is_secure = True)
    i = 1
    while True:
        assignments = conn.get_assignments(hit_id, page_size = 100, page_number = i)
        if len(assignments) == 0:
            break
        else:
            for assignment in assignments:
                #Note: the following line assumes that there's only one free-text user input for the HIT.
                redemption_code = assignment.answers[0][0].FreeText
                bonus = bonus_amount(redemption_code)
                print redemption_code + ': ' + str(bonus)
                if bonus > 1:
                    bonus_price = Price(cents_to_dollars(bonus))
                    print bonus_price
                    if bonus_price.amount > 10:
                        raise Error, "Bonus price is too high."
                    conn.grant_bonus(worker_id = assignment.WorkerId, assignment_id = assignment.AssignmentId, bonus_price = bonus_price, reason = "Thanks!")
        i += 1

