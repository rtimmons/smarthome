from __future__ import annotations

import importlib.util
import ipaddress
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest import mock

ROLE = Path(__file__).parents[1] / "ansible/roles/cloud_vpn"
SPEC = importlib.util.spec_from_file_location("vpn_network", ROLE / "files/vpn-network.py")
vpn = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vpn)
LOAD_SPEC = importlib.util.spec_from_file_location("vpn_loader", ROLE / "files/load-vpn.py")
loader = importlib.util.module_from_spec(LOAD_SPEC)
LOAD_SPEC.loader.exec_module(loader)
CONFIG = dict(service_ip="10.77.0.1", service_cidr="10.77.0.0/30", lan_cidr="192.168.1.0/24",
              peer_ip="100.1.188.109", local_ip="89.167.18.138")
BEFORE = """# Existing administrator configuration
*nat
:POSTROUTING ACCEPT [0:0]
-A POSTROUTING -s 172.18.0.0/16 -j MASQUERADE
COMMIT
*filter
:ufw-before-input - [0:0]
:ufw-before-output - [0:0]
:ufw-before-forward - [0:0]
-A ufw-before-input -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A ufw-before-output -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A ufw-before-input -p tcp --dport 22 -j ACCEPT
COMMIT
"""


def decision(chain, packet):
    """Evaluate the emitted rule predicates against synthetic packet metadata."""
    for row in vpn.policy_rules(CONFIG):
        args = shlex.split(row)
        if args[1] != chain:
            continue
        match = True
        # --strict is standalone, so look up flags without pair alignment.
        flags = {flag: args[index + 1] for index, flag in enumerate(args[:-1]) if flag.startswith("-") and flag != "--strict"}
        for flag, field in (("-s", "src"), ("-d", "dst")):
            if flag in flags and ipaddress.ip_address(packet[field]) not in ipaddress.ip_network(flags[flag]):
                match = False
        for flag, field in (("-i", "interface"), ("-o", "interface"), ("-p", "protocol")):
            if flag in flags and packet.get(field) != flags[flag]:
                match = False
        for flag, field in (("--sports", "sport"), ("--dports", "dport"), ("--ctstate", "state")):
            if flag in flags and str(packet.get(field)) not in flags[flag].split(","):
                match = False
        if "--pol" in flags:
            policy = packet.get("policy") or {}
            for flag, field in (("--pol", "kind"), ("--dir", "direction"), ("--proto", "protocol"),
                                ("--mode", "mode"), ("--tunnel-src", "src"), ("--tunnel-dst", "dst")):
                if policy.get(field) != flags[flag]:
                    match = False
            if policy.get("count") != 1:
                match = False
        if match:
            return flags["-j"]
    return "RETURN"


def incoming(**changes):
    result = dict(src="192.168.1.20", dst="10.77.0.1", interface="eth0", protocol="tcp", sport=40200,
                  dport=18080, state="NEW", policy=dict(kind="ipsec", direction="in", protocol="esp",
                  mode="tunnel", src=CONFIG["peer_ip"] + "/32", dst=CONFIG["local_ip"] + "/32", count=1))
    result.update(changes)
    return result


