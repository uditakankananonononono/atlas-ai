"""Two humidity bookkeeping repairs and current refusal-shape pins."""
import copy
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / 'backend/app/modules/m20_general_cognitive_worker/humidity_exposure1549.py'
spec=importlib.util.spec_from_file_location('humidity_repair',PATH)
h=importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def base():
    return {'rh_limit':50,'observations':[{'time':'2026-01-01T00:00:00+00:00','rh':40},
                                        {'time':'2026-01-01T00:00:01+00:00','rh':60}]}


class CoreRepairs(unittest.TestCase):
    def test_zero_duration_final_point_not_excursion(self):
        output=h.evaluate(base())
        self.assertEqual(output['time_above_limit_seconds'],0)
        self.assertEqual(output['excursion_count'],0)
        self.assertEqual(output['max_continuous_excursion_seconds'],0)
        self.assertEqual(output['intervals'][-1]['duration_seconds'],0)
        self.assertEqual(output['intervals'][-1]['state'],'above')

    def test_positive_duration_final_point_is_excursion(self):
        profile=base();profile['horizon']='2026-01-01T00:00:02+00:00'
        output=h.evaluate(profile)
        self.assertEqual(output['time_above_limit_seconds'],1)
        self.assertEqual(output['excursion_count'],1)
        self.assertEqual(output['max_continuous_excursion_seconds'],1)

    def test_ordinary_huge_integers_refuse_cleanly_four_paths(self):
        for field in ['rh_limit','rh','max_gap_seconds','measured']:
            profile=base()
            if field=='rh':profile['observations'][0]['rh']=10**400
            elif field=='measured':profile['measured']={'time_above_limit':10**400}
            else:profile[field]=10**400
            with self.subTest(field=field),self.assertRaises(ValueError):h.evaluate(profile)


class RefusalPins(unittest.TestCase):
    def test_finite_nan_and_infinite_gap_measured(self):
        for number in [float('nan'),float('inf'),float('-inf')]:
            for field in ['max_gap_seconds','measured']:
                profile=base()
                if field=='measured':profile[field]={'time_above_limit':number}
                else:profile[field]=number
                name='measured.time_above_limit' if field=='measured' else field
                with self.subTest(field=field,number=number),self.assertRaisesRegex(ValueError,'^'+name.replace('.','\\.')+' must be finite$'):h.evaluate(profile)

    def test_timestamp_wrong_type_valueerror(self):
        for value in [None,123,[],{},True]:
            profile=base();profile['observations'][0]['time']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'^observation time must be an ISO-8601 timestamp string with explicit offset$'):h.evaluate(profile)

    def test_input_object_shape(self):
        for value in [None,[],(),23,'profile']:
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'^input must be an object$'):h.evaluate(value)

    def test_protocol_optional_string(self):
        for value in [1,True,[],{}]:
            profile=base();profile['protocol']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'^protocol must be a string when declared$'):h.evaluate(profile)
        for value in [None,'','declared']:
            profile=base();profile['protocol']=value
            self.assertEqual(h.evaluate(profile)['protocol'],value)

    def test_unknown_gap_policy(self):
        for value in ['unknown','',None,1,[],{}]:
            profile=base();profile['gap_policy']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,"^gap_policy must be 'report' or 'refuse'$"):h.evaluate(profile)

    def test_max_gap_zero_negative(self):
        for value in [0,-1,-0.0]:
            profile=base();profile['max_gap_seconds']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'^max_gap_seconds must be > 0$'):h.evaluate(profile)
        profile=base();profile['max_gap_seconds']=1
        self.assertEqual(h.evaluate(profile)['coverage']['gaps'],[])

    def test_observation_object_shape(self):
        for value in [None,[],(),123,'observation']:
            profile=base();profile['observations'][0]=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'^each observation must be an object$'):h.evaluate(profile)

    def test_measured_object_shape(self):
        for value in [None,[],(),123,'measured']:
            profile=base();profile['measured']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'^measured must be an object of supplied outcome values$'):h.evaluate(profile)
        profile=base();profile['measured']={}
        self.assertEqual(h.evaluate(profile)['measured_comparison'],{})

    def test_source_id_optional_string(self):
        for field in ['source','id']:
            for value in [123,False,[],{}]:
                profile=base();profile['observations'][0][field]=value
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'^observation '+field+' must be a string when supplied$'):h.evaluate(profile)
            for value in [None,'','declared']:
                profile=base();profile['observations'][0][field]=value
                self.assertEqual(h.evaluate(profile)['intervals'][0][field],value)


if __name__=='__main__':unittest.main(verbosity=2)
