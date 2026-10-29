import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio.analysis import summarize,paired,differences,plan
class AnalysisTests(unittest.TestCase):
    def test_summary(self):
        s=summarize([1,2,3,4]);self.assertEqual(s['mean'],2.5);self.assertEqual(s['q25'],1.75);self.assertLessEqual(s['mean_ci95'][0],2.5)
    def test_pair(self):
        s=paired([1,2,3],[2,3,4]);self.assertEqual(s['mean'],1);self.assertIsNone(s['paired_standardized_effect'])
    def test_invalid(self):
        for x in [[],[float('nan')],[True],['1']]:
            with self.assertRaises(ValueError):summarize(x)
        with self.assertRaises(ValueError):paired([1],[1,2])
    def test_diff(self):
        self.assertEqual(differences([{'x':1,'y':[2]},{'x':1,'y':[3]}]),[{'parameter':'y[0]','values':[2,3]}])

    def test_plan(self):
        p=plan({'stages':[{'profile':'gait','updates':100,'blocks':3}]})
        self.assertEqual(p['updates_per_sequence'],300)
        self.assertEqual(p['evaluations_per_sequence'],3)
        self.assertFalse(p['repeats_until_stopped'])
    def test_plan_validates(self):
        with self.assertRaises(ValueError):plan({'seed':-1})
