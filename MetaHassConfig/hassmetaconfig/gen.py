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
        ents = [e for e in self.entities if e['name'] == name]
        if len(ents) != 1:
            raise Exception(f"Unknown entity {name}")
        return ents[0]

    @property
    def dimmer_entities(self) -> typ.List[typ.Dict]:
        # TODO: just look for on_* entries don't rely on gross substring logic.
        return [e for e in self.entities if e['type'].startswith('dimmer switch')]

    @property
    def scenes(self) -> typ.List[typ.Dict]:
        return self.data['scenes']

    @property
    def state_templates(self) -> typ.Dict:
        return self.data['state_templates']

    @property
    def event_names(self) -> typ.Dict:
        return self.data['event_names']

    @property
    def additional_automations(self) -> typ.Dict:
        return self.data.get("additional_automations", {})

    @property
    def additional_scenes(self) -> typ.Dict:
        return self.data.get("additional_scenes", {})


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
                elif entity['type'].startswith('dimmer switch'):
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
        out.extend(self.metaconfig.additional_scenes)
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

        if dimmer['type'] not in self.metaconfig.event_names:
            event_names = {}
        else:
            event_names = self.metaconfig.event_names[dimmer['type']]

        taps = {k: {'parts': split(k), 'v': v} for (k, v) in dimmer.items() if k.startswith('on_')}
        # taps = {'on_down_double':
        #             {'parts': ['double', 'down'],
        #              'v': 'scene_bedroom_off'},
        #         'on_up_double':
        #             {'parts': ['double', 'up'],
        #              'v': 'scene_bedroom_high'}}

        out = []
        for (tap_name, tap) in taps.items():
            # print(f"Writing automation for {dimmer['name']} {tap_name}")
            event_data = {
                'node_id': dimmer['node_id'],
            }
            # for part in ["double", "up"]
            for part in tap['parts']:
                if part not in event_names:
                    raise Exception(f"Don't know how to do {part} for {dimmer['type']}. Update event_names.")
                event_data.update(event_names[part])
            item = {
                'id': f"{dimmer['name']}_{tap_name}",
                'alias': f"{dimmer['name']}_{tap_name}",
                'triggers': [{
                    'trigger': 'event',
                    'event_type': 'zwave_js_value_notification',
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
        out.extend(self.metaconfig.additional_automations)
        out.sort(key=lambda a: a['id'])
        return out
