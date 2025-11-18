set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

# Fetch the Home Assistant YAML configs into new-hass-configs/
fetch:
	mkdir -p new-hass-configs
	rsync -av \
		--delete \
		--prune-empty-dirs \
		--include '*/' \
		--include '*.yaml' \
		--include '*.yml' \
		--include '*.json' \
		--include '*.sh' \
		--exclude '.git/' \
		--exclude '.cloud/' \
		--exclude '.storage/' \
		--exclude 'deps/' \
		--exclude 'tts/' \
		--exclude 'secrets.yaml' \
		--exclude '*.db*' \
		--exclude '*.log' \
		--exclude '*.pickle' \
		--exclude '*.uuid' \
		--exclude '*~' \
		--exclude '*.pyc' \
		--exclude '__pycache__/' \
		--exclude '*' \
		-e "ssh -p 22" \
		root@homeassistant.local:/config/ new-hass-configs/
