set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
tmp_dir := "/tmp/new-hass-configs"
ha_container := "homeassistant"

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

# Validate the contents of new-hass-configs/ on Home Assistant and show what would change (no apply).
check:
		test -d new-hass-configs
		ssh -p 22 root@homeassistant.local "rm -rf \"{{tmp_dir}}\" && mkdir -p \"{{tmp_dir}}\""
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
		    new-hass-configs/ root@homeassistant.local:"{{tmp_dir}}"/
	ssh -p 22 root@homeassistant.local "if [ -f /config/secrets.yaml ]; then cp /config/secrets.yaml \"{{tmp_dir}}\"/; fi"
	ssh -p 22 root@homeassistant.local "\
		set -euo pipefail; \
		backup_dir=\"/tmp/hass-config-backup\"; \
		rm -rf \"${backup_dir}\"; \
		mkdir -p \"${backup_dir}\"; \
		rsync -a --delete /config/ \"${backup_dir}\"/; \
		rsync -av --delete --prune-empty-dirs \
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
			\"{{tmp_dir}}\"/ /config/; \
		ha core check; \
		rsync -a --delete \"${backup_dir}\"/ /config/; \
		rm -rf \"${backup_dir}\""
	echo "Diff against /config (dry-run):"
	rsync -av --delete --itemize-changes --dry-run \
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
		new-hass-configs/ root@homeassistant.local:/config/ \
		| sed 's/^/  /'
	ssh -p 22 root@homeassistant.local "rm -rf \"{{tmp_dir}}\""

# Push the contents of new-hass-configs/ to Home Assistant, validate, and restart.
push:
			test -d new-hass-configs
	ssh -p 22 root@homeassistant.local "rm -rf \"{{tmp_dir}}\" && mkdir -p \"{{tmp_dir}}\""
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
		    new-hass-configs/ root@homeassistant.local:"{{tmp_dir}}"/
	ssh -p 22 root@homeassistant.local "if [ -f /config/secrets.yaml ]; then cp /config/secrets.yaml \"{{tmp_dir}}\"/; fi"
	ssh -p 22 root@homeassistant.local "\
		set -euo pipefail; \
		backup_dir=\"/tmp/hass-config-backup\"; \
		rm -rf \"${backup_dir}\"; \
		mkdir -p \"${backup_dir}\"; \
		rsync -a --delete /config/ \"${backup_dir}\"/; \
		rsync -av --delete --prune-empty-dirs \
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
			\"{{tmp_dir}}\"/ /config/; \
		if ha core check; then \
			rm -rf \"${backup_dir}\"; \
		else \
			rsync -a --delete \"${backup_dir}\"/ /config/; \
			rm -rf \"${backup_dir}\"; \
			exit 1; \
		fi"
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
		new-hass-configs/ root@homeassistant.local:/config/
	ssh -p 22 root@homeassistant.local "ha core restart"
	ssh -p 22 root@homeassistant.local "rm -rf \"{{tmp_dir}}\""
