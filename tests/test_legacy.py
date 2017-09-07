from .utils import TestCase


class TestLegacy(TestCase):

    def test_boto2_import(self):
        '''testing the otree-boto2-shim'''
        from boto.mturk import qualification
        quals = [
            qualification.LocaleRequirement("EqualTo", "US"),
            qualification.PercentAssignmentsApprovedRequirement(
                     "GreaterThanOrEqualTo", 50),
            qualification.NumberHitsApprovedRequirement(
                     "GreaterThanOrEqualTo", 5)
        ]

        # make sure the import is actually using the boto2 shim,
        # not the actual boto2 package that may still be lying around
        for qual in quals:
            self.assertEqual(qual, None)
