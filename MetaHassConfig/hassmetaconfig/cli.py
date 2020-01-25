import sys
import hassmetaconfig.gen as gen
import yaml


def main(args=None):
    if args is None:
        args = sys.argv
    config = gen.MetaConfig(args[1])
    automations = gen.Automation(config).gen()
    scenes = gen.Scenes(config).gen()

    with open('automations.yml', 'w') as f:
        yaml.dump(automations, f)
    with open('scenes.yaml', 'w') as f:
        yaml.dump(scenes, f)
