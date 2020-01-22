import os
import yaml

import typing as typ


class MetaConfig:
    def __init__(self, fpath: str):
        self.fpath = fpath
        if not os.path.isfile(self.fpath):
            raise Exception(f"MetaConfig input {self.fpath} isn't a file")
        with open(fpath) as conts:
            self.data = yaml.load(conts, Loader=yaml.FullLoader)

    def dimmer_entities(self):
        return [{k: v} for (k, v) in self.data['entities'].items() if v['type'] == 'dimmer switch']


class Automation:
    def __init__(self, metaconfig: MetaConfig):
        self.metaconfig = metaconfig

    def _taps(self, dimmer: typ.Dict) -> typ.List[typ.Dict]:
        assert(len(dimmer) == 1)
        name = list(dimmer.keys())[0]  #lol
        attrs = dimmer[name]  # lol
        return [{
            'id': f"{name}_doubletap_up",
            'alias': f"{name}_doubletap_up",
            'trigger': [{
                'platform': 'event',
                'event_type': 'zwave.scene_activated',
                'event_data': {
                    'entity_id': f"zwave.{name}",
                    'scene_id': 1,  # convention that 1 is up
                }
            }],
            'condition': [],
            'action': [
                {'scene': f"scene.{attrs['on_up']['scene']}"}
            ]
        }, {
            'id': f"{name}_doubletap_down",
            'alias': f"{name}_doubletap_down",
            'trigger': [{
                'platform': 'event',
                'event_type': 'zwave.scene_activated',
                'event_data': {
                    'entity_id': f"zwave.{name}",
                    'scene_id': 2,  # convention that 1 is down
                }
            }],
            'condition': [],
            'action': [
                {'scene': f"scene.{attrs['on_down']['scene']}"}
            ]
        }]

    def _webhooks(self, dimmer: typ.Dict) -> typ.List[typ.Dict]:
        assert (len(dimmer) == 1)
        attrs = list(dimmer.values())[0]
        return [{
            'id': scene,  # TODO should this have a "hook_" prefix?
            'alias': scene,
            'description': '',
            'trigger': [{
                'platform': 'webhook',
                'webhook_id': scene,
            }],
            'condition': [],
            'action': [{
                'scene': f"scene.{scene}",
            }],
        } for scene in {attrs['on_up']['scene'], attrs['on_down']['scene']}]

    def gen(self) -> typ.List[typ.Dict]:
        # flat_list = [item for sublist in l for item in sublist]

        out = []
        for dimmer in self.metaconfig.dimmer_entities():
            out.extend(self._taps(dimmer))
        for dimmer in self.metaconfig.dimmer_entities():
            out.extend(self._webhooks(dimmer))
        out.sort(key=lambda a: a['id'])
        return out
