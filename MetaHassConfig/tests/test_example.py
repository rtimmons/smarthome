import hassmetaconfig.gen as gen

import unittest
import os
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def tcase_dir(tcase):
    return os.path.join(REPO_ROOT, 'tests', 'cases', tcase)


def expected(tcase, which):
    tdir = tcase_dir(tcase)
    fpath = os.path.join(tdir, which)
    if not os.path.isfile(fpath):
        raise Exception(f"Expected fpath={fpath} doesn't exist")
    with open(fpath) as conts:
        return yaml.load(conts, Loader=yaml.FullLoader)


class TestAutomation(unittest.TestCase):
    def test_produces_one_dimmer_automation(self):
        tdir = tcase_dir('one-dimmer')
        config = gen.MetaConfig(os.path.join(tdir, 'input.yaml'))
        automations = gen.Automation(config)

        actual = automations.gen()
        exp = expected('one-dimmer', 'automations.yaml')

        msg = f"Expected:\n{yaml.dump(exp)}\n\nActual:\n{yaml.dump(actual)}\n"
        self.assertListEqual(actual, exp, msg)