class CloudVpnTests(unittest.TestCase):
    def test_config_rejects_overlap_and_untrusted_address_syntax(self):
        changes = [("service_ip", "10.77.0.1;echo invalid"), ("service_cidr", "0.0.0.0/0"),
                   ("service_ip", "10.78.0.1"), ("service_cidr", "10.77.0.1/30"),
                   ("lan_cidr", "10.77.0.0/24"), ("lan_cidr", "192.168.1.1/24"),
                   ("peer_ip", "127.0.0.1"), ("peer_ip", "100.64.1.1"), ("local_ip", CONFIG["peer_ip"]),
                   ("local_ip", "::1")]
        for key, value in changes:
            with self.subTest(key=key, value=value), self.assertRaises(vpn.PolicyError):
                vpn.validate_config({**CONFIG, key: value})
        self.assertEqual(vpn.validate_config(CONFIG), CONFIG)

    def test_config_rejects_unexpected_fields(self):
        with self.assertRaises(vpn.PolicyError):
            vpn.validate_config({**CONFIG, "secret": "opaque"})

    def test_only_reviewed_ipsec_ui_requests_are_allowed(self):
        for port in (18080, 19696):
            for state in ("NEW", "ESTABLISHED"):
                self.assertEqual(decision(vpn.CHAINS[0], incoming(dport=port, state=state)), "ACCEPT")
        for update in (dict(policy=None), dict(src="192.168.6.20"), dict(dst="10.77.0.2"),
                       dict(dport=8080), dict(dport=22), dict(protocol="udp"), dict(state="INVALID")):
            self.assertEqual(decision(vpn.CHAINS[0], incoming(**update)), "DROP")

    def test_wrong_peer_policy_and_transport_mode_cannot_bypass(self):
        for key, value in (("src", "8.8.8.8/32"), ("dst", "1.1.1.1/32"), ("mode", "transport"),
                           ("protocol", "ah"), ("direction", "out"), ("count", 2)):
            packet = incoming()
            packet["policy"][key] = value
            self.assertEqual(decision(vpn.CHAINS[0], packet), "DROP")

    def test_return_traffic_requires_existing_connection_and_outbound_ipsec(self):
        packet = incoming(src="10.77.0.1", dst="192.168.1.20", sport=18080, dport=40200, state="ESTABLISHED")
        packet["policy"].update(direction="out", src=CONFIG["local_ip"] + "/32", dst=CONFIG["peer_ip"] + "/32")
        self.assertEqual(decision(vpn.CHAINS[1], packet), "ACCEPT")
        for update in (dict(policy=None), dict(state="NEW"), dict(dst="192.168.6.20"), dict(src="10.77.0.2"),
                       dict(dst="8.8.8.8"), dict(sport=22)):
            self.assertEqual(decision(vpn.CHAINS[1], {**packet, **update}), "DROP")

    def test_host_health_exception_requires_same_address_and_loopback(self):
        packet = incoming(src="10.77.0.1", dst="10.77.0.1", interface="lo", policy=None)
        for chain in vpn.CHAINS[:2]:
            self.assertEqual(decision(chain, packet), "ACCEPT")
            self.assertEqual(decision(chain, {**packet, "sport": 18080, "dport": 40200, "state": "ESTABLISHED"}), "ACCEPT")
            for update in (dict(interface="eth0"), dict(src="192.168.1.20"), dict(dport=8080)):
                expected = "RETURN" if chain == vpn.CHAINS[1] and "src" in update else "DROP"
                self.assertEqual(decision(chain, {**packet, **update}), expected)

    def test_unused_selector_addresses_cannot_be_forwarded(self):
        for address in ("10.77.0.0", "10.77.0.1", "10.77.0.2", "10.77.0.3"):
            self.assertEqual(decision(vpn.CHAINS[2], incoming(dst=address)), "DROP")
            self.assertEqual(decision(vpn.CHAINS[2], incoming(src=address, dst="192.168.1.20")), "DROP")

    def test_unrelated_ssh_and_docker_traffic_is_untouched(self):
        for chain in vpn.CHAINS:
            self.assertEqual(decision(chain, incoming(src="8.8.8.8", dst=CONFIG["local_ip"], dport=22)), "RETURN")
            self.assertEqual(decision(chain, incoming(src="172.18.0.2", dst="8.8.8.8", dport=443)), "RETURN")

    def test_ufw_fragment_is_idempotent_and_preserves_prior_rules(self):
        rendered = vpn.render_ufw(BEFORE, CONFIG)
        self.assertEqual(vpn.render_ufw(rendered, CONFIG), rendered)
        cleaned = rendered[:rendered.index(vpn.BEGIN)] + rendered[rendered.index(vpn.END) + len(vpn.END) + 1:]
        self.assertEqual(cleaned, BEFORE)
        self.assertLess(rendered.index("-A ufw-before-input -j USENET"), rendered.index("--ctstate RELATED,ESTABLISHED"))

    def test_ufw_fragment_rejects_foreign_or_corrupt_chain_ownership(self):
        for existing in (BEFORE + vpn.BEGIN, BEFORE + "\n:USENET_VPN_IN - [0:0]\n",
                         BEFORE.replace(":ufw-before-input - [0:0]\n", ""), BEFORE + "\n*filter\n"):
            with self.assertRaises(vpn.PolicyError):
                vpn.render_ufw(existing, CONFIG)

    def test_atomic_script_only_flushes_owned_chains_and_does_not_duplicate_hooks(self):
        new = vpn.restore_script(CONFIG, set())
        existing = vpn.restore_script(CONFIG, {"INPUT", "OUTPUT", "FORWARD"})
        self.assertEqual(new.count("COMMIT"), 1)
        self.assertEqual(new.count("-I "), 3)
        self.assertNotIn("-I ", existing)
        flushes = [line for line in existing.splitlines() if line.startswith("-F")]
        self.assertEqual(flushes, ["-F " + chain for chain in vpn.CHAINS])
        self.assertNotIn("*nat", new)

    def test_firewall_validation_failure_preserves_disk_and_never_applies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "before.rules"
            path.write_text(BEFORE)
            calls = []
            def fake(argv, **kwargs):
                calls.append((argv, kwargs))
                if "--test" in argv:
                    raise vpn.PolicyError("synthetic parser rejection")
                return subprocess.CompletedProcess(argv, 0, "", "")
            with mock.patch.object(vpn, "check_interface", return_value=False), mock.patch.object(vpn, "run", side_effect=fake):
                with self.assertRaises(vpn.PolicyError):
                    vpn.install_firewall(CONFIG, path)
            self.assertEqual(path.read_text(), BEFORE)
            self.assertFalse(any(argv[0].endswith("iptables-restore") and "--test" not in argv for argv, _ in calls))

    def test_first_install_never_probes_a_nonexistent_jump_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "before.rules"
            path.write_text(BEFORE)
            calls = []
            def fake(argv, **kwargs):
                calls.append(argv)
                if "-C" in argv:
                    self.fail("iptables-nft target parsing can fail before checking absent rules")
                return subprocess.CompletedProcess(argv, 0, "-P INPUT ACCEPT\n", "")
            with mock.patch.object(vpn, "check_interface", return_value=False), mock.patch.object(vpn, "run", side_effect=fake), \
                 mock.patch.object(vpn, "write_atomic") as publish:
                vpn.install_firewall(CONFIG, path)
            publish.assert_called_once()
            self.assertEqual(sum(argv[0].endswith("iptables-restore") and "--test" not in argv for argv in calls), 1)

    def test_existing_non_dummy_or_foreign_address_is_refused(self):
        for kind, addresses in (("bridge", []), ("dummy", [{"addr_info": [{"local": "10.99.0.1", "prefixlen": 32}]}])):
            results = [subprocess.CompletedProcess([], 0, json.dumps([{"linkinfo": {"info_kind": kind}}]), ""),
                       subprocess.CompletedProcess([], 0, json.dumps(addresses), "")]
            with mock.patch.object(vpn, "run", side_effect=results), self.assertRaises(vpn.PolicyError):
                vpn.check_interface(CONFIG)

    def test_failed_subprocess_never_discloses_diagnostics(self):
        completed = subprocess.CompletedProcess([], 1, "PRIVATE MATERIAL", "PRIVATE MATERIAL")
        with mock.patch.object(vpn.subprocess, "run", return_value=completed):
            with self.assertRaises(vpn.PolicyError) as error:
                vpn.run(["/usr/sbin/iptables"])
        self.assertNotIn("PRIVATE", str(error.exception))


