
# Make sure to install: sudo apt-get install xmount ewf-tools afflib-tools sleuthkit disktype python-magic
from imagemounter import ImageParser

import os
import utils
import logging
import datetime

logger = logging.getLogger()


class DiskProcessor:
    """
    Bundles functionality, needed for mounting and hashing disk images.
    """

    def __init__(self, img_path):
        """
        Creates a DiskProcessor corresponding to the given image

        :param img_path, absolute path to dd image
        """

        self.img_path = img_path
        self.img_label = os.path.basename(img_path).split(".")[0]
        self.mount_parent = "/tmp"
        self.mount_stub = "img_mnt"
        self.mount_path, self.volume_mount_paths = self._mount_dd_img()
        self.is_mounted = True

    # See https://github.com/ralphje/imagemounter/blob/master/examples/simple_cli.py#L64
    def _mount_dd_img(self):
        """
        Mounts a dd image and all of its volumes and returns a list of directory paths to each volume, as well as the
        mount path for the disk image itself.

        :return: path_to_mountpoint, list of paths to mounted volumes
        """
        parser = ImageParser([self.img_path], pretty=True, mountdir=self.mount_parent, casename=self.mount_stub, disk_mounter="xmount")
        volume_mount_paths = []

        for volume in parser.init(single=True, swallow_exceptions=True):

            # parser.init() loops over all volumes and mounts them
            if volume.mountpoint:
                # If the mountpoint is set, we have successfully mounted it
                logger.info(f"Mounted volume {volume.get_description()} on {volume.mountpoint}")
                volume_mount_paths.append((volume.mountpoint))

            elif volume.exception and volume.size is not None and volume.size <= 1048576:
                # If an exception occurred, but the volume is small, this is just a warning
                logger.info(f"Exception while mounting small volume {volume.get_description()}")

            elif volume.exception:
                # Other exceptions are a bit troubling. Should never happen, actually.
                logger.debug(f"Exception while mounting {volume.get_description()}")

        return parser.disks[0].mountpoint, volume_mount_paths

    def hash_with_hashrat(self, result_dir):
        """
        Hashes all files in the directories, where the volumes are mounted on.

        :param result_dir: path to directory, where the resulting hash lists will be stored.
        """
        if self.is_mounted:
            # Hash all volumes, requires hashrat
            for d in self.volume_mount_paths:
                logger.info(f"Hashing {d}")
                hashresults = utils.run_cmd_with_output(["hashrat", "-trad", "-md5", "-r", d])

                # Erases the information stemming of the mount point from hashlist
                hashresults_clean = hashresults.replace(os.path.join(self.mount_parent, self.mount_stub), "")

                # Writes hashlist to disk
                dt_label = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H%M")
                vol_label = os.path.basename(d)
                with open(os.path.join(result_dir, f"{dt_label}_{self.img_label}_{vol_label}"), "w") as f:
                    f.write(hashresults_clean)

    def __del__(self):
        """
        Destructor is responsible for cleaning up all artifacts. This covers unmounting and deleting the mountpoints.
        The mount_stub remains unchanged.
        """

        if self.is_mounted:
            for d in self.volume_mount_paths:
                logger.info(f"Cleaning up {d}")
                # Unmount and clean up
                utils.run_shell_cmd(["sudo", "umount", d])
                utils.run_shell_cmd(["sudo", "rm", "-r", d])

            logger.info(f"Cleaning up {self.mount_path}")
            utils.run_shell_cmd(["sudo", "umount", self.mount_path])
            utils.run_shell_cmd(["sudo", "rm", "-r", self.mount_path])


if __name__ == "__main__":
    dp = DiskProcessor()
