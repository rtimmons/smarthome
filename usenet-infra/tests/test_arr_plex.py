import copy
import importlib.util
from pathlib import Path
import unittest
import yaml

s = importlib.util.spec_from_file_location('arr_plex', Path(__file__).parents[1]/'scripts/arr-plex.py')
p = importlib.util.module_from_spec(s); s.loader.exec_module(p)


def schema():
    return {'implementation':'PlexServer', 'supportsOnImportComplete':True,
            'supportsOnDownload':True, 'onGrab':True, 'onDownload':True,
            'onImportComplete':False, 'onRename':False, 'onMovieDelete':True,
            'fields':[{'name':k} for k in ('host','port','useSsl','urlBase','authToken',
                                          'updateLibrary','mapFrom','mapTo')]}


class PlexTests(unittest.TestCase):
    def test_mapping_requires_exact_unique_general_library(self):
        for app, (identity, kind, target) in p.TARGETS.items():
            sections = [{'id':identity,'type':kind,'locations':[target]}]
            self.assertEqual(p.verify_mapping(app,[{'path':'/library'}],sections),target)
            for roots, value in [([{'path':'/other'}],sections),
                                 ([{'path':'/library'}],[]),
                                 ([{'path':'/library'}],sections*2),
                                 ([{'path':'/library'}],[dict(sections[0],id='1')])]:
                with self.assertRaises(RuntimeError):p.verify_mapping(app,roots,value)

    def test_import_triggers_exclude_grabs_deletions_and_duplicate_notifications(self):
        for app in p.TARGETS:
            value=p.desired(schema(),app,'synthetic-credential')
            self.assertFalse(value['onGrab']);self.assertFalse(value['onMovieDelete'])
            self.assertTrue(value['onRename'])
            self.assertEqual(value['onDownload'],app=='radarr')
            self.assertEqual(value['onImportComplete'],app=='sonarr')
            self.assertEqual(p.fields(value)['mapFrom'],'/library')
            p.verify_resource(value,value)
            changed=copy.deepcopy(value);changed['fields'][-1]['value']='/wrong'
            with self.assertRaises(RuntimeError):p.verify_resource(changed,value)

    def test_schema_drift_and_duplicate_fields_fail_closed(self):
        value=schema();value['fields'].append(value['fields'][0])
        with self.assertRaises(RuntimeError):p.desired(value,'sonarr','synthetic')
        value=schema();value['supportsOnImportComplete']=False
        with self.assertRaises(RuntimeError):p.desired(value,'sonarr','synthetic')


class ProxyBoundaryTests(unittest.TestCase):
    def test_standard_proxy_is_bound_only_to_private_bridge_and_exact_plex(self):
        root=Path(__file__).parents[1]
        socket=(root/'config/usenet-arr-plex.socket.j2').read_text()
        service=(root/'config/usenet-arr-plex.service').read_text()
        self.assertIn('ListenStream={{ arr_plex_network.gateway }}:32401',socket)
        self.assertIn('BindToDevice={{ arr_plex_network.bridge }}',socket)
        self.assertIn('IPAddressDeny=any',socket)
        self.assertIn('IPAddressAllow={{ arr_plex_network.subnet }}',socket)
        self.assertIn('systemd-socket-proxyd 192.168.1.66:32400',service)
        self.assertIn('DynamicUser=true',service)

    def test_firewall_arguments_preserve_literal_on_token(self):
        play=yaml.safe_load((Path(__file__).parents[1]/'ansible/arr-plex.yml').read_text())[0]
        task=next(t for t in play['tasks'] if 'bridge clients' in t['name'])
        argv=task['ansible.builtin.command']['argv']
        self.assertTrue(all(isinstance(v,str) for v in argv))
        self.assertEqual(argv[:4],['ufw','allow','in','on'])
