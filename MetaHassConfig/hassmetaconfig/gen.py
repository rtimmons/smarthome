import os
import yaml
import copy

import typing as typ


class MetaConfig:
    def __init__(self, fpath: str):
        self.fpath = fpath
        if not os.path.isfile(self.fpath):
            raise Exception(f"MetaConfig input {self.fpath} isn't a file")
        with open(fpath) as conts:
            self.data = yaml.load(conts, Loader=yaml.FullLoader)

    @property
    def entities(self) -> typ.List[typ.Dict]:
        return self.data['entities']

    def entity(self, name):
        return [e for e in self.entities if e['name'] == name][0]

    @property
    def dimmer_entities(self) -> typ.List[typ.Dict]:
        return [e for e in self.entities if e['type'] == 'dimmer switch']

    @property
    def scenes(self) -> typ.List[typ.Dict]:
        return self.data['scenes']

    @property
    def state_templates(self) -> typ.Dict:
        return self.data['state_templates']

    @property
    def event_names(self) -> typ.Dict:
        return self.data['event_names']


class Scenes:
    def __init__(self, metaconfig: MetaConfig):
        self.metaconfig = metaconfig

    def gen(self) -> typ.List[typ.Dict]:
        out = []
        for scene in self.metaconfig.scenes:
            entities = {}
            for (ent_name, state) in scene['entities'].items():
                template = copy.deepcopy(self.metaconfig.state_templates[state])

                entity = self.metaconfig.entity(ent_name)
                full_name = ent_name

                if entity['type'] == 'hue light color' or entity['type'] == 'hue light':
                    full_name = f"light.{ent_name}"
                elif entity['type'] == 'dimmer switch':
                    full_name = f"light.{ent_name}"
                    template['node_id'] = entity['node_id']
                elif entity['type'] == 'outlet':
                    full_name = f"switch.{ent_name}"
                    template['node_id'] = entity['node_id']

                template['friendly_name'] = ent_name

                entities[full_name] = template

            out.append({
                'id': scene['name'],
                'name': scene['name'],
                'entities': entities,
            })
        out.sort(key=lambda s: s['id'])
        return out


class Automation:
    def __init__(self, metaconfig: MetaConfig):
        self.metaconfig = metaconfig

    def _taps(self, dimmer: typ.Dict) -> typ.List[typ.Dict]:
        def split(k):
            out = k.split('_')[1:]
            out.sort()
            return out

        event_names = self.metaconfig.event_names
        taps = {k: {'parts': split(k), 'v': v} for (k, v) in dimmer.items() if k.startswith('on_')}

        out = []
        for (tap_name, tap) in taps.items():
            event_data = {
                'entity_id': f"zwave.{dimmer['name']}",
            }
            for part in tap['parts']:
                event_data.update(event_names[part])
            item = {
                'id': f"{dimmer['name']}_{tap_name}",
                'alias': f"{dimmer['name']}_{tap_name}",
                'trigger': [{
                    'platform': 'event',
                    'event_type': 'zwave.scene_activated',
                    'event_data': event_data,
                }],
                'condition': [],
                'action': [
                    {'scene': f"scene.{tap['v']}"}
                ]
            }
            out.append(item)
        return out

    def _scene_webhooks(self, scenes: typ.List[typ.Dict]) -> typ.List[typ.Dict]:
        return [{
            'id': scene['name'],  # TODO should this have a "hook_" prefix?
            'alias': scene['name'],
            'description': '',
            'trigger': [{
                'platform': 'webhook',
                'webhook_id': scene['name'],
            }],
            'condition': [],
            'action': [{
                'scene': f"scene.{scene['name']}",
            }],
        } for scene in scenes]

    def gen(self) -> typ.List[typ.Dict]:
        # flat_list = [item for sublist in l for item in sublist]

        out = []
        for dimmer in self.metaconfig.dimmer_entities:
            out.extend(self._taps(dimmer))
        out.extend(self._scene_webhooks(self.metaconfig.scenes))
        out.sort(key=lambda a: a['id'])
        return out
