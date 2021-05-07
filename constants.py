#!/usr/bin/env python3

########################################
# Projects
########################################
# GCP Projects that you want to make DHCP logs for
PROJECTS = [
    "example-project-name",
    "example-project-name2",
]

########################################
# Developent (--dev) variables
########################################
# gcloud command path on your development machine, e.g. /usr/bin/gcloud
PATH_TO_GCLOUD_COMMAND_DEV = ""


########################################
# Production variables
########################################
# gcloud command path on your machine, e.g. /snap/bin/gcloud
PATH_TO_GCLOUD_COMMAND = ""
# Folder to cache historic logs to, e.g. /var/log/
FOLDER_FOR_HISTORIC_LOGS = ""
# Folder to cache logs to send to Chronicle to, e.g. /var/log/  
# This is the same path that you will use for the docker run command
FOLDER_FOR_CHRONICLE_LOGS = ""

