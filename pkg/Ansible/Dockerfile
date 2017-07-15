# https://store.docker.com/community/images/williamyeh/ansible

FROM    williamyeh/ansible:ubuntu14.04-onbuild
RUN     ansible-playbook-wrapper
RUN     ansible-playbook -i inventory.ini playbook.yml \
            --connection=local --sudo
