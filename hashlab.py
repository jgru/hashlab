#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import vagrant
import os
import logging
import re
import utils
from virtualbox_vm_handler import VMHandler
from disk_processor import DiskProcessor

#sh = logger.StreamHandler()
#logger = logger.getLogger(__name__)
#sh.setLevel(logger.INFO)
#logger.addHandler(sh)

logger = logging.getLogger()


def get_virtualbox_vm_name(vagrantfile):
    """
    Retrieves name of the VM as specified in the vagrantfile like this

    config.vm.provider :virtualbox do |vb|
       vb.name = "win10-updates-only"
    end

    This is needed to get a reference on the running machine and be able to dump disk.

    :param vagrantfile: absolute path to vagrant file
    :return: vm_name: name of the VM as seen by VirtualBox/vboxmanage

    """
    with open(vagrantfile, "r") as f:
        data = f.read()

    pattern = r"vb.name\s?=\s?\"([-_a-zA-Z0-9]*)\""
    match = re.search(pattern, data)

    if match:
        vm_name = match.group(1)
        logger.info(f"Name of VirtualBox VM from {vagrantfile}: {vm_name}")
        return vm_name
    else:
        logger.error(f"Could not retrieve VM name from {vagrantfile}")
        return None


def check_operation_mode(vd):
    """
    Checks, if a snapshot has to be stored and/or provisioning for everytime. This is assumed, when a file name
    "cumulate" is existing as sibling to vagrantfile.

    :param vd: directory, where vagrantfile and its sibling lives in
    :return: is_cumulate, is_always_provision, booleans specifying, whether to cumulate vm states and/or run
    provisioners everytime
    """
    files = [f for f in os.listdir(vd) if os.path.isfile(os.path.join(vd, f))]

    if "cumulate" in files:
        logger.info(f"Cumulation set for {vd}")
        is_cumulate = True
    else:
        is_cumulate = False

    if "provision_always" in files:
        logger.info(f"Provision always set for {vd}")
        is_always_provision = True
    else:
        is_always_provision = False

    return is_cumulate, is_always_provision


def find_vagrantfiles(box_dir):
    """
    Looks for vagrantfiles recursively

    :param box_dir: directory where vagrantfiles are exepected to reside
    :return: list of absolute paths to vagrantfiles
    """

    vfiles = []

    # Recurses directory and looks for files named vagrantfile
    for root, dirs, files in os.walk(os.path.abspath(box_dir), topdown=False):
        for f in files:
            if f.startswith("vagrantfile") and not f.endswith("~") and not f.startswith("#"):
                vfiles.append(os.path.join(root, f))
    return vfiles


def control_virtualbox_vm(vf, clonedir="/tmp"):
    """
    Controls the hdd cloning of VM, which vagrant created. It creates a snapshot at first, then clones the disk as raw
    to the given directory (clonedir). Afterwards the UUID of the disk is retrieved, to clone it.
    Important note: The name of the imported VM has to be specified by the line r"vb.name\s?=\s?\"([-_a-zA-Z0-9]*)\""
    in the vagrantfile.

    :param vf: abs path to vagrantfile of the VM, which is currently up and running
    :param clonedir: path to directory, where image will be stored

    :return: vm_name: name of the corresponding VM as seen by VirtualBox/vboxmanage
    """

    # Retrieve name
    vm_name = get_virtualbox_vm_name(vf)

    # Build handler
    handler = VMHandler(vm_name, "vagrant", "vagrant")

    # Take snapshot after full provisioning
    snap_name = "tmp"
    handler.gen_snap(snap_name)

    # Save machine state
    handler.save()
    logger.info(f"Saved state of {vm_name} ")

    disk_fp = os.path.join(clonedir, f"{vm_name}.dd")

    # Set this for parsing UUID of disk
    handler.dump_vm_vdi(disk_fp)
    logger.info(f"Cloned disk of {vm_name} to {disk_fp}")

    #handler.del_snap(snap_name)

    return vm_name, disk_fp


def main(box_dir="../boxes", result_dir="../results", interactive=False, time=False):
    setup_logging(args.time)
    logger.info(f"Processing boxes in {box_dir}")
    logger.info(f"Storing results in {result_dir}")

    vfiles = find_vagrantfiles(box_dir)

    logger.info(f"Found {len(vfiles)} vagrantfiles")

    # Process all vagrant boxes
    for vf in vfiles:
        vd = os.path.dirname(vf)
        logger.info(f"Starting vagrantfile in {vd}")
        vbox = vagrant.Vagrant(vd)

        is_cumulate, is_always_provision = check_operation_mode(vd)

        if is_cumulate:
            try:
                vbox.snapshot_pop()
            except RuntimeError:
                logger.info("No pushed snapshot, skipping restore")
                pass

        # Brings vagrant box up
        if is_always_provision:
            logger.info("Calling vagrant up --provision")
            vbox.up(provision=True)
        else:
            logger.info("Calling vagrant up --provision")
            vbox.up()

        if interactive:
            logger.info("Modify the running VM. Waiting until user input.")
            utils.wait_for_confirm()

        vm_name, disk_fp = control_virtualbox_vm(vf)

        if is_cumulate:
            vbox.snapshot_push()

        vbox.halt()

        # Mount image
        dp = DiskProcessor(disk_fp)
        # Hash all volumes with hashrat and store result in result_dir
        dp.hash_with_hashrat(result_dir)
        # Unmount and clean up
        del dp

        # Delete cloned medium
        utils.run_shell_cmd(["rm", disk_fp])  # further cleanup is done by DiskProcessor's destructor
        logger.info(f"Completed processing of {vf}")


def setup_logging(log_with_time=False):
    logger.setLevel(logging.INFO)
    console_log = logging.StreamHandler()

    if log_with_time:
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(funcName)-30s %(message)s')
        console_log.setFormatter(formatter)

    console_log.setLevel(logging.INFO)
    logger.addHandler(console_log)


def parse_args():
    """
    Parses the command line arguments.
    """

    parser = argparse.ArgumentParser(
        description="Hashlab is a tool to generate lists of hashes of known benign and common files, which can be used for whitelisting in DFIR workflows. By leveraging vagrant and vboxmanage this can be accomplished in a highly automated manner.")
    parser.add_argument('--box-dir', type=str, default="../boxes",
                        help="Path to the directory, which contains subdirectories with the vagrantfiles and the neccessary files for provisioning.")
    parser.add_argument('--result-dir', type=str, default="../results",
                        help="Path to the directory, where the resulting hashlists should be stored.")
    parser.add_argument('--interactive', help='Pause after vagrant up to interactively/manualy modify VM',
                        action='store_true')
    parser.add_argument('--time', help='Log with timestamps', action='store_true')

    return parser.parse_args()


if __name__ == '__main__':
    # Example call:
    # sudo venv/bin/python3.7 hashlab.py --box-dir /home/user01/boxes --result-dir /home/user01/Desktop/

    # Note sudo is needed for image mounting!
    if os.geteuid() != 0:
        exit("[!] You need to have root privileges to run this script.\n[+] Please try again, 'sudo'. Exiting.")
    args = parse_args()
    main(**vars(args))
