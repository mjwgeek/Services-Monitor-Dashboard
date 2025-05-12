#!/bin/bash
/usr/bin/python3 /home/servicemonitor/prefetch_services.py
exec /usr/bin/python3 /home/servicemonitor/app.py
