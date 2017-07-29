# https://store.docker.com/community/images/williamyeh/ansible

FROM    williamyeh/ansible:ubuntu14.04-onbuild
RUN     ansible-playbook -vvv \
            -i inventory.ini \
            playbook.yml
