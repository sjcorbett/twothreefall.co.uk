#!/bin/bash
sudo /etc/init.d/celeryd start
sudo /etc/init.d/apache2 start
sudo /etc/init.d/memcached start
sudo /etc/init.d/memcached force-reload