class CloudVpnLoaderTests(unittest.TestCase):
    loaded = "loaded ike secret 'ike-usenet-ui'\nloaded connection 'usenet-ui'\n"
    listed = "usenet-ui: IKEv2, no reauthentication\n  usenet-ui: TUNNEL, rekeying every 3000s\n"

    def test_success_requires_fresh_connection_credential_and_daemon_child(self):
        with mock.patch.object(loader, "run", side_effect=[self.loaded, self.listed]) as run:
            loader.load()
        self.assertEqual(run.call_args_list, [
            mock.call(["--load-all", "--noprompt", "--file", loader.CONFIG]),
            mock.call(["--list-conns"]),
        ])

    def test_zero_exit_empty_load_is_failure_even_if_daemon_previously_had_connection(self):
        for output in ("no connections found, 0 unloaded\n", "no connections found, 1 unloaded\n", ""):
            with self.subTest(output=output), \
                 mock.patch.object(loader, "run", side_effect=[output, self.listed]) as run, \
                 self.assertRaises(loader.LoadError):
                loader.load()
            self.assertEqual(run.call_count, 1)

    def test_load_rejects_missing_or_different_credential(self):
        for output in ("loaded connection 'usenet-ui'\n",
                       "loaded ike secret 'another-vpn'\nloaded connection 'usenet-ui'\n"):
            with mock.patch.object(loader, "run", return_value=output), self.assertRaises(loader.LoadError):
                loader.load()

    def test_check_rejects_empty_wrong_name_wrong_ike_and_missing_child(self):
        for output in ("", self.listed.replace("usenet-ui", "other-vpn"),
                       self.listed.replace("IKEv2", "IKEv1"), self.listed.splitlines()[0]):
            with mock.patch.object(loader, "run", return_value=output), self.assertRaises(loader.LoadError):
                loader.check()

    def test_child_from_another_connection_cannot_pass_check(self):
        output = "usenet-ui: IKEv2, no reauthentication\n  wrong-child: TUNNEL\n" + \
                 "unrelated: IKEv2, no reauthentication\n  usenet-ui: TUNNEL\n"
        with mock.patch.object(loader, "run", return_value=output), self.assertRaises(loader.LoadError):
            loader.check()

    def test_command_failure_or_timeout_does_not_disclose_private_output(self):
        failures = [subprocess.CompletedProcess([], 1, "PRIVATE CONFIG", "PRIVATE CONFIG"),
                    subprocess.TimeoutExpired([], 45, output="PRIVATE CONFIG")]
        for failure in failures:
            kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
            with mock.patch.object(loader.subprocess, "run", **kwargs), self.assertRaises(loader.LoadError) as error:
                loader.run(["--load-all"])
            self.assertNotIn("PRIVATE", str(error.exception))

    def test_role_preserves_apparmor_enforcement_and_checks_actual_loaded_state(self):
        tasks = (ROLE / "tasks/main.yml").read_text()
        override = (ROLE / "templates/strongswan-override.conf.j2").read_text()
        self.assertIn("/etc/usenet-vpn/swanctl.conf r,", tasks)
        self.assertIn("ansible.builtin.blockinfile:", tasks)
        self.assertNotIn("/etc/usenet-vpn/**", tasks)
        self.assertNotIn("aa-complain", tasks)
        self.assertLess(tasks.index("/usr/sbin/apparmor_parser"), tasks.index("Start the systemd IPsec daemon"))
        self.assertIn("load-vpn.py load", override)
        self.assertNotIn("--load-all", override)
        self.assertIn("Verify that the expected connection and child are loaded", tasks)


if __name__ == "__main__":
    unittest.main()
