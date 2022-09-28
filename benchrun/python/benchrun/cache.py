import subprocess


class CacheManager:
    _drop_failed = False
    _purge_failed = False

    def sync_and_drop(self):
        if not self._drop_failed:
            command = "sync; echo 3 | sudo tee /proc/sys/vm/drop_caches"
            try:
                subprocess.run(command, shell=True, check=True)
                return True
            except subprocess.CalledProcessError:
                self._drop_failed = True

        if not self._purge_failed:
            command = "sync; sudo purge"
            try:
                subprocess.run(command, shell=True, check=True)
                return True
            except subprocess.CalledProcessError:
                self._purge_failed = True

        return False
