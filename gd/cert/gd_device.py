#!/usr/bin/env python3
#
#   Copyright 2019 - The Android Open Source Project
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import collections
import logging
import math
import os
import re
import socket
import time
from builtins import open
from builtins import str
from datetime import datetime
import signal
import subprocess

from acts import error
from acts import logger as acts_logger
from acts import tracelogger
from acts import utils
from acts.libs.proc import job

import grpc

from hal.facade import api_pb2
from hal.facade import api_pb2_grpc

ANDROID_BUILD_TOP = os.environ.get('ANDROID_BUILD_TOP')
ANDROID_HOST_OUT = os.environ.get('ANDROID_HOST_OUT')

ACTS_CONTROLLER_CONFIG_NAME = "GdDevice"
ACTS_CONTROLLER_REFERENCE_NAME = "gd_devices"

def create(configs):
    if not configs:
        raise GdDeviceConfigError("Configuration is empty")
    elif not isinstance(configs, list):
        raise GdDeviceConfigError("Configuration should be a list")
    else:
        # Configs is a list of dicts.
        devices = get_instances_with_configs(configs)

    return devices


def destroy(devices):
    for device in devices:
        try:
            device.clean_up()
        except:
            device.log.exception("Failed to clean up properly.")


def get_info(devices):
    return []


def get_post_job_info(ads):
    return 'Not implemented'


def get_instances_with_configs(configs):
    print(configs)
    devices = []
    for config in configs:
        resolved_cmd = []
        for entry in config["cmd"]:
            resolved_cmd.append(replace_vars(entry, config))

        device = GdDevice(config["grpc_port"], resolved_cmd, config["label"])
        devices.append(device)
    return devices

def replace_vars(string, config):
    return string.replace("$ANDROID_HOST_OUT", ANDROID_HOST_OUT) \
                 .replace("$(grpc_port)", config.get("grpc_port")) \
                 .replace("$(rootcanal_port)", config.get("rootcanal_port"))

class GdDevice:
    def __init__(self, grpc_port, cmd, label):
        print(cmd)
        self.label = label if label is not None else grpc_port
        # logging.log_path only exists when this is used in an ACTS test run.
        log_path_base = getattr(logging, 'log_path', '/tmp/logs')
        self.log = tracelogger.TraceLogger(
            GdDeviceLoggerAdapter(logging.getLogger(), {
                'device': label
            }))

        backing_process_logpath = os.path.join(
            log_path_base, 'GdDevice_%s_backing_logs.txt' % label)
        self.backing_process_logs = open(backing_process_logpath, 'w')

        self.backing_process = subprocess.Popen(
            cmd,
            cwd=ANDROID_BUILD_TOP,
            env=os.environ.copy(),
            stdout=self.backing_process_logs,
            stderr=self.backing_process_logs)

        self.grpc_channel = grpc.insecure_channel("localhost:" + grpc_port)
        self.hal = api_pb2_grpc.HciTransportationStub(self.grpc_channel)

    def clean_up(self):
        self.grpc_channel.close()
        self.backing_process.send_signal(signal.SIGINT)
        self.backing_process_logs.close()

class GdDeviceLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        msg = "[GdDevice|%s] %s" % (self.extra["device"], msg)
        return (msg, kwargs)

class GdDeviceConfigError(Exception):
    """Raised when GdDevice configs are malformatted."""


class GdDeviceError(error.ActsError):
    """Raised when there is an error in GdDevice."""
