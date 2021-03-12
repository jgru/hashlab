import re
import subprocess
import utils
import logging

logger = logging.getLogger(__name__)


class VMHandler:
    """
    This class wraps all basic functionality of a VM, by creating a simple API to exposing VBoxManage calls to
    the subclasses.
    """
    def __init__(self, uuid, user, password):
        # Store credentials for accessing VM via VBoxManage
        self.uuid = uuid
        self.user = user
        self.password = password
        self.snap_list = []

    def start(self, type="headless"):
        self.start_vm(self.uuid, type)

    def gen_snap(self, snap_name, desc=""):
        self.snap_list.append(self.generate_snapshot(self.uuid, snap_name, desc))

    def del_snap(self, snap_name):
        snap_uuid = VMHandler.retrieve_snapshot_uuid(self.uuid, snap_name)

        if snap_uuid in self.snap_list:
            self.delete_snapshot(self.uuid, snap_name)

    def save(self):
        self.save_state(self.uuid)

    def restore(self, uuid_snap):
        self.restore_state(self.uuid, uuid_snap)

    def dump_vm_vdi(self, file_path):
        """
        Dumps a VDI to disk and does the required work beforehand.

        :param uuid_vm: UUID of VM
        :param file_path: path to the destination VDI
        :return:
        """
        uuid_hdd = VMHandler.retrieve_hdd_uuid(self.uuid, is_verbose=True)
        VMHandler.write_raw_img(uuid_hdd, file_path)

    @staticmethod
    def run_basic_shell_cmd(cmd):
        """
        Takes a command and executes it with the help of Popen.
        """

        # Run cmd
        subprocess.run(cmd, shell=True, check=True)

    @staticmethod
    def run_shell_cmd(cmd):
        """
        Takes a command and executes it with the help of Popen.

        :param cmd: the command to execute in form of a list
        :return: rc, status code of the process
        """

        return utils.run_shell_cmd(cmd)

    @staticmethod
    def run_cmd_with_output(cmd):
        """
        Takes a command and executes it with the help of Popen. The stdout will received and returned.

        :param cmd: the command to execute in form of a list
        :return: stdout, a string containing the contents stdout
        """
        return utils.run_cmd_with_output(cmd)

    @staticmethod
    def retrieve_vm_uuid(vm_name):
        """
        Retrieves the UUID to a string identifier of a VM
        :param vm_name: string, name of the VM
        :return: uuid_vm, string representing the UUID of the specified VM
        """
        cmd_list = ["VBoxManage", "list", "vms"]
        result_string = VMHandler.run_cmd_with_output(cmd_list)
        pattern = re.compile(r"\"" + vm_name + r"\"\s\{([-\w\d]*)\}", re.I | re.MULTILINE)
        match = re.search(pattern, result_string)

        if match:
            uuid_vm = match.group(1)
            logging.info(f"UUID of {vm_name}: {uuid_vm}")
            return uuid_vm
        else:
            logging.error(f"Could not retrieve UUID of given VM name {vm_name}")
            return None

    @staticmethod
    def retrieve_snapshot_uuid(uuid_vm, snap_name):
        """
        Retrieves the UUID of a snapshot, which is defined by name

        :param uuid_vm: UUID of the VM in question
        :param snap_name: name of the snapshot
        :return: snap_uuid, string representation of the UUID of the named snapshot
        """

        cmd = ["VBoxManage", "showvminfo", uuid_vm, "--machinereadable"]

        result_string = VMHandler.run_cmd_with_output(cmd)

        pattern = re.compile(r"SnapshotName(-\d){?}=\"(" + snap_name + r")[]\"\nSnapshotUUID=\"([-\w\d]*)\"", re.I | re.MULTILINE)
        match = re.search(pattern, result_string)

        #print(match.groups)
        if match:
            snap_uuid = match.group(-1)
            logging.info(f"UUID of snapshot '{snap_name}': {snap_uuid}")
            return snap_uuid

        else:
            logging.error(f"Snapshot UUID of '{snap_name}' could not be found.")
            return None

    @staticmethod
    def generate_snapshot(uuid_vm, snap_name, description=""):
        """
        Generates a snapshot

        :param uuid_vm: UUID of the VM
        :param snap_name: name for the snapshot to create
        :param description: description of the snapshot to create
        :return:
        """
        cmd = ["VBoxManage", "snapshot", uuid_vm, "take", snap_name, "--description", description]
        VMHandler.run_shell_cmd(cmd)

        snap_uuid = VMHandler.retrieve_snapshot_uuid(uuid_vm, snap_name)
        logging.info(f"Generated snapshot '{snap_name}': {snap_uuid}")

        return snap_uuid

    @staticmethod
    def delete_snapshot(uuid_vm, snap_name, description=""):
        """
        Generates a snapshot

        :param uuid_vm: UUID of the VM
        :param snap_name: name for the snapshot to create
        :param description: description of the snapshot to create
        :return:
        """

        cmd = ["VBoxManage", "snapshot", uuid_vm, "delete", snap_name]
        VMHandler.run_shell_cmd(cmd)

        logging.info(f"Deleted snapshot '{snap_name}'")


    @staticmethod
    def restore_state(uuid_vm, uuid_snap):
        """
        Restores the given snapshot of a VM

        :param uuid_vm: UUID of VM
        :param uuid_snap: UUID of snapshot
        """

        # Defines command
        cmd = ["VBoxManage", "snapshot", uuid_vm, "restore", uuid_snap]
        rc = VMHandler.run_shell_cmd(cmd)
        if rc:
            # Special logging, if an error occurs
            logging.error(f"Not able to restore snapshot {uuid_snap}")

    @staticmethod
    def save_state(uuid_vm):
        """
        Saves the machine state of a VM.

        :param uuid_vm: UUID of the VM
        """

        # Stop VM and save state
        cmd_savestate = ["VBoxManage", "controlvm", uuid_vm, "savestate"]
        rc = VMHandler.run_shell_cmd(cmd_savestate)
        if rc:
            # Special logging, if an error occurs
            logging.error(f"Not able to save state {uuid_vm}")

    @staticmethod
    def start_vm(uuid_vm, type="headless"):
        """
        Starts a VM according to the given type (default value is headless).

        :param uuid_vm: UUID of the VM
        :param type: maybe "headless" or "gui"
        """

        cmd_start = ["VBoxManage", "startvm", uuid_vm, "--type", type]
        VMHandler.run_shell_cmd(cmd_start)

    STORAGE_CTL = ["IDE Controller", "SATA"]

    @staticmethod
    def retrieve_hdd_uuid(uuid_vm, is_verbose=False):
        """
        Retrieves the UUID of the attached HDD of a VM.

        :param uuid_vm: UUID of the VM
        :param is_verbose: boolean - defines, wether UUID of HDD should be logged
        """

        cmd_info = ["VBoxManage", "showvminfo", uuid_vm, "--machinereadable"]
        match = None
        uuid_hdd = None
        #print(f"Looking for {VMHandler.STORAGE_CTL}")
        # Make sure to receive showvminfo output
        for ctl in VMHandler.STORAGE_CTL:
            result = VMHandler.run_cmd_with_output(cmd_info)
            pt = re.compile(f"(\"{ctl}-ImageUUID-0-0\")(=)\"([-\w\d]*)\"", re.I)

            match = re.search(pt, result)
            if match:
                uuid_hdd = match.group(3)
                break

        logging.info(f"UUID of HDD: {uuid_hdd}")

        return uuid_hdd

    @staticmethod
    def write_raw_img(uuid_hdd, file_path):
        """
        Clones a virtual hard drive to the given file path.

        :param uuid_hdd: UUID of the HDD (VDI) to clone
        :param file_path: path to the destination vdi
        :return:
        """

        '''
        Try to delete an already existing hdd with the identical name
        Even if not existing in file system, there might be a registered hdd
        '''
        cmd_del = ["VBoxManage", "closemedium", file_path, "--delete"]
        VMHandler.run_shell_cmd(cmd_del)
        logging.info(f"Deleting {file_path}, if existing")

        # Write raw img to disk
        cmd_clone = ["VBoxManage", "clonemedium", uuid_hdd, file_path, "--format", "RAW"]
        logging.info(f"Cloning HDD to {file_path}")
        VMHandler.run_shell_cmd(cmd_clone)

    @staticmethod
    def retrieve_vm_uuid(vm_name):
        """
        Retrieves the UUID to a string identifier of a VM
        :param vm_name: string, name of the VM
        :return: uuid_vm, string representing the UUID of the specified VM
        """
        cmd_list = ["VBoxManage", "list", "vms"]
        result_string = VMHandler.run_cmd_with_output(cmd_list)
        pattern = re.compile(r"\"" + vm_name + r"\"\s\{([_-\w\d]*)\}", re.I | re.MULTILINE)
        match = re.search(pattern, result_string)

        if match:
            uuid_vm = match.group(1)
            logging.info(f"UUID of {vm_name}: {uuid_vm}")
            return uuid_vm
        else:
            logging.error(f"Could not retrieve UUID of given VM name {vm_name}")
            return None

    @staticmethod
    def retrieve_snapshot_uuid(uuid_vm, snap_name):
        """
        Retrieves the UUID of a snapshot, which is defined by name

        :param uuid_vm: UUID of the VM in question
        :param snap_name: name of the snapshot
        :return: snap_uuid, string representation of the UUID of the named snapshot
        """

        cmd = ["VBoxManage", "showvminfo", uuid_vm, "--machinereadable"]
        result_string = VMHandler.run_cmd_with_output(cmd)

        pattern = re.compile(r"SnapshotName(-\d\d?){0,}=\"(" + snap_name + r")\"\nSnapshotUUID(-\d\d?){0,}=\"([-\w\d]*)\"", re.I | re.MULTILINE)
        match = re.search(pattern, result_string)

        if match:
            matches = match.groups()

            snap_uuid = matches[-1]
            logging.info(f"UUID of snapshot '{snap_name}': {snap_uuid}")
            return snap_uuid

        else:
            logging.error(f"Snapshot UUID of '{snap_name}' could not be found.")
            return None

    @staticmethod
    def generate_snapshot(uuid_vm, snap_name, description=""):
        """
        Generates a snapshot

        :param uuid_vm: UUID of the VM
        :param snap_name: name for the snapshot to create
        :param description: description of the snapshot to create
        :return:
        """
        cmd = ["VBoxManage", "snapshot", uuid_vm, "take", snap_name, "--description", description]
        VMHandler.run_shell_cmd(cmd)

        snap_uuid = VMHandler.retrieve_snapshot_uuid(uuid_vm, snap_name)
        logging.info(f"Generated snapshot '{snap_name}': {snap_uuid}")

        return snap_uuid